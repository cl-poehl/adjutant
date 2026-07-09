"""Agenda — the command-deck brain.

One Claude call over the current mail state produces a ranked daily agenda:
urgent items (deadlines, blocking people), the reply queue, and FYIs.
Cached in-process; regenerated on demand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.llm import DRAFT_MODEL, complete, extract_json
from db.models import Email, Project

_SYSTEM = """You are the user's chief of staff. From their current email state you \
produce a focused agenda that answers: "what should I do right now?"

Input: their projects, then threads as lines: id | status | urgency | project | sender | subject | snippet.
Status meaning: drafted = a reply draft is ready for their review; needs_reply = a reply \
is owed but not yet drafted; classified = informational. Threads pre-scored urgency=high \
are strong candidates for "urgent" — verify against the content.

Respond with ONLY this JSON, no prose:
{
  "headline": "<one calm sentence sizing up the day — what matters most right now>",
  "urgent": [{"id": <thread id>, "title": "<short imperative, e.g. 'Confirm Monday meeting with Dr. Heller'>", "why": "<one short clause>", "deadline": "<extracted date/time or null>"}],
  "reply_queue": [{"id": <thread id>, "title": "<short imperative>", "why": "<one short clause>"}],
  "fyi": [{"id": <thread id>, "title": "<short noun phrase>", "note": "<one short clause>"}],
  "deadlines": [{"id": <thread id>, "title": "<what is due>", "date": "<ISO date YYYY-MM-DD if derivable, else the raw date phrase>"}]
}

Rules:
- "urgent": ONLY items with a real deadline, time-sensitivity, or a person blocked \
waiting on the user. Extract concrete deadlines from the text when present. Empty list is fine.
- Account, billing, subscription, security-alert, permissions, data-exposure, and \
service-shutdown notices are NEVER urgent and never in reply_queue — they go in "fyi" \
(or are omitted). Urgent is for work and people, not account housekeeping.
- "reply_queue": every thread with status drafted or needs_reply that isn't in urgent, \
ranked by importance to their projects. An urgent thread appears in urgent only.
- "fyi": at most 5 genuinely useful informational items. Skip routine noise.
- "deadlines": EVERY thread that mentions a concrete future date/deadline (submissions, \
meetings, payments, expirations), across all threads — even if also listed elsewhere. \
Prefer an ISO date. Empty list if none.
- Use ONLY the provided thread ids. Never invent ids or facts.
- EMPHASIS: in the headline and the "why"/"note" text, guide the eye by wrapping the \
single most decision-driving phrase in ==double equals== (renders highlighted) and at \
most one or two secondary key terms in **double asterisks** (renders bold). Mark what \
truly carries weight — the real reason this matters right now — not categories, dates, \
or numbers by reflex. Be sparing; many items need no marks, and never mark whole \
sentences. Keep the marks inside the JSON string values."""

_cache: dict | None = None


def build_agenda(session: Session, refresh: bool = False, days: int = 10) -> dict:
    global _cache
    if _cache is not None and not refresh:
        return _cache

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    not_snoozed = (Email.snoozed_until.is_(None)) | (Email.snoozed_until <= now)
    in_play = not_snoozed & Email.done.is_(False)
    actionable = session.scalars(
        select(Email).where(Email.status.in_(("needs_reply", "drafted")), in_play)
    ).all()
    digest_ids = select(Project.id).where(Project.digest)
    recent_info = session.scalars(
        select(Email)
        .where(
            Email.status == "classified",
            Email.updated_at >= cutoff,
            Email.project_id.notin_(digest_ids) | Email.project_id.is_(None),
            in_play,
        )
        .order_by(Email.updated_at.desc())
        .limit(60)
    ).all()
    rows = list({e.id: e for e in [*actionable, *recent_info]}.values())
    if not rows:
        _cache = {
            "headline": "Inbox clear — nothing waiting on you.",
            "urgent": [], "reply_queue": [], "fyi": [], "deadlines": [],
            "waiting": _compute_waiting(session),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return _cache

    projects = {p.id: p for p in session.scalars(select(Project)).all()}
    plist = "\n".join(
        f"- {p.name}: {p.description[:150]}" for p in projects.values() if not p.digest
    )
    listing = "\n".join(
        f"{e.id} | {e.status} | {e.urgency or 'normal'}"
        f" | {projects[e.project_id].name if e.project_id in projects else '-'}"
        f" | {e.last_sender[:35]} | {e.subject[:80]} | {' '.join((e.snippet or '').split())[:100]}"
        for e in rows
    )
    raw = complete(
        DRAFT_MODEL,
        _SYSTEM,
        f"PROJECTS:\n{plist}\n\nTHREADS:\n{listing}",
        max_tokens=3000,
    )
    data = extract_json(raw)

    valid = {e.id for e in rows}

    def clean(items: list, fields: tuple[str, ...]) -> list[dict]:
        out = []
        for it in items or []:
            try:
                tid = int(it.get("id"))
            except (TypeError, ValueError):
                continue
            if tid not in valid:
                continue
            entry = {"id": tid}
            for f in fields:
                entry[f] = it.get(f) or None
            out.append(entry)
        return out

    # follow-up radar: threads I've sent and am waiting on (computed, no LLM)
    waiting = _compute_waiting(session)

    _cache = {
        "headline": str(data.get("headline", "")) or "Here's where things stand.",
        "urgent": clean(data.get("urgent", []), ("title", "why", "deadline")),
        "reply_queue": clean(data.get("reply_queue", []), ("title", "why")),
        "fyi": clean(data.get("fyi", []), ("title", "note")),
        "deadlines": clean(data.get("deadlines", []), ("title", "date")),
        "waiting": waiting,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _cache


def invalidate_cache() -> None:
    global _cache
    _cache = None


def _compute_waiting(session: Session) -> list[dict]:
    """The follow-up 'waiting on' list — a pure DB read, no LLM."""
    now = datetime.now(timezone.utc)
    waiting: list[dict] = []
    rows = session.scalars(
        select(Email).where(Email.status == "sent", Email.awaiting_since.is_not(None))
    ).all()
    for e in rows:
        since = e.awaiting_since
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        days = (now - since).days if since else 0
        waiting.append({
            "id": e.id,
            "title": e.subject or "(no subject)",
            "sender": e.last_sender,
            "days": days,
        })
    waiting.sort(key=lambda w: -w["days"])
    return waiting


def drop_from_cache(thread_id: int) -> None:
    """Surgically remove one thread from the cached agenda — no LLM regen.

    When a single thread is triaged (sent / snoozed / done / ignored) the rest
    of the agenda is unaffected, so there's no need to pay for a full rebuild on
    the next visit. The frontend already drops the item optimistically; this
    keeps the server cache in step so the next load stays warm and free."""
    global _cache
    if _cache is None:
        return
    for key in ("urgent", "reply_queue", "fyi", "deadlines", "waiting"):
        items = _cache.get(key)
        if items:
            _cache[key] = [it for it in items if it.get("id") != thread_id]


def update_waiting(session: Session) -> None:
    """Refresh only the (LLM-free) 'waiting on' list in the cache — e.g. after a
    send, which starts a new follow-up timer — without rebuilding the agenda."""
    global _cache
    if _cache is not None:
        _cache["waiting"] = _compute_waiting(session)
