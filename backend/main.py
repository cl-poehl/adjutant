"""Adjutant API.

Endpoints are deliberately synchronous (`def`): FastAPI runs them in a thread
pool, which plays cleanly with the synchronous Gmail + Anthropic clients for a
single-user v1.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import founder, notify, settings, style
from core.agenda import (
    build_agenda,
    drop_from_cache,
    invalidate_cache,
    update_waiting,
)
from core.digest import build_briefing, invalidate_digest_cache
from core.events import scout_events
from core.ideas import generate_ideas
from core.jobs import scout_jobs
from core.research import build_daily_brief, run_nightly, run_research, seed_default_topics
from core.secondbrain import ask as brain_ask
from core.standing import build_standings, invalidate_standing_cache
from core.discover import organize
from core.sync import redraft_thread, run_sync
from db.models import (
    Email,
    Event,
    Habit,
    HabitLog,
    Idea,
    Job,
    JournalEntry,
    Note,
    Project,
    ResearchBrief,
    ResearchFinding,
    ResearchTopic,
)
from db.session import SessionLocal, get_session, init_db
from providers import get_provider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("adjutant")

_sync_lock = threading.Lock()


def _sync_changed(summary: dict) -> bool:
    """True if a sync altered anything the deck (agenda/digest/standing) reflects
    — new classifications, fresh drafts, or follow-up replies arriving. A sync
    that only re-sees already-processed mail leaves the caches valid, so we don't
    burn tokens rebuilding them."""
    return bool(
        summary.get("classified")
        or summary.get("drafted")
        or summary.get("replies_in")
        or summary.get("restaled")
    )


_last_idea_date: str | None = None


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Automation toggles: DB setting (set from the dashboard) is the source of truth;
# the env var is only the default when the user has never flipped the switch.
AUTOMATION_KEYS = {
    "ideas": ("automation.ideas", "IDEAS_DAILY"),
    "jobs": ("automation.jobs", "JOBS_DAILY"),
    "research": ("automation.research", "RESEARCH_DAILY"),
}


def _automation_on(session: Session, which: str) -> bool:
    key, env = AUTOMATION_KEYS[which]
    return settings.get_bool(session, key, _env_bool(env))


def _maybe_daily_ideas(session: Session) -> None:
    """Generate the day's startup ideas once per calendar day (if enabled)."""
    global _last_idea_date
    if not _automation_on(session, "ideas"):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    already = session.scalar(select(Idea).where(Idea.created_date == today))
    if _last_idea_date == today or already is not None:
        _last_idea_date = today
        return
    try:
        result = generate_ideas(session, n=int(os.getenv("IDEAS_PER_DAY", "5")))
        _last_idea_date = today
        log.info("daily ideas: %s", result)
    except Exception:
        log.exception("daily idea generation failed")


_last_job_date: str | None = None


def _maybe_daily_jobs(session: Session) -> None:
    """Scout jobs once per calendar day (if enabled)."""
    global _last_job_date
    if not _automation_on(session, "jobs"):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    already = session.scalar(select(Job).where(Job.found_date == today))
    if _last_job_date == today or already is not None:
        _last_job_date = today
        return
    try:
        result = scout_jobs(session, n=int(os.getenv("JOBS_PER_DAY", "6")))
        _last_job_date = today
        log.info("daily jobs: %s", result)
    except Exception:
        log.exception("daily job scout failed")


def _maybe_daily_research(session: Session) -> None:
    """Build + push the morning brief once per day, at/after the configured local
    send hour (RESEARCH_BRIEF_HOUR, default 07:00 in BRIEF_TZ). 'Already done
    today' is keyed on the stored brief row, so a restart never double-fires."""
    if not _automation_on(session, "research"):
        return
    try:
        from zoneinfo import ZoneInfo
        now_local = datetime.now(ZoneInfo(os.getenv("BRIEF_TZ", "UTC")))
    except Exception:
        now_local = datetime.now(timezone.utc)  # fallback if tz db unavailable
    if now_local.hour < int(os.getenv("RESEARCH_BRIEF_HOUR", "7")):
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if session.scalar(select(ResearchBrief).where(ResearchBrief.day == today)) is not None:
        return  # already briefed today (persisted across restarts)
    try:
        result = run_nightly(session)  # seed -> run topics -> brief + push
        log.info("daily research brief: day=%s pushed=%s", result.get("day"), result.get("pushed"))
    except Exception:
        log.exception("daily research run failed")


