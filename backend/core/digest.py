"""Digest briefing — reads the feed-noise so the user doesn't have to.

Collects recent threads from digest-flagged categories and asks Claude for a
short personal briefing: only what's genuinely interesting given the user's
projects; ads and generic marketing are dropped without mention.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.llm import DRAFT_MODEL, EMPHASIS_GUIDE, complete, extract_json
from db.models import Email, Project

_TAGS = {"research", "tools", "money", "security", "event", "admin"}

_cache: dict | None = None

_SYSTEM = """You write a scannable briefing from a researcher's newsletter and feed \
mail (the mail they don't want to read themselves). You get their actual work projects \
as an interest profile, plus recent feed threads (sender | subject | snippet).

Pick ONLY items genuinely worth their attention given that profile: relevant research, \
useful tools, real opportunities. Drop ads, promotions, engagement bait, and generic \
marketing entirely.

Respond with ONLY this JSON, no prose:
{
  "highlights": [
    {
      "title": "<punchy 4–9 word headline>",
      "detail": "<one sentence: what it is and why it matters to THEM>",
      "tag": "<exactly one of: research | tools | money | security | event | admin>"
    }
  ]
}
3–8 highlights, most relevant first. Empty list if nothing is worthwhile."""


def build_briefing(
    session: Session, days: int = 7, max_threads: int = 120, refresh: bool = False
) -> dict:
    global _cache
    if _cache is not None and not refresh:
        return _cache
    digest_projects = session.scalars(select(Project).where(Project.digest)).all()
    if not digest_projects:
        return {
            "highlights": [],
            "threads": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    ids = [p.id for p in digest_projects]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.scalars(
        select(Email)
        .where(Email.project_id.in_(ids), Email.updated_at >= cutoff)
        .order_by(Email.updated_at.desc())
        .limit(max_threads)
    ).all()
    if not rows:
        return {
            "highlights": [],
            "threads": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    interests = session.scalars(
        select(Project).where(Project.digest.is_(False))
    ).all()
    profile = "\n".join(f"- {p.name}: {p.description}" for p in interests) or "(none)"
    listing = "\n".join(
        f"{r.last_sender[:40]} | {r.subject[:90]} | {' '.join((r.snippet or '').split())[:110]}"
        for r in rows
    )
    raw = complete(
        DRAFT_MODEL,
        _SYSTEM + "\n\n" + EMPHASIS_GUIDE,
        f"INTEREST PROFILE (their projects):\n{profile}\n\n"
        f"FEED THREADS ({len(rows)}, newest first):\n{listing}",
        max_tokens=1500,
    )
    data = extract_json(raw)
    highlights = []
    for h in data.get("highlights", []) or []:
        title = str(h.get("title", "")).strip()
        if not title:
            continue
        tag = h.get("tag")
        highlights.append({
            "title": title,
            "detail": str(h.get("detail", "")).strip(),
            "tag": tag if tag in _TAGS else "admin",
        })
    _cache = {
        "highlights": highlights[:8],
        "threads": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache


def invalidate_digest_cache() -> None:
    global _cache
    _cache = None
