"""Project standings — "where does each project stand right now?"

One Claude call over each work project's recent threads produces a one-line
standing + concrete next step. This is the seed of the later progress-tracking
phase (which will persist these onto the projects table); for now they live in
a cache that invalidates whenever mail state changes.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.llm import DRAFT_MODEL, EMPHASIS_GUIDE, complete, extract_json
from db.models import Email, Project

_cache: dict | None = None

_SYSTEM = """You are the user's chief of staff. For each of their projects you get \
the description and the most recent email threads (status | sender | subject | snippet). \
Thread status meaning: drafted = reply waiting for the user's review; needs_reply = \
reply owed; sent = user replied; classified = informational.

Respond with ONLY this JSON, no prose:
{
  "<project id>": {
    "standing": "<ONE concrete sentence: where the project stands right now — name \
people, dates, decisions. Written like a status report, not a description.>",
    "next": "<short imperative next step for the user, or null if nothing is pending>"
  }
}
Only use the given project ids. If a project's threads show no real activity, \
standing = "No recent email activity." and next = null."""


def build_standings(session: Session, refresh: bool = False) -> dict:
    global _cache
    if _cache is not None and not refresh:
        return _cache

    projects = session.scalars(
        select(Project).where(Project.digest.is_(False)).order_by(Project.name)
    ).all()
    standings: dict[str, dict] = {}
    blocks: list[str] = []
    asked: set[int] = set()

    for p in projects:
        threads = session.scalars(
            select(Email)
            .where(Email.project_id == p.id, Email.status != "ignored")
            .order_by(Email.updated_at.desc())
            .limit(8)
        ).all()
        if not threads:
            standings[str(p.id)] = {"standing": "No email activity yet.", "next": None}
            continue
        asked.add(p.id)
        lines = "\n".join(
            f"  - {t.status} | {t.last_sender[:30]} | {t.subject[:70]} | "
            f"{' '.join((t.snippet or '').split())[:90]}"
            for t in threads
        )
        blocks.append(f'PROJECT id={p.id} "{p.name}": {p.description[:200]}\n{lines}')

    if asked:
        raw = complete(DRAFT_MODEL, _SYSTEM + "\n\n" + EMPHASIS_GUIDE, "\n\n".join(blocks), max_tokens=2000)
        data = extract_json(raw)
        for key, val in (data or {}).items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            if pid not in asked or not isinstance(val, dict):
                continue
            standings[str(pid)] = {
                "standing": str(val.get("standing", "")).strip() or "—",
                "next": (str(val.get("next")).strip() or None)
                if val.get("next") else None,
            }

    _cache = {
        "standings": standings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache


def invalidate_standing_cache() -> None:
    global _cache
    _cache = None