def _interval_loop(minutes: int, stop: threading.Event) -> None:
    """Optional background poll (SYNC_INTERVAL_MINUTES > 0). Upgradeable to
    Gmail push/Pub-Sub later without touching anything else."""
    while not stop.wait(minutes * 60):
        try:
            with _sync_lock, SessionLocal() as session:
                summary = run_sync(session, get_provider())
                # Only spend tokens rebuilding the deck if mail actually changed.
                if _sync_changed(summary):
                    invalidate_cache()
                    invalidate_digest_cache()
                    invalidate_standing_cache()
                log.info("scheduled sync: %s", summary)
            try:
                notify.notify_sync_highlights(summary, summary.get("items", []))
            except Exception:
                log.exception("sync notification failed")
            with SessionLocal() as session:
                _maybe_daily_ideas(session)
            with SessionLocal() as session:
                _maybe_daily_jobs(session)
            with SessionLocal() as session:
                _maybe_daily_research(session)
        except Exception:
            log.exception("scheduled sync failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        with SessionLocal() as session:
            seed_default_topics(session)  # default daily research topics, once
    except Exception:
        log.exception("seeding default research topics failed")
    stop = threading.Event()
    minutes = int(os.getenv("SYNC_INTERVAL_MINUTES", "0"))
    if minutes > 0:
        threading.Thread(
            target=_interval_loop, args=(minutes, stop), daemon=True
        ).start()
        log.info("background sync every %d min", minutes)
    yield
    stop.set()


app = FastAPI(title="Adjutant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ schemas

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    auto: bool = False
    digest: bool = False
    created_at: datetime
    thread_count: int = 0
    needs_attention: int = 0


class ThreadOut(BaseModel):
    id: int
    provider: str
    provider_thread_id: str
    project_id: int | None
    subject: str
    last_sender: str
    snippet: str
    status: str
    urgency: str | None = None
    has_draft: bool
    updated_at: datetime


class MessageOut(BaseModel):
    sender_name: str
    sender_email: str
    date: datetime | None
    body_text: str
    is_from_me: bool


class ThreadDetailOut(BaseModel):
    thread: ThreadOut
    messages: list[MessageOut]
    draft_body: str | None
    reply_to: str  # who the reply will go to


class DraftIn(BaseModel):
    body: str


class SendIn(BaseModel):
    body: str | None = None  # optional final override; falls back to saved draft
    to: str | None = None  # optional recipient override (e.g. forwarded threads)


def _thread_out(e: Email) -> ThreadOut:
    return ThreadOut(
        id=e.id,
        provider=e.provider,
        provider_thread_id=e.provider_thread_id,
        project_id=e.project_id,
        subject=e.subject or "(no subject)",
        last_sender=e.last_sender,
        snippet=e.snippet,
        status=e.status,
        urgency=e.urgency,
        has_draft=bool(e.draft_body),
        updated_at=e.updated_at,
    )


# ----------------------------------------------------------------- projects

@app.get("/projects", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)):
    out = []
    for p in session.scalars(select(Project).order_by(Project.name)):
        emails = p.emails
        out.append(
            ProjectOut(
                id=p.id,
                name=p.name,
                description=p.description,
                auto=p.auto,
                digest=p.digest,
                created_at=p.created_at,
                thread_count=len(emails),
                needs_attention=sum(1 for e in emails if e.status in ("needs_reply", "drafted")),
            )
        )
    return out


@app.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectIn, session: Session = Depends(get_session)):
    exists = session.scalar(select(Project).where(Project.name == payload.name))
    if exists:
        raise HTTPException(409, f"Project '{payload.name}' already exists")
    p = Project(name=payload.name.strip(), description=payload.description.strip())
    session.add(p)
    session.commit()
    return ProjectOut(
        id=p.id, name=p.name, description=p.description, created_at=p.created_at
    )


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    junk_threads: bool = False,
    session: Session = Depends(get_session),
):
    """Remove a project/category. Its threads go back to unclassified —
    or straight to ignored with junk_threads=true (for newsletter buckets)."""
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    moved = 0
    for e in session.scalars(select(Email).where(Email.project_id == project_id)):
        e.project_id = None
        if junk_threads and e.status not in ("sent", "drafted", "needs_reply"):
            e.status = "ignored"
        moved += 1
    session.delete(p)
    session.commit()
    return {"deleted": p.name, "threads_affected": moved, "junked": junk_threads}


# ------------------------------------------------------------------ threads

