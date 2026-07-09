"""Auto-organize — discover categories from the mail itself.

Takes everything still unfiled (project_id IS NULL, not sent), asks Claude to
propose stable, broad categories for the *relevant* recurring mail, files every
thread into an existing project / a new category / SKIP (junk → ignored).

Explicitly user-triggered (POST /organize). It re-files threads but never
re-drafts and never touches anything already assigned to a project, so manual
project assignments and the sync loop's idempotency are preserved.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.llm import DRAFT_MODEL, complete, extract_json
from db.models import Email, Project

log = logging.getLogger("adjutant.discover")

_BATCH = 120          # threads per model call
_MAX_NEW_CATEGORIES = 6

_SYSTEM = """You organize a researcher's mailbox. You get their existing projects \
and a list of unfiled email threads (one per line: id | sender | subject | snippet).

Tasks:
1. Invent NEW categories (at most {max_new} across the whole list) for recurring kinds \
of mail worth the user's attention that fit no existing project. Categories must be \
broad, stable buckets a human would create, e.g. "Work", "Clients", "Conferences & \
Events", "Personal & Friends"; never one-off or sender-specific.
2. Assign EVERY thread id to exactly one of: an existing project name, one of your new \
category names, or "SKIP".
   - "SKIP" = not worth attention: newsletters, marketing, promotions, job alerts, \
social-media notifications, receipts, automated alerts, mass mail.
   - Threads the user should see (personal mail, work mail, official/administrative \
matters) must NOT be SKIP — give them a category.

Respond with ONLY this JSON, no prose:
{{
  "new_categories": [{{"name": "...", "description": "<what belongs here, written as \
classification context for future emails>", "digest": <true if this category is \
newsletters/feeds/content to skim rather than personal or actionable mail>}}],
  "assignments": {{"<thread id>": "<project or category name, or SKIP>"}}
}}
Every input thread id must appear exactly once in "assignments"."""


def _compact(text: str, n: int) -> str:
    return " ".join((text or "").split())[:n]


def organize(session: Session) -> dict:
    # Only genuinely unfiled, non-junk threads. Ignored mail stays ignored —
    # re-considering it just resurrects newsletters into new categories.
    rows = session.scalars(
        select(Email).where(
            Email.project_id.is_(None), Email.status.notin_(("sent", "ignored"))
        )
    ).all()
    summary = {"considered": len(rows), "new_projects": [], "assigned": 0,
               "skipped": 0, "unresolved": 0}
    if not rows:
        return summary

    projects = {p.name: p for p in session.scalars(select(Project)).all()}

    for start in range(0, len(rows), _BATCH):
        batch = rows[start : start + _BATCH]
        existing_block = "\n".join(
            f'- "{p.name}": {_compact(p.description, 200)}' for p in projects.values()
        ) or "(none yet)"
        thread_block = "\n".join(
            f"{r.id} | {_compact(r.last_sender, 40)} | {_compact(r.subject, 80)} | {_compact(r.snippet, 90)}"
            for r in batch
        )
        raw = complete(
            DRAFT_MODEL,
            _SYSTEM.format(max_new=_MAX_NEW_CATEGORIES),
            f"EXISTING PROJECTS:\n{existing_block}\n\nUNFILED THREADS:\n{thread_block}",
            max_tokens=8000,
        )
        data = extract_json(raw)

        # create newly proposed categories (carried into later batches)
        for cat in data.get("new_categories", []) or []:
            name = str(cat.get("name", "")).strip()
            if not name or name in projects:
                continue
            if len(summary["new_projects"]) >= _MAX_NEW_CATEGORIES:
                break
            p = Project(
                name=name,
                description=str(cat.get("description", "")).strip(),
                auto=True,
                digest=bool(cat.get("digest", False)),
            )
            session.add(p)
            session.flush()
            projects[name] = p
            summary["new_projects"].append(name)

        by_id = {r.id: r for r in batch}
        assignments = data.get("assignments", {}) or {}
        for key, target in assignments.items():
            try:
                row = by_id[int(key)]
            except (ValueError, KeyError):
                continue
            target = str(target).strip()
            if target.upper() == "SKIP":
                row.status = "ignored"
                summary["skipped"] += 1
            elif target in projects:
                row.project_id = projects[target].id
                if row.status == "ignored":
                    row.status = "classified"  # rescued from the junk pile
                summary["assigned"] += 1
            else:
                summary["unresolved"] += 1
        # threads the model forgot stay unfiled — visible, never silently buried
        summary["unresolved"] += sum(
            1 for r in batch if str(r.id) not in {str(k) for k in assignments}
        )
        session.commit()

    return summary
