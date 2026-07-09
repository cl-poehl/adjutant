"""LLMProvider — the model-vendor seam.

Mirrors providers/base.py (the email seam): the classifier, the drafter, and
every generation call reach the model only through complete() /
complete_with_search(), so swapping Anthropic for another vendor is one new file
plus one env var (LLM_PROVIDER) — no caller changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Normalized text-completion operations every model backend must support."""

    #: short identifier used by LLM_PROVIDER (e.g. "anthropic")
    name: str

    @abstractmethod
    def complete(
        self, model: str, system: str, user: str, max_tokens: int = 1024, think: bool = False
    ) -> str:
        """One completion, returning only the final text. `think=True` asks the
        model to reason in a hidden channel (where the vendor supports it) so
        that reasoning never leaks into the returned text; `max_tokens` must
        then also cover the thinking, so callers budget generously."""

    def complete_with_search(
        self, model: str, system: str, user: str, max_tokens: int = 2048, max_searches: int = 5
    ) -> str:
        """A completion that may run live web searches, where the vendor exposes
        a server-side search tool. The default degrades to a plain completion so
        every backend is usable without implementing search."""
        return self.complete(model, system, user, max_tokens=max_tokens)
