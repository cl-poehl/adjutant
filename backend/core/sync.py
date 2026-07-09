"""Sync loop: pull recent threads → classify → label → draft replies.

Idempotent by design: a thread whose row has processed=True is never
re-classified or re-drafted. Callable on demand (POST /sync) or on an interval
(SYNC_INTERVAL_MINUTES). Per-thread failures are recorded and skipped without
marking the thread processed, so the next sync retries them.
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import draft as drafter
from core.classify import classify_thread
from db.models import Email, Project
from providers.base import EmailProvider

log = logging.getLogger("adjutant.sync")

SYNC_QUERY = os.getenv("SYNC_QUERY", "in:inbox newer_than:7d")
SYNC_MAX_THREADS = int(os.getenv("SYNC_MAX_THREADS", "25"))
# How many of the newest messages to map back to threads each pass. This is the
# reliable-recency path: it catches freshly-replied threads that the provider's
# thread-level ranking buries below the SYNC_MAX_THREADS window.
SYNC_MAX_MESSAGES = int(os.getenv("SYNC_MAX_MESSAGES", "400"))


def redraft_thread(session: Session, provider: EmailProvider, row: Email) -> str:
    """Force a fresh AI draft for one stored thread, regardless of how triage
    rated it. The escape hatch for threads the classifier filed as 'read' when
    they actually awaited a reply — drafting is otherwise gated on that call,
    and a processed thread is never revisited by the sync loop.

    Supersedes any existing provider draft so the mailbox doesn't accumulate
    duplicates. Returns the new draft body."""
    thread = provider.get_thread(row.provider_thread_id)
    project = session.get(Project, row.project_id) if row.project_id else None
    body = drafter.generate_draft(
        thread,
        project_name=project.name if project else None,
        project_description=project.description if project else None,
    )
    if row.draft_id:
        provider.delete_draft(row.draft_id)
    row.draft_body = body
    row.draft_id = provider.create_draft(thread, body)
    row.status = "drafted"
    row.processed = True
    last = thread.last_message
    row.last_seen_message_id = last.provider_message_id if last else None
    session.commit()
    return body


def run_sync(session: Session, provider: EmailProvider) -> dict:
    """One full pass. Returns a summary the dashboard can show."""
    summary = {"seen": 0, "skipped": 0, "classified": 0, "drafted": 0,
               "errors": [], "items": []}

    # Two independent selections, unioned (freshest first, de-duped):
    #  - newest messages → their threads: reliable recency, catches a recent
    #    reply on an otherwise-old thread the thread ranking would bury. The
    #    pairs also give each thread's newest message id, so we can tell
    #    'nothing new' from 'a fresh reply landed' without a fetch.
    #  - the thread-level window: unchanged coverage for anything the message
    #    scan didn't reach.
    recent_pairs = provider.list_recent_thread_messages(
        max_results=SYNC_MAX_MESSAGES, query=SYNC_QUERY
    )
    newest_by_thread = {tid: mid for tid, mid in recent_pairs if mid}
    window = provider.list_threads(max_results=SYNC_MAX_THREADS, query=SYNC_QUERY)
    thread_ids = list(dict.fromkeys([tid for tid, _ in recent_pairs] + window))
    summary["seen"] = len(thread_ids)

    projects = session.scalars(select(Project)).all()
    project_dicts = [{"name": p.name, "description": p.description} for p in projects]
    by_name = {p.name: p for p in projects}

    handled: set[str] = set()  # thread ids seen in the scan window this pass
    for tid in thread_ids:
        handled.add(tid)
        row = session.scalar(
            select(Email).where(
                Email.provider == provider.name, Email.provider_thread_id == tid
            )
        )
        # --- idempotency gate ---
        # A processed thread is normally left alone, but a NEW inbound message
        # (the other side replied, or I replied straight from Gmail) must re-open
        # it — INCLUDING threads I earlier filed as 'ignored', since one that was
        # just my own outbound inquiry can later get a real, reply-worthy answer.
        # 'sent' threads are owned by the follow-up radar below. To avoid a fetch
        # per parked thread, first cheap-skip using the newest message id the
        # recency scan already handed us: if it matches what we last triaged,
        # nothing changed.
        known_newest = newest_by_thread.get(tid)
        if row is not None and row.processed:
            if row.status == "sent":
                summary["skipped"] += 1
                continue
            if known_newest is not None and known_newest == row.last_seen_message_id:
                summary["skipped"] += 1
                continue

        try:
            thread = provider.get_thread(tid)
            last = thread.last_message
            last_id = last.provider_message_id if last else None
            # Keep the stored marker aligned with what the recency scan reports
            # for this thread (the newest inbox message), so a thread carrying a
            # draft as its literal last message doesn't get re-fetched forever.
            marker = known_newest or last_id

            # Processed thread with no new inbound message → genuinely nothing
            # to do. (A new message from me doesn't reopen it — I'm not awaiting
            # myself.) Re-open only when the latest message is inbound and one
            # we haven't triaged yet.
            if row is not None and row.processed:
                new_inbound = (
                    last is not None
                    and not last.is_from_me
                    and bool(last_id)
                    and last_id != row.last_seen_message_id
                )
                if not new_inbound:
                    if row.last_seen_message_id != marker:
                        row.last_seen_message_id = marker
                        session.commit()
                    summary["skipped"] += 1
                    continue
                # fresh inbound on a parked thread — triage + draft it again
                row.processed = False
                row.done = False
                row.awaiting_since = None

            if row is None:
                row = Email(provider=provider.name, provider_thread_id=tid)
                session.add(row)
            row.subject = thread.subject
            row.last_sender = thread.last_sender
            row.snippet = thread.snippet
            row.last_seen_message_id = marker

            # 1. classify + triage relevance
            result = classify_thread(thread, project_dicts)
            project = by_name.get(result.project_name) if result.project_name else None
            row.project_id = project.id if project else None
            row.urgency = result.urgency
            if result.relevance == "skip":
                # not worth attention — file away, never draft
                row.status = "ignored"
            else:
                row.status = "needs_reply" if result.needs_reply else "classified"
                summary["items"].append({
                    "urgency": result.urgency,
                    "needs_reply": result.needs_reply,
                    "subject": row.subject or "(no subject)",
                    "sender": row.last_sender or "",
                    "from_email": (last.sender_email if last else "") or "",
                })
            summary["classified"] += 1

            # 2. label in the mailbox so Gmail mirrors the dashboard
            if project and result.relevance != "skip":
                try:
                    provider.apply_label(tid, project.name)
                except Exception as exc:  # labeling is cosmetic — never fatal
                    log.warning("label failed for %s: %s", tid, exc)

            # 3. draft a reply when one is owed (a suggestion — send is manual)
            if result.relevance != "skip" and result.needs_reply:
                body = drafter.generate_draft(
                    thread,
                    project_name=project.name if project else None,
                    project_description=project.description if project else None,
                )
                # supersede any prior draft so a re-opened thread doesn't leave
                # a stale duplicate sitting in the mailbox
                if row.draft_id:
                    provider.delete_draft(row.draft_id)
                row.draft_body = body
                row.draft_id = provider.create_draft(thread, body)
                row.status = "drafted"
                summary["drafted"] += 1

            row.processed = True
            session.commit()
        except Exception as exc:
            session.rollback()
            log.exception("sync failed for thread %s", tid)
            summary["errors"].append({"thread_id": tid, "error": str(exc)})
            # processed stays False → retried on the next sync

    # Follow-up radar: re-check threads I'm waiting on — if they've replied,
    # clear the wait and flag it as needing my response again.
    summary["replies_in"] = 0
    awaiting = session.scalars(
        select(Email).where(Email.status == "sent", Email.awaiting_since.is_not(None))
    ).all()
    for row in awaiting:
        try:
            thread = provider.get_thread(row.provider_thread_id)
            last = thread.last_message
            if last is not None and not last.is_from_me:
                row.status = "needs_reply"
                row.last_sender = thread.last_sender
                row.snippet = thread.snippet
                row.awaiting_since = None
                row.processed = False  # eligible for drafting next pass
                summary["replies_in"] += 1
                session.commit()
        except Exception:
            session.rollback()
            log.exception("awaiting re-check failed for %s", row.provider_thread_id)

    # Stale-draft radar: the scan window above only covers the newest
    # SYNC_MAX_THREADS threads, but the action queue can hold threads far older
    # than that (a busy inbox has thousands). Re-check every thread I still owe
    # a reply on — drafted or needs_reply — that the window missed. If a new
    # inbound message has landed, its draft is stale (or absent); re-draft it so
    # the queue never silently rots regardless of how deep the thread has sunk.
    summary["restaled"] = 0
    open_rows = session.scalars(
        select(Email).where(
            Email.provider == provider.name,
            Email.status.in_(("drafted", "needs_reply")),
            Email.done.is_(False),
        )
    ).all()
    for row in open_rows:
        if row.provider_thread_id in handled:
            continue  # already re-evaluated in the scan-window loop
        try:
            thread = provider.get_thread(row.provider_thread_id)
            last = thread.last_message
            last_id = last.provider_message_id if last else None
            new_inbound = (
                last is not None
                and not last.is_from_me
                and bool(last_id)
                and last_id != row.last_seen_message_id
            )
            if not new_inbound:
                continue
            redraft_thread(session, provider, row)
            summary["restaled"] += 1
        except Exception:
            session.rollback()
            log.exception("stale-draft radar failed for %s", row.provider_thread_id)

    return summary
