"""Shared LLM access + vendor selection.

Every model call in the app goes through `complete()` / `complete_with_search()`
here; the concrete vendor is chosen once by `LLM_PROVIDER` (default "anthropic")
and lives behind the `LLMProvider` seam in this package — mirroring how all
email code lives behind `providers/`.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from dotenv import load_dotenv

from .anthropic import AnthropicLLM
from .base import LLMProvider

load_dotenv()

CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", "claude-haiku-4-5-20251001")
DRAFT_MODEL = os.getenv("DRAFT_MODEL", "claude-sonnet-4-6")

# Shared instruction so emphasis is decided semantically by the model, not by a
# client-side regex. Append to any system prompt whose free-text output is
# rendered through the frontend <Emphasize> component.
EMPHASIS_GUIDE = (
    "EMPHASIS: guide the reader's eye in the free-text fields. Wrap the single "
    "most decision-driving phrase in ==double equals== (renders highlighted) and "
    "at most one or two secondary key terms in **double asterisks** (renders "
    "bold). Mark what genuinely carries weight — the core insight, a real "
    "constraint, the thing that makes this worth their time — NOT categories, "
    "numbers, dates, or jargon by reflex. Be sparing: many fields need no marks, "
    "and never mark whole sentences. Keep the marks inside the JSON string values."
)


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    name = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if name == "openai":
        from .openai import OpenAILLM
        return OpenAILLM()
    return AnthropicLLM()


def complete(
    model: str, system: str, user: str, max_tokens: int = 1024,
    think: bool = False, temperature: float | None = None,
) -> str:
    return get_provider().complete(
        model, system, user, max_tokens=max_tokens, think=think, temperature=temperature
    )


def complete_with_search(
    model: str, system: str, user: str, max_tokens: int = 2048, max_searches: int = 5
) -> str:
    return get_provider().complete_with_search(
        model, system, user, max_tokens=max_tokens, max_searches=max_searches
    )


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response, defensively."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


__all__ = [
    "CLASSIFY_MODEL",
    "DRAFT_MODEL",
    "EMPHASIS_GUIDE",
    "LLMProvider",
    "complete",
    "complete_with_search",
    "extract_json",
    "get_provider",
]
