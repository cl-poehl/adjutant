"""Founder profile loader — the 'why you' grounding for idea generation."""
from __future__ import annotations

from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
PROFILE_PATH = _DATA / "founder_profile.md"
EXAMPLE_PATH = _DATA / "founder_profile.example.md"

_FALLBACK = "Technical founder looking for a startup idea. No detailed profile set yet."


def load_profile() -> str:
    # Real profile (git-ignored) first; fall back to the committed template.
    for path in (PROFILE_PATH, EXAMPLE_PATH):
        if path.exists():
            text = path.read_text().strip()
            if text:
                return text
    return _FALLBACK


def save_profile(text: str) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(text.strip() + "\n")
