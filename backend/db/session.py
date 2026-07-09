"""Engine + session factory.

DATABASE_URL drives everything: point it at Postgres for the spec'd setup
(run db/migrations/001_init.sql), or leave the SQLite default for a
zero-infrastructure local run (schema auto-created on startup).
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./adjutant.db")

# Accept Supabase/Heroku style URLs.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables if missing (idempotent; Postgres users may instead run
    the migration file — the schemas are identical)."""
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
