"""Anthropic backend — the default. Haiku for triage, Sonnet for drafting and
generation; adaptive thinking for reasoning-heavy drafts; the server-side
web_search tool for the research/scout agents."""
from __future__ import annotations

import os
from functools import lru_cache

from anthropic import Anthropic

from .base import LLMProvider


@lru_cache(maxsize=1)
def _client() -> Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — copy .env.example to .env and fill it in."
        )
    return Anthropic()


class AnthropicLLM(LLMProvider):
    name = "anthropic"

    def complete(
        self, model: str, system: str, user: str, max_tokens: int = 1024,
        think: bool = False, temperature: float | None = None,
    ) -> str:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if think:
            kwargs["thinking"] = {"type": "adaptive"}  # thinking pins temperature itself
        elif temperature is not None:
            kwargs["temperature"] = temperature
        resp = _client().messages.create(**kwargs)
        return "".join(b.text for b in resp.content if b.type == "text")

    def complete_with_search(
        self, model: str, system: str, user: str, max_tokens: int = 2048, max_searches: int = 5
    ) -> str:
        try:
            resp = _client().messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_searches,
                }],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            if text.strip():
                return text
        except Exception:
            pass  # search not enabled / unsupported → degrade gracefully
        return self.complete(model, system, user, max_tokens=max_tokens)
