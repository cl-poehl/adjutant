"""SQLAlchemy models — mirror of db/migrations/001_init.sql.

Designed as the seed for later phases: `meetings` and `action_items` will FK
onto projects; progress fields will be added to projects. Nothing here blocks
that.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMAIL_STATUSES = ("new", "classified", "needs_reply", "drafted", "sent", "ignored")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # The description doubles as classification context — it is the prompt.
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # True for categories discovered by auto-organize (vs. user-created).
    auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True for low-priority feed buckets (newsletters/digests) — shown in a
    # muted "Digest" section and summarized by the briefing instead of read.
    digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    emails: Mapped[list["Email"]] = relationship(back_populates="project")


class Email(Base):
    """One row per thread, normalized and provider-agnostic."""

    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("provider", "provider_thread_id", name="uq_provider_thread"),
        CheckConstraint(
            "status IN ('new','classified','needs_reply','drafted','sent','ignored')",
            name="ck_email_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="gmail")
    provider_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    subject: Mapped[str] = mapped_column(Text, default="")
    last_sender: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    draft_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'high' | 'normal' — scored by the classifier at ingestion.
    urgency: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Hidden from the agenda until this moment ("not today").
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Ticked off the agenda as completed.
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set when I send a reply and am now waiting on them (follow-up radar).
    awaiting_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # provider_message_id of the last message we triaged. Lets sync notice when
    # a NEW message has arrived on an already-processed thread (e.g. the other
    # side replied, or I replied outside the dashboard) so the thread is
    # re-opened and re-drafted instead of keeping a stale draft.
    last_seen_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped[Project | None] = relationship(back_populates="emails")


class Idea(Base):
    """A generated startup idea. Seeds the later 'ideas' phase; for now a simple
    accumulating log the founder can save/dismiss."""

    __tablename__ = "ideas"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','saved','dismissed')", name="ck_idea_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_date: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(Text, nullable=False)
    pitch: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=3)
    why_now: Mapped[str] = mapped_column(Text, default="")
    why_you: Mapped[str] = mapped_column(Text, default="")
    first_step: Mapped[str] = mapped_column(Text, default="")
    market: Mapped[str] = mapped_column(Text, default="")
    signal: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Job(Base):
    """A scouted job opportunity matched to the founder profile."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','saved','dismissed')", name="ck_job_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    found_date: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(Text, default="")
    comp: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    fit_score: Mapped[int] = mapped_column(Integer, default=3)
    trajectory: Mapped[int] = mapped_column(Integer, default=3)
    why_fit: Mapped[str] = mapped_column(Text, default="")
    why_step_up: Mapped[str] = mapped_column(Text, default="")
    watch_outs: Mapped[str] = mapped_column(Text, default="")
    # Concrete step to become a fit / unblock (preprints, referral, visa runway).
    readiness: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Event(Base):
    """A scouted real-world event in the selected city, matched to the user's
    personal + professional interests. Same save/dismiss lifecycle as jobs."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','saved','dismissed')", name="ck_event_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    found_date: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD scouted
    city: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, default="")  # e.g. Classical, Techno, Art
    venue: Mapped[str] = mapped_column(Text, default="")
    when: Mapped[str] = mapped_column(Text, default="")  # human date/time, may be a range
    deadline: Mapped[str] = mapped_column(Text, default="")  # register/RSVP/ticket by
    price: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    fit_score: Mapped[int] = mapped_column(Integer, default=3)
    why_fit: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


# ───────────────────────────────── research agent ──────────────────────────

class ResearchTopic(Base):
    """A standing research question the agent digs into (on demand or nightly).
    Each run produces ResearchFinding rows the user can read/save/dismiss."""

    __tablename__ = "research_topics"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','done','error')", name="ck_research_status"
        ),
        CheckConstraint("cadence IN ('once','daily')", name="ck_research_cadence"),
        CheckConstraint("track IN ('you','venture')", name="ck_research_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    # Which section of the daily brief this feeds: 'you' = your research/career
    # edge; 'venture' = industry/competitor intel for what you're building.
    track: Mapped[str] = mapped_column(Text, nullable=False, default="you")
    # 'once' = run then go idle; 'daily' = re-run each night for fresh developments.
    cadence: Mapped[str] = mapped_column(Text, nullable=False, default="once")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    last_summary: Mapped[str] = mapped_column(Text, default="")  # headline of last run
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    findings: Mapped[list["ResearchFinding"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class ResearchFinding(Base):
    """One nugget surfaced by a research run — a claim/development plus why it
    matters and a source to verify it."""

    __tablename__ = "research_findings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','saved','dismissed')", name="ck_finding_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("research_topics.id", ondelete="CASCADE"), nullable=False
    )
    run_date: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    why_matters: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    topic: Mapped["ResearchTopic"] = relationship(back_populates="findings")


class ResearchBrief(Base):
    """The synthesized daily morning brief — two sections of bullet lines
    (markdown), one row per day. Pinned in the Research pane and pushed."""

    __tablename__ = "research_briefs"
    __table_args__ = (UniqueConstraint("day", name="uq_brief_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD
    for_you: Mapped[str] = mapped_column(Text, default="")  # markdown bullets
    ventures: Mapped[str] = mapped_column(Text, default="")  # markdown bullets
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


# ──────────────────────────────── habits & journal ─────────────────────────

class Habit(Base):
    """A habit to keep a streak on. Completions live in HabitLog (one per day)."""

    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    emoji: Mapped[str] = mapped_column(Text, default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    logs: Mapped[list["HabitLog"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan"
    )


class HabitLog(Base):
    """A single day's completion of a habit."""

    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint("habit_id", "day", name="uq_habit_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey("habits.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD

    habit: Mapped["Habit"] = relationship(back_populates="logs")


class JournalEntry(Base):
    """A free-text journal entry for a given day (one per day, upserted)."""

    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("day", name="uq_journal_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(Text, nullable=False)  # YYYY-MM-DD
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mood: Mapped[str] = mapped_column(Text, default="")  # optional emoji/word
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# ───────────────────────────── second brain (notes) ────────────────────────

class Setting(Base):
    """A single runtime setting (key → value). Backs the dashboard's automation
    toggles so the paid daily jobs can be switched on/off without redeploying."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Note(Base):
    """A note or bookmark in the second brain. Q&A retrieves over `content`."""

    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint("kind IN ('note','bookmark')", name="ck_note_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="note")
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
