"""Runtime settings — a tiny key/value store in the DB so toggles set in the
dashboard persist across restarts and are read live by the background loop.

Used today for the automation switches (ideas / jobs / research brief) so the
user can turn the paid daily jobs on and off without redeploying or touching
env vars. Env vars remain the *default* when a key has never been set."""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import Setting

_TRUE = {"1", "true", "yes", "on"}


def get(session: Session, key: str, default: str | None = None) -> str | None:
    row = session.get(Setting, key)
    return row.value if row is not None else default


def set(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.commit()


def get_bool(session: Session, key: str, default: bool) -> bool:
    raw = get(session, key)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def set_bool(session: Session, key: str, value: bool) -> None:
    set(session, key, "true" if value else "false")
