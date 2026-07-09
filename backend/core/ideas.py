"""Daily startup-idea engine.

Two-step generation:
  1. SCAN — Claude with live web search builds a brief of *current* shifts in the
     founder's areas, fused with signals from the user's own AI-newsletter feed
     (the digest buckets — "the AI newspaper").
  2. SYNTHESIZE — Claude turns that brief + the founder profile into concrete,
     non-obvious startup ideas, each tied to a specific signal (why now) and the
     founder's specific edge (why you), with a weekend-buildable first wedge.

Ideas are deduped against recent titles and persisted so they accumulate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import founder
from core.llm import (
    DRAFT_MODEL,
    EMPHASIS_GUIDE,
    complete,
    complete_with_search,
    extract_json,
)
from db.models import Email, Idea, Project

log = logging.getLogger("adjutant.ideas")

_SCAN_SYSTEM = """You are a venture scout. Using web search, identify what is shifting \
RIGHT NOW (last few weeks) across the founder's areas of credibility — new AI \
capabilities, model releases, regulatory moves, funding rounds, infrastructure gaps, \
emerging pain points. Combine that with the signals from their own AI-newsletter feed \
provided below.

Write a tight intelligence brief (8–15 bullet points) of concrete, datable shifts and \
the openings they create. Prefer specific over generic. Cite what you found (source/date)."""

_IDEA_SYSTEM = """You are a sharp startup-idea generator working for ONE specific founder. \
You get their profile (their real, unfair edges), an intelligence brief of current shifts, \
and a required LANE MIX. Propose startup ideas that only THIS founder is unusually well-\
positioned to win right now.

Hard rules:
- Honor the LANE MIX exactly: produce the requested number of ideas per lane, and set each \
idea's "lane" field accordingly.
- VARIETY IS MANDATORY. No two ideas may target the same sub-market, and the batch must \
not collapse onto a single type of product. Do not make everything a dev tool.
- Each idea must ride a SPECIFIC current shift from the brief (a real "why now"), not an \
evergreen SaaS truism.
- "why_you" must cite the founder's ACTUAL edges from their profile, picking whichever \
genuinely fits this idea. Be specific, not flattery.
- "first_step" = a concrete wedge buildable in a weekend or two that produces a sharp \
initial signal of demand.
- Avoid the listed EXISTING IDEAS; bring genuinely new angles.

Respond with ONLY this JSON, no prose:
{
  "ideas": [
    {
      "title": "<punchy product name or 4–8 word concept>",
      "pitch": "<one vivid sentence: what it is and for whom>",
      "lane": "<one of: core | adjacent | broad | wildcard>",
      "domain": "<short tag, e.g. 'dev tools', 'marketplace', 'fintech'>",
      "score": <integer 1–5: fit × timing × buildability>,
      "why_now": "<the specific current shift it rides>",
      "why_you": "<the founder's specific edge that makes them unfair here>",
      "first_step": "<weekend-buildable wedge to test demand>",
      "market": "<who pays and a rough sense of size/willingness>",
      "signal": "<the source/trend it came from>"
    }
  ]
}"""

# The lanes the engine can draw from, relative to the founder profile.
LANES: dict[str, str] = {
    "core": "CORE: squarely in the founder's primary domain(s) from the profile; "
    "leans hardest on their strongest, most credible edge.",
    "adjacent": "ADJACENT: one step out from the core domain, where the edge still "
    "transfers but the market is new to them.",
    "broad": "BROAD: any domain, including well outside their background: consumer, "
    "fintech, dev tools, vertical SaaS, productivity, hardware.",
    "wildcard": "WILDCARD: deliberately unexpected, contrarian, or playful bets that "
    "still connect to at least one real edge from the profile.",
}


def _resolve_mix(focus: str, n: int) -> dict[str, int]:
    """Map a focus choice to a per-lane idea-count quota."""
    focus = (focus or "balanced").lower()
    if focus in LANES:  # single-lane focus
        return {focus: n}
    # balanced: spread across the three exploration lanes.
    base, rem = divmod(n, 3)
    mix = {"core": base, "adjacent": base, "broad": base}
    for lane in ("core", "adjacent", "broad")[:rem]:
        mix[lane] += 1
    return {k: v for k, v in mix.items() if v > 0}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _gather_signals(session: Session, days: int = 21, limit: int = 60) -> str:
    """Recent items from the digest feed buckets — the user's 'AI newspaper'."""
    digest_ids = select(Project.id).where(Project.digest)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.scalars(
        select(Email)
        .where(Email.project_id.in_(digest_ids), Email.updated_at >= cutoff)
        .order_by(Email.updated_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return "(no newsletter signals available yet)"
    return "\n".join(
        f"- {r.subject[:90]} :: {' '.join((r.snippet or '').split())[:110]}"
        for r in rows
    )


def generate_ideas(
    session: Session, n: int = 6, use_web: bool = True, focus: str = "balanced"
) -> dict:
    profile = founder.load_profile()
    signals = _gather_signals(session)
    mix = _resolve_mix(focus, n)

    recent_titles = session.scalars(
        select(Idea.title).order_by(Idea.created_at.desc()).limit(40)
    ).all()
    avoid = "\n".join(f"- {t}" for t in recent_titles) or "(none yet)"

    # 1. SCAN — current shifts (web + newsletter feed)
    scan_user = (
        f"FOUNDER AREAS / PROFILE:\n{profile}\n\n"
        f"THEIR AI-NEWSLETTER SIGNALS (last weeks):\n{signals}\n\n"
        "Produce the intelligence brief now."
    )
    if use_web:
        brief = complete_with_search(DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=2500)
    else:
        brief = complete(DRAFT_MODEL, _SCAN_SYSTEM, scan_user, max_tokens=2000)

    # 2. SYNTHESIZE — structured ideas, spread across the requested lanes
    mix_lines = "\n".join(
        f"- {count} idea(s) in lane '{lane}': {LANES[lane]}" for lane, count in mix.items()
    )
    idea_user = (
        f"FOUNDER PROFILE:\n{profile}\n\n"
        f"INTELLIGENCE BRIEF (current shifts):\n{brief}\n\n"
        f"EXISTING IDEAS (avoid repeating):\n{avoid}\n\n"
        f"REQUIRED LANE MIX (produce exactly this distribution):\n{mix_lines}\n\n"
        f"Generate {sum(mix.values())} ideas total, honoring the lane mix and variety rules."
    )
    raw = complete(DRAFT_MODEL, _IDEA_SYSTEM + "\n\n" + EMPHASIS_GUIDE, idea_user, max_tokens=4500)
    data = extract_json(raw)

    today = _today()
    created: list[dict] = []
    for it in data.get("ideas", [])[:n]:
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        try:
            score = max(1, min(5, int(it.get("score", 3))))
        except (TypeError, ValueError):
            score = 3
        idea = Idea(
            created_date=today,
            title=title,
            pitch=str(it.get("pitch", "")).strip(),
            domain=str(it.get("domain", "")).strip()[:60],
            score=score,
            why_now=str(it.get("why_now", "")).strip(),
            why_you=str(it.get("why_you", "")).strip(),
            first_step=str(it.get("first_step", "")).strip(),
            market=str(it.get("market", "")).strip(),
            signal=str(it.get("signal", "")).strip(),
        )
        session.add(idea)
        created.append(idea)
    session.commit()

    return {
        "generated": len(created),
        "date": today,
        "used_web": use_web,
        "ids": [i.id for i in created],
    }
