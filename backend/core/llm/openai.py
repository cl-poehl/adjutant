"""OpenAI backend — implemented against the OpenAI SDK, same interface.

Scaffolded like providers/outlook.py: wired and importable, but not yet
exercised in production. Enable with LLM_PROVIDER=openai and set model ids
(CLASSIFY_MODEL / DRAFT_MODEL) to OpenAI models (e.g. gpt-4o-mini / gpt-4o).
Requires `pip install openai` and OPENAI_API_KEY.
"""
from __future__ import annotations

from functools import lru_cache

from .base import LLMProvider


@lru_cache(maxsize=1)
def _client():
    try:
        from openai import OpenAI  # optional dependency
    except ImportError as exc:  # pragma: no cover - scaffold
        raise RuntimeError(
            "LLM_PROVIDER=openai requires the openai package — `pip install openai`."
        ) from exc
    return OpenAI()  # reads OPENAI_API_KEY from the environment


class OpenAILLM(LLMProvider):
    name = "openai"

    def complete(
        self, model: str, system: str, user: str, max_tokens: int = 1024, think: bool = False
    ) -> str:
        # `think` maps to a reasoning model's effort where applicable; for the
        # base chat models it is a no-op, so the returned text is the final
        # answer either way.
        resp = _client().chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    # complete_with_search intentionally inherits the base fallback until wired
    # to the OpenAI web-search / Responses API.
