"""Research agent — digs into a standing topic via live web search and reports
findings as cards. On-demand or nightly (cadence='daily'), mirroring the scout
pattern: SCAN with web search -> structured findings grounded in who the user is.

The backend can't reach the claude.ai MCP servers (PubMed/bioRxiv) — those are
bound to the CLI session — so the agent searches scholarly + industry sources on
the open web. It is told to prefer primary sources and cite URLs.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

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
from db.models import ResearchBrief, ResearchFinding, ResearchTopic

log = logging.getLogger("adjutant.research")

_SYSTEM = """You are a rigorous research analyst with live web search, working for \
ONE person whose profile is given. You are handed a research question. Dig in: run \
several searches, read primary and high-quality sources (papers, preprints on \
pubmed/biorxiv/arxiv, company pages, filings, reputable industry press), and return \
the most important, CONCRETE, recent findings — not generic background.

Optimise for signal the person can act on, tied to who they are. Prefer specific \
facts, numbers, named players, dates and developments over vague summary. Every \
finding MUST cite a real source URL you actually used.

Respond with ONLY this JSON, no prose:
{
  "summary": "<2-3 sentence headline of what you learned — the bottom line>",
  "findings": [
    {
      "title": "<the finding, as a sharp claim or development>",
      "detail": "<1-3 sentences of specifics: who/what/when/numbers>",
      "why_matters": "<one clause: why it matters to THIS person specifically>",
      "url": "<source URL you used>",
      "source": "<publication / site name>",
      "importance": <integer 1-5: how significant this is for them>
    }
  ]
}
Return 5-10 findings, ordered by importance descending. Drop anything you cannot \
attach a real source to. Do not invent URLs."""


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def run_research(session: Session, topic: ResearchTopic, use_web: bool = True) -> dict:
    """Run one research pass for a topic, storing fresh findings."""
    topic.status = "running"
    topic.last_error = ""
    session.commit()

    profile = founder.load_profile()
    today = _today()

    # Avoid repeating findings already surfaced for this topic (daily cadence).
    recent = session.execute(
        select(ResearchFinding.title)
        .where(ResearchFinding.topic_id == topic.id)
        .order_by(ResearchFinding.created_at.desc())
        .limit(40)
    ).all()
    avoid = "\n".join(f"- {t}" for (t,) in recent) or "(none yet)"

    user = (
        f"PERSON PROFILE:\n{profile}\n\n"
        f"RESEARCH QUESTION:\n{topic.query}\n\n"
        f"TODAY: {today}\n\n"
        f"ALREADY-REPORTED FINDINGS (find NEW developments, don't repeat these):\n{avoid}\n\n"
        "Research this now and report the most important, sourced findings."
    )

    try:
        if use_web:
            raw = complete_with_search(
                DRAFT_MODEL, _SYSTEM + "\n\n" + EMPHASIS_GUIDE, user,
                max_tokens=4000, max_searches=8,
            )
        else:
            raw = complete(DRAFT_MODEL, _SYSTEM + "\n\n" + EMPHASIS_GUIDE, user, max_tokens=3000)
        data = extract_json(raw)
    except Exception as exc:  # network / API failure — record, don't crash
        log.exception("research run failed for topic %s", topic.id)
        topic.status = "error"
        topic.last_error = str(exc)[:300]
        topic.last_run_at = datetime.now(timezone.utc)
        session.commit()
        return {"topic_id": topic.id, "error": topic.last_error, "found": 0}

    created: list[ResearchFinding] = []
    for it in data.get("findings", [])[:10]:
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        try:
            imp = max(1, min(5, int(it.get("importance", 3))))
        except (TypeError, ValueError):
            imp = 3
        f = ResearchFinding(
            topic_id=topic.id,
            run_date=today,
            title=title,
            detail=str(it.get("detail", "")).strip(),
            why_matters=str(it.get("why_matters", "")).strip(),
            url=str(it.get("url", "")).strip(),
            source=str(it.get("source", "")).strip(),
            importance=imp,
        )
        session.add(f)
        created.append(f)

    topic.last_summary = str(data.get("summary", "")).strip()[:600]
    topic.last_run_at = datetime.now(timezone.utc)
    topic.status = "done"
    session.commit()

    return {"topic_id": topic.id, "summary": topic.last_summary,
            "found": len(created), "ids": [f.id for f in created]}


def run_due_topics(session: Session) -> dict:
    """Nightly pass: run every queued topic and re-run every 'daily' topic."""
    due = session.scalars(
        select(ResearchTopic).where(
            ResearchTopic.archived.is_(False),
            (ResearchTopic.status == "queued") | (ResearchTopic.cadence == "daily"),
        )
    ).all()
    ran = 0
    for topic in due:
        run_research(session, topic)
        ran += 1
    return {"ran": ran}


# ───────────────────────────── daily morning brief ─────────────────────────

# Seeded once if the user has no topics, so the brief works out of the box.
# Both tracks are profile-grounded: the agent reads the founder profile on every
# run, so these deliberately generic queries resolve to the user's actual field
# and ventures. Edit them or add your own from the Research pane.
_SEED_TOPICS = [
    # "For you": your field and career edge.
    ("you", "New papers, releases, datasets, and benchmarks in the fields, methods, "
            "and models on the founder profile"),
    ("you", "Funding calls, grants, fellowships, and career opportunities that fit "
            "the founder profile and that the other topics would miss"),
    # "Your ventures": market and competitor intel for what they're building.
    ("venture", "Competitor launches, funding rounds, and regulatory shifts in the "
                "markets the founder's ventures target"),
    ("venture", "Adjacent entrants, funding, and developments across those markets "
                "that the named venture topics would miss"),
]


def seed_default_topics(session: Session) -> None:
    """Create the two default daily topics if the user has none yet."""
    if session.scalar(select(ResearchTopic.id).limit(1)) is not None:
        return
    for track, query in _SEED_TOPICS:
        session.add(ResearchTopic(query=query, track=track, cadence="daily", status="queued"))
    session.commit()
    log.info("seeded default research topics")


def _bullets(findings: list[ResearchFinding]) -> str:
    lines = []
    for f in findings:
        src = f"[{f.source}]({f.url})" if f.url else (f.source or "")
        line = f"• {f.title}"
        if src:
            line += f" — {src}"
        lines.append(line)
    return "\n".join(lines)


def build_daily_brief(session: Session, push: bool = True) -> dict:
    """Synthesize today's fresh findings into a two-section brief (For you /
    Your ventures), store it, and push it to the configured channels."""
    today = _today()
    rows = session.execute(
        select(ResearchFinding, ResearchTopic.track)
        .join(ResearchTopic, ResearchFinding.topic_id == ResearchTopic.id)
        .where(ResearchFinding.run_date == today, ResearchFinding.status != "dismissed")
        .order_by(ResearchFinding.importance.desc(), ResearchFinding.id.desc())
    ).all()

    for_you: list[ResearchFinding] = []
    ventures: list[ResearchFinding] = []
    seen: set[str] = set()
    for finding, track in rows:
        key = (finding.title or "").lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        (ventures if track == "venture" else for_you).append(finding)

    for_md = _bullets(for_you[:6])
    ven_md = _bullets(ventures[:6])

    brief = session.scalar(select(ResearchBrief).where(ResearchBrief.day == today))
    if not brief:
        brief = ResearchBrief(day=today)
        session.add(brief)
    brief.for_you = for_md
    brief.ventures = ven_md
    session.commit()

    pushed = None
    if push and (for_md or ven_md):
        parts = []
        if for_md:
            parts.append("🔬 *For you*\n" + for_md)
        if ven_md:
            parts.append("🚀 *Your ventures*\n" + ven_md)
        from core import notify  # lazy: avoid import cycle
        pushed = notify.notify(f"📡 Your research brief · {today}", "\n\n".join(parts))

    return {"day": today, "for_you": for_md, "ventures": ven_md, "pushed": pushed}


def run_nightly(session: Session) -> dict:
    """The full nightly job: ensure topics, run them, then brief + push."""
    seed_default_topics(session)
    run_due_topics(session)
    return build_daily_brief(session, push=True)