@app.get("/threads", response_model=list[ThreadOut])
def list_threads(
    project_id: int | None = None,
    unclassified: bool = False,
    digest: bool = False,
    status: str | None = None,
    session: Session = Depends(get_session),
):
    q = select(Email).order_by(Email.updated_at.desc())
    if unclassified:
        q = q.where(Email.project_id.is_(None))
    elif digest:
        q = q.where(
            Email.project_id.in_(select(Project.id).where(Project.digest))
        )
    elif project_id is not None:
        q = q.where(Email.project_id == project_id)
    if status:
        q = q.where(Email.status == status)
    return [_thread_out(e) for e in session.scalars(q)]


@app.get("/threads/{thread_id}", response_model=ThreadDetailOut)
def get_thread(thread_id: int, session: Session = Depends(get_session)):
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    try:
        provider = get_provider(e.provider)
        thread = provider.get_thread(e.provider_thread_id)
        messages = [
            MessageOut(
                sender_name=m.sender_name,
                sender_email=m.sender_email,
                date=m.date,
                body_text=m.body_text,
                is_from_me=m.is_from_me,
            )
            for m in thread.messages
        ]
        reply_to = provider.suggested_recipient(thread)
    except Exception:
        # Live message bodies couldn't be fetched (provider unavailable, or a
        # seeded demo thread with no real provider thread). Reconstruct a minimal
        # view from stored fields so the draft stays reviewable either way.
        log.warning("thread %s: live fetch failed, serving stored fallback", thread_id)
        messages = (
            [MessageOut(
                sender_name=e.last_sender or "",
                sender_email="",
                date=e.updated_at,
                body_text=e.snippet or "",
                is_from_me=False,
            )]
            if (e.snippet or e.last_sender)
            else []
        )
        reply_to = e.last_sender or ""
    return ThreadDetailOut(
        thread=_thread_out(e),
        messages=messages,
        draft_body=e.draft_body,
        reply_to=reply_to,
    )


@app.put("/threads/{thread_id}/draft", response_model=ThreadOut)
def save_draft(thread_id: int, payload: DraftIn, session: Session = Depends(get_session)):
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    if e.status == "sent":
        raise HTTPException(409, "Thread already sent")
    e.draft_body = payload.body
    if e.status in ("new", "classified", "needs_reply"):
        e.status = "drafted"
    session.commit()
    return _thread_out(e)


@app.post("/threads/{thread_id}/redraft", response_model=ThreadOut)
def redraft_thread_endpoint(thread_id: int, session: Session = Depends(get_session)):
    """Force a fresh AI draft for a thread — the recovery path when triage filed
    it as 'read' (so sync never drafted it) or when the existing draft is no
    longer wanted. Generates only; sending stays a separate, manual step."""
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    if e.status == "sent":
        raise HTTPException(409, "Thread already sent")
    body = redraft_thread(session, get_provider(e.provider), e)
    if not body.strip():
        raise HTTPException(502, "The drafter returned an empty reply")
    invalidate_cache()  # a new draft changes the agenda's reply queue
    return _thread_out(e)


@app.post("/threads/{thread_id}/send", response_model=ThreadOut)
def send_thread(thread_id: int, payload: SendIn, session: Session = Depends(get_session)):
    """THE only send path in the system. Triggered exclusively by the explicit
    Send confirmation in the dashboard. There is no scheduled or rules-based
    sending anywhere, by design."""
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    if e.status == "sent":
        raise HTTPException(409, "Thread already sent")
    body = (payload.body if payload.body is not None else e.draft_body) or ""
    if not body.strip():
        raise HTTPException(400, "Draft body is empty — nothing to send")

    provider = get_provider(e.provider)
    thread = provider.get_thread(e.provider_thread_id)
    provider.send_message(thread, body, stale_draft_id=e.draft_id, to=payload.to)

    e.draft_body = body
    e.draft_id = None
    e.status = "sent"
    e.awaiting_since = datetime.now(timezone.utc)  # follow-up radar starts now
    session.commit()

    # Keep the agenda cache warm: drop this thread from the action lists and
    # refresh the (LLM-free) 'waiting on' list rather than rebuilding the deck.
    drop_from_cache(thread_id)
    update_waiting(session)
    invalidate_standing_cache()  # a sent reply can shift a project's standing
    return _thread_out(e)


class SnoozeIn(BaseModel):
    hours: int = Field(default=16, ge=1, le=24 * 14)


@app.post("/threads/{thread_id}/snooze", response_model=ThreadOut)
def snooze_thread(
    thread_id: int, payload: SnoozeIn, session: Session = Depends(get_session)
):
    """'Not today' — hide the thread from the agenda until the snooze lapses
    (default: resurfaces tomorrow). Nothing else about the thread changes."""
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    e.snoozed_until = datetime.now(timezone.utc) + timedelta(hours=payload.hours)
    session.commit()
    drop_from_cache(thread_id)  # leaves the rest of the agenda cache intact
    return _thread_out(e)


@app.post("/threads/{thread_id}/done", response_model=ThreadOut)
def complete_thread(thread_id: int, session: Session = Depends(get_session)):
    """Tick an agenda item off as completed. The thread stays visible in its
    project but stops counting as something waiting on the user."""
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    e.done = True
    if e.status in ("needs_reply", "drafted"):
        e.status = "classified"
    session.commit()
    drop_from_cache(thread_id)
    invalidate_standing_cache()  # completing work can change a project's standing
    return _thread_out(e)


@app.post("/threads/{thread_id}/ignore", response_model=ThreadOut)
def ignore_thread(thread_id: int, session: Session = Depends(get_session)):
    e = session.get(Email, thread_id)
    if not e:
        raise HTTPException(404, "Thread not found")
    if e.status == "sent":
        raise HTTPException(409, "Thread already sent")
    e.status = "ignored"
    session.commit()
    drop_from_cache(thread_id)
    return _thread_out(e)


# --------------------------------------------------------------- sync/style

@app.post("/sync")
def sync_now(session: Session = Depends(get_session)):
    if not _sync_lock.acquire(blocking=False):
        raise HTTPException(409, "A sync is already running")
    try:
        summary = run_sync(session, get_provider())
        if _sync_changed(summary):
            invalidate_cache()
            invalidate_digest_cache()
            invalidate_standing_cache()
        try:
            notify.notify_sync_highlights(summary, summary.get("items", []))
        except Exception:
            log.exception("sync notification failed")
        return summary
    finally:
        _sync_lock.release()


@app.post("/organize")
def organize_now(session: Session = Depends(get_session)):
    """Auto-organize: discover categories from unfiled mail, file every thread,
    junk what isn't worth attention. Never re-drafts, never touches threads
    already assigned to a project."""
    result = organize(session)
    invalidate_cache()
    invalidate_digest_cache()
    invalidate_standing_cache()
    return result


@app.post("/agenda")
def agenda(refresh: bool = False, session: Session = Depends(get_session)):
    """The command-deck agenda: urgent items, ranked reply queue, FYIs.
    Cached until a sync/send/organize changes the mail state (or refresh=true)."""
    return build_agenda(session, refresh=refresh)


# ----------------------------------------------------------------- ideas

class IdeaOut(BaseModel):
    id: int
    created_date: str
    title: str
    pitch: str
    domain: str
    score: int
    why_now: str
    why_you: str
    first_step: str
    market: str
    signal: str
    status: str
    created_at: datetime


def _idea_out(i: Idea) -> IdeaOut:
    return IdeaOut(
        id=i.id, created_date=i.created_date, title=i.title, pitch=i.pitch,
        domain=i.domain, score=i.score, why_now=i.why_now, why_you=i.why_you,
        first_step=i.first_step, market=i.market, signal=i.signal,
        status=i.status, created_at=i.created_at,
    )


_ideas_lock = threading.Lock()


@app.get("/ideas", response_model=list[IdeaOut])
def list_ideas(
    status: str | None = None,
    include_dismissed: bool = False,
    session: Session = Depends(get_session),
):
    q = select(Idea).order_by(Idea.created_at.desc())
    if status:
        q = q.where(Idea.status == status)
    elif not include_dismissed:
        q = q.where(Idea.status != "dismissed")
    return [_idea_out(i) for i in session.scalars(q)]


@app.post("/ideas/generate")
def ideas_generate(
    n: int = 6,
    use_web: bool = True,
    focus: str = "balanced",
    session: Session = Depends(get_session),
):
    """Generate today's startup ideas from the AI-newsletter feed + live web
    search, grounded in the founder profile. `focus` is one of: balanced,
    core, adjacent, broad, wildcard."""
    if not _ideas_lock.acquire(blocking=False):
        raise HTTPException(409, "Idea generation already running")
    try:
        result = generate_ideas(session, n=n, use_web=use_web, focus=focus)
        result["ideas"] = [
            _idea_out(i).model_dump(mode="json")
            for i in session.scalars(
                select(Idea).where(Idea.id.in_(result["ids"]))
            )
        ]
        return result
    finally:
        _ideas_lock.release()


@app.post("/ideas/{idea_id}/save", response_model=IdeaOut)
def save_idea(idea_id: int, session: Session = Depends(get_session)):
    i = session.get(Idea, idea_id)
    if not i:
        raise HTTPException(404, "Idea not found")
    i.status = "saved"
    session.commit()
    return _idea_out(i)


@app.post("/ideas/{idea_id}/dismiss", response_model=IdeaOut)
def dismiss_idea(idea_id: int, session: Session = Depends(get_session)):
    i = session.get(Idea, idea_id)
    if not i:
        raise HTTPException(404, "Idea not found")
    i.status = "dismissed"
    session.commit()
    return _idea_out(i)


# ------------------------------------------------------------------ jobs

class JobOut(BaseModel):
    id: int
    found_date: str
    title: str
    company: str
    location: str
    comp: str
    url: str
    fit_score: int
    trajectory: int
    why_fit: str
    why_step_up: str
    readiness: str
    watch_outs: str
    source: str
    status: str
    created_at: datetime


def _job_out(j: Job) -> JobOut:
    return JobOut(
        id=j.id, found_date=j.found_date, title=j.title, company=j.company,
        location=j.location, comp=j.comp, url=j.url, fit_score=j.fit_score,
        trajectory=j.trajectory, why_fit=j.why_fit, why_step_up=j.why_step_up,
        readiness=j.readiness, watch_outs=j.watch_outs, source=j.source,
        status=j.status, created_at=j.created_at,
    )


_jobs_lock = threading.Lock()


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(
    include_dismissed: bool = False, session: Session = Depends(get_session)
):
    q = select(Job).order_by(
        (Job.fit_score + Job.trajectory).desc(), Job.created_at.desc()
    )
    if not include_dismissed:
        q = q.where(Job.status != "dismissed")
    return [_job_out(j) for j in session.scalars(q)]


@app.post("/jobs/scout")
def jobs_scout(n: int = 8, use_web: bool = True, session: Session = Depends(get_session)):
    """Scout current roles that fit the founder profile and are a real career
    step-up (high comp / trajectory). Web search + profile-grounded ranking."""
    if not _jobs_lock.acquire(blocking=False):
        raise HTTPException(409, "Job scouting already running")
    try:
        result = scout_jobs(session, n=n, use_web=use_web)
        result["jobs"] = [
            _job_out(j).model_dump(mode="json")
            for j in session.scalars(select(Job).where(Job.id.in_(result["ids"])))
        ]
        return result
    finally:
        _jobs_lock.release()


@app.post("/jobs/{job_id}/save", response_model=JobOut)
def save_job(job_id: int, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    j.status = "saved"
    session.commit()
    return _job_out(j)


@app.post("/jobs/{job_id}/dismiss", response_model=JobOut)
def dismiss_job(job_id: int, session: Session = Depends(get_session)):
    j = session.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    j.status = "dismissed"
    session.commit()
    return _job_out(j)


# ------------------------------------------------------------------ events

class EventOut(BaseModel):
    id: int
    found_date: str
    city: str
    title: str
    category: str
    venue: str
    when: str
    deadline: str
    price: str
    url: str
    fit_score: int
    why_fit: str
    description: str
    source: str
    status: str
    created_at: datetime


def _event_out(e: Event) -> EventOut:
    return EventOut(
        id=e.id, found_date=e.found_date, city=e.city, title=e.title,
        category=e.category, venue=e.venue, when=e.when, deadline=e.deadline,
        price=e.price, url=e.url, fit_score=e.fit_score, why_fit=e.why_fit,
        description=e.description, source=e.source, status=e.status,
        created_at=e.created_at,
    )


_events_lock = threading.Lock()


@app.get("/events", response_model=list[EventOut])
def list_events(
    city: str | None = None,
    include_dismissed: bool = False,
    session: Session = Depends(get_session),
):
    q = select(Event).order_by(Event.fit_score.desc(), Event.created_at.desc())
    if city:
        q = q.where(Event.city == city)
    if not include_dismissed:
        q = q.where(Event.status != "dismissed")
    return [_event_out(e) for e in session.scalars(q)]


@app.post("/events/scout")
def events_scout(
    city: str = "",
    n: int = 10,
    use_web: bool = True,
    session: Session = Depends(get_session),
):
    """Scout real, upcoming events in `city` that fit the user's personal and
    professional interests. Live web search + interest-grounded ranking."""
    if not _events_lock.acquire(blocking=False):
        raise HTTPException(409, "Event scouting already running")
    try:
        result = scout_events(session, city=city, n=n, use_web=use_web)
        result["events"] = [
            _event_out(e).model_dump(mode="json")
            for e in session.scalars(select(Event).where(Event.id.in_(result["ids"])))
        ]
        return result
    finally:
        _events_lock.release()


@app.post("/events/{event_id}/save", response_model=EventOut)
def save_event(event_id: int, session: Session = Depends(get_session)):
    e = session.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    e.status = "saved"
    session.commit()
    return _event_out(e)


@app.post("/events/{event_id}/dismiss", response_model=EventOut)
def dismiss_event(event_id: int, session: Session = Depends(get_session)):
    e = session.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    e.status = "dismissed"
    session.commit()
    return _event_out(e)


# ------------------------------------------------------------------ research

class FindingOut(BaseModel):
    id: int
    title: str
    detail: str
    why_matters: str
    url: str
    source: str
    importance: int
    status: str
    run_date: str


class TopicOut(BaseModel):
    id: int
    query: str
    track: str
    cadence: str
    status: str
    last_summary: str
    last_error: str
    last_run_at: datetime | None
    findings: list[FindingOut]


def _finding_out(f: ResearchFinding) -> FindingOut:
    return FindingOut(
        id=f.id, title=f.title, detail=f.detail, why_matters=f.why_matters,
        url=f.url, source=f.source, importance=f.importance, status=f.status,
        run_date=f.run_date,
    )


def _topic_out(t: ResearchTopic) -> TopicOut:
    findings = [
        _finding_out(f)
        for f in sorted(t.findings, key=lambda x: (-x.importance, -x.id))
        if f.status != "dismissed"
    ]
    return TopicOut(
        id=t.id, query=t.query, track=t.track, cadence=t.cadence, status=t.status,
        last_summary=t.last_summary, last_error=t.last_error,
        last_run_at=t.last_run_at, findings=findings,
    )


_research_lock = threading.Lock()


@app.get("/research", response_model=list[TopicOut])
def list_research(session: Session = Depends(get_session)):
    topics = session.scalars(
        select(ResearchTopic).where(ResearchTopic.archived.is_(False))
        .order_by(ResearchTopic.created_at.desc())
    ).all()
    return [_topic_out(t) for t in topics]


# brief routes are declared BEFORE the /research/{topic_id} routes so the static
# "brief" path isn't captured as a topic id.
class BriefOut(BaseModel):
    day: str
    for_you: str
    ventures: str


@app.get("/research/brief")
def get_brief(session: Session = Depends(get_session)):
    """The most recent daily morning brief (null if none generated yet)."""
    b = session.scalar(select(ResearchBrief).order_by(ResearchBrief.day.desc()))
    if not b:
        return None
    return BriefOut(day=b.day, for_you=b.for_you, ventures=b.ventures)


@app.post("/research/brief/run")
def run_brief(session: Session = Depends(get_session)):
    """Generate today's brief now: run all due daily topics, synthesize, push.
    Long-running (live web search across topics)."""
    if not _research_lock.acquire(blocking=False):
        raise HTTPException(409, "A research run is already in progress")
    try:
        return run_nightly(session)
    finally:
        _research_lock.release()


class TopicIn(BaseModel):
    query: str = Field(min_length=3, max_length=400)
    cadence: str = Field(default="once")
    track: str = Field(default="you")
    run_now: bool = True


@app.post("/research/topics", response_model=TopicOut, status_code=201)
def add_topic(payload: TopicIn, session: Session = Depends(get_session)):
    cadence = payload.cadence if payload.cadence in ("once", "daily") else "once"
    track = payload.track if payload.track in ("you", "venture") else "you"
    topic = ResearchTopic(query=payload.query.strip(), track=track, cadence=cadence, status="queued")
    session.add(topic)
    session.commit()
    if payload.run_now:
        if not _research_lock.acquire(blocking=False):
            raise HTTPException(409, "A research run is already in progress")
        try:
            run_research(session, topic)
        finally:
            _research_lock.release()
    return _topic_out(topic)


@app.post("/research/{topic_id}/run", response_model=TopicOut)
def run_topic(topic_id: int, session: Session = Depends(get_session)):
    topic = session.get(ResearchTopic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    if not _research_lock.acquire(blocking=False):
        raise HTTPException(409, "A research run is already in progress")
    try:
        run_research(session, topic)
    finally:
        _research_lock.release()
    return _topic_out(topic)


@app.post("/research/{topic_id}/archive", response_model=TopicOut)
def archive_topic(topic_id: int, session: Session = Depends(get_session)):
    topic = session.get(ResearchTopic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    topic.archived = True
    session.commit()
    return _topic_out(topic)


@app.delete("/research/{topic_id}")
def delete_topic(topic_id: int, session: Session = Depends(get_session)):
    topic = session.get(ResearchTopic, topic_id)
    if topic:
        session.delete(topic)
        session.commit()
    return {"deleted": topic_id}


@app.post("/research/findings/{finding_id}/save", response_model=FindingOut)
def save_finding(finding_id: int, session: Session = Depends(get_session)):
    f = session.get(ResearchFinding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    f.status = "saved"
    session.commit()
    return _finding_out(f)


@app.post("/research/findings/{finding_id}/dismiss", response_model=FindingOut)
def dismiss_finding(finding_id: int, session: Session = Depends(get_session)):
    f = session.get(ResearchFinding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    f.status = "dismissed"
    session.commit()
    return _finding_out(f)


# ------------------------------------------------------------------ habits

class HabitOut(BaseModel):
    id: int
    name: str
    emoji: str
    streak: int
    days: list[str]  # completed days within the requested window (YYYY-MM-DD)


class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    emoji: str = Field(default="", max_length=8)


def _streak(done: set[str], today: date) -> int:
    n = 0
    cur = today
    # Streak counts back from today; if today isn't done yet, start from yesterday
    # so an unticked "today" doesn't reset a real streak.
    if cur.isoformat() not in done:
        cur = cur - timedelta(days=1)
    while cur.isoformat() in done:
        n += 1
        cur = cur - timedelta(days=1)
    return n


@app.get("/habits", response_model=list[HabitOut])
def list_habits(days: int = 30, session: Session = Depends(get_session)):
    today = datetime.now(timezone.utc).date()
    window_start = (today - timedelta(days=max(1, days) - 1)).isoformat()
    habits = session.scalars(
        select(Habit).where(Habit.archived.is_(False)).order_by(Habit.sort, Habit.id)
    ).all()
    out = []
    for h in habits:
        all_days = {l.day for l in h.logs}
        window = sorted(d for d in all_days if d >= window_start)
        out.append(HabitOut(
            id=h.id, name=h.name, emoji=h.emoji,
            streak=_streak(all_days, today), days=window,
        ))
    return out


@app.post("/habits", response_model=HabitOut, status_code=201)
def create_habit(payload: HabitIn, session: Session = Depends(get_session)):
    nxt = (session.scalar(select(Habit.sort).order_by(Habit.sort.desc())) or 0) + 1
    h = Habit(name=payload.name.strip(), emoji=payload.emoji.strip(), sort=nxt)
    session.add(h)
    session.commit()
    return HabitOut(id=h.id, name=h.name, emoji=h.emoji, streak=0, days=[])


@app.post("/habits/{habit_id}/toggle", response_model=HabitOut)
def toggle_habit(
    habit_id: int, day: str | None = None, session: Session = Depends(get_session)
):
    h = session.get(Habit, habit_id)
    if not h:
        raise HTTPException(404, "Habit not found")
    d = day or datetime.now(timezone.utc).date().isoformat()
    existing = session.scalar(
        select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.day == d)
    )
    if existing:
        session.delete(existing)
    else:
        session.add(HabitLog(habit_id=habit_id, day=d))
    session.commit()
    session.refresh(h)
    all_days = {l.day for l in h.logs}
    today = datetime.now(timezone.utc).date()
    window_start = (today - timedelta(days=29)).isoformat()
    return HabitOut(
        id=h.id, name=h.name, emoji=h.emoji, streak=_streak(all_days, today),
        days=sorted(d for d in all_days if d >= window_start),
    )


@app.delete("/habits/{habit_id}")
def delete_habit(habit_id: int, session: Session = Depends(get_session)):
    h = session.get(Habit, habit_id)
    if h:
        h.archived = True
        session.commit()
    return {"archived": habit_id}


# ------------------------------------------------------------------ journal

class JournalOut(BaseModel):
    day: str
    text: str
    mood: str


class JournalIn(BaseModel):
    text: str = ""
    mood: str = ""


@app.get("/journal/{day}", response_model=JournalOut)
def get_journal(day: str, session: Session = Depends(get_session)):
    e = session.scalar(select(JournalEntry).where(JournalEntry.day == day))
    return JournalOut(day=day, text=e.text if e else "", mood=e.mood if e else "")


@app.put("/journal/{day}", response_model=JournalOut)
def put_journal(day: str, payload: JournalIn, session: Session = Depends(get_session)):
    e = session.scalar(select(JournalEntry).where(JournalEntry.day == day))
    if not e:
        e = JournalEntry(day=day)
        session.add(e)
    e.text = payload.text
    e.mood = payload.mood
    session.commit()
    return JournalOut(day=e.day, text=e.text, mood=e.mood)


@app.get("/journal")
def list_journal(limit: int = 14, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(JournalEntry).order_by(JournalEntry.day.desc()).limit(limit)
    ).all()
    return [{"day": r.day, "text": r.text, "mood": r.mood} for r in rows]


# ------------------------------------------------------------- second brain

class NoteOut(BaseModel):
    id: int
    kind: str
    title: str
    content: str
    url: str
    tags: str
    created_at: datetime


class NoteIn(BaseModel):
    kind: str = "note"
    title: str = ""
    content: str = ""
    url: str = ""
    tags: str = ""


def _note_out(n: Note) -> NoteOut:
    return NoteOut(id=n.id, kind=n.kind, title=n.title, content=n.content,
                   url=n.url, tags=n.tags, created_at=n.created_at)


@app.get("/notes", response_model=list[NoteOut])
def list_notes(session: Session = Depends(get_session)):
    notes = session.scalars(select(Note).order_by(Note.created_at.desc())).all()
    return [_note_out(n) for n in notes]


@app.post("/notes", response_model=NoteOut, status_code=201)
def add_note(payload: NoteIn, session: Session = Depends(get_session)):
    kind = payload.kind if payload.kind in ("note", "bookmark") else "note"
    if not (payload.content.strip() or payload.url.strip() or payload.title.strip()):
        raise HTTPException(400, "A note needs some content, title or URL")
    n = Note(
        kind=kind, title=payload.title.strip(), content=payload.content.strip(),
        url=payload.url.strip(), tags=payload.tags.strip(),
    )
    session.add(n)
    session.commit()
    return _note_out(n)


@app.delete("/notes/{note_id}")
def delete_note(note_id: int, session: Session = Depends(get_session)):
    n = session.get(Note, note_id)
    if n:
        session.delete(n)
        session.commit()
    return {"deleted": note_id}


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@app.post("/brain/ask")
def brain_ask_endpoint(payload: AskIn, session: Session = Depends(get_session)):
    return brain_ask(session, payload.question.strip())


# ------------------------------------------------------------- notifications

@app.get("/notify/status")
def notify_status():
    return {"channels": notify.configured_channels()}


@app.post("/notify/test")
def notify_test():
    result = notify.notify("✅ Adjutant test", "Notifications are wired up correctly.")
    if not result["channels"]:
        raise HTTPException(
            400,
            "No notification channels configured. Set TELEGRAM_BOT_TOKEN + "
            "TELEGRAM_CHAT_ID, and/or rely on the Gmail email channel.",
        )
    return result


class FounderProfile(BaseModel):
    profile: str


@app.get("/founder", response_model=FounderProfile)
def get_founder():
    return FounderProfile(profile=founder.load_profile())


@app.put("/founder", response_model=FounderProfile)
def put_founder(payload: FounderProfile):
    founder.save_profile(payload.profile)
    return FounderProfile(profile=founder.load_profile())


class Automations(BaseModel):
    # Whether each paid daily background job runs automatically. Manual
    # generate/scout/run buttons are unaffected — these gate only the auto runs.
    ideas: bool
    jobs: bool
    research: bool


@app.get("/settings/automations", response_model=Automations)
def get_automations(session: Session = Depends(get_session)):
    return Automations(
        ideas=_automation_on(session, "ideas"),
        jobs=_automation_on(session, "jobs"),
        research=_automation_on(session, "research"),
    )


@app.put("/settings/automations", response_model=Automations)
def put_automations(payload: Automations, session: Session = Depends(get_session)):
    settings.set_bool(session, AUTOMATION_KEYS["ideas"][0], payload.ideas)
    settings.set_bool(session, AUTOMATION_KEYS["jobs"][0], payload.jobs)
    settings.set_bool(session, AUTOMATION_KEYS["research"][0], payload.research)
    return payload


@app.post("/standing")
def project_standings(refresh: bool = False, session: Session = Depends(get_session)):
    """One-line AI status report + next step per work project. Cached."""
    return build_standings(session, refresh=refresh)


@app.post("/digest")
def digest_briefing(
    days: int = 7, refresh: bool = False, session: Session = Depends(get_session)
):
    """The digest briefing: a short AI summary of the feed-noise categories,
    filtered to what's genuinely interesting. Cached until mail state changes."""
    return build_briefing(session, days=days, refresh=refresh)


@app.post("/style/build")
def build_style_corpus(max_messages: int = 200):
    count = style.build_corpus(get_provider(), max_messages=max_messages)
    return {"examples_kept": count}


@app.get("/health")
def health():
    return {"ok": True, "style_corpus_examples": style.corpus_size()}
