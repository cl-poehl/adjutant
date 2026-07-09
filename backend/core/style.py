"""Style corpus — the mechanism that makes drafts sound like me.

One-time (refreshable) pull of my sent mail via the provider; a cleaned sample
is persisted locally and a handful of examples are injected as few-shot
context into every drafting call. Few-shot only — no fine-tuning.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from providers.base import EmailProvider

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "style_corpus.json"

# Markers that begin quoted history in replies.
_QUOTE_PATTERNS = [
    re.compile(r"^On .{5,120} wrote:\s*$", re.MULTILINE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^From: .+$", re.MULTILINE),
    re.compile(r"^>.*$", re.MULTILINE),
]

MIN_BODY_CHARS = 80     # skip "ok thanks" one-liners — no signal
MAX_BODY_CHARS = 2500   # skip newsletters/forwards I technically "sent"


def strip_quoted_history(body: str) -> str:
    """Keep only the text I actually wrote, not the quoted thread below it."""
    cut = len(body)
    for pat in _QUOTE_PATTERNS:
        m = pat.search(body)
        if m:
            cut = min(cut, m.start())
    return body[:cut].strip()


def build_corpus(provider: EmailProvider, max_messages: int = 200) -> int:
    """Pull sent mail, clean it, persist usable examples. Returns count kept."""
    sent = provider.list_sent_messages(max_results=max_messages)
    examples: list[dict] = []
    for msg in sent:
        body = strip_quoted_history(msg.body_text or "")
        if not (MIN_BODY_CHARS <= len(body) <= MAX_BODY_CHARS):
            continue
        examples.append({"subject": "", "body": body})
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(json.dumps(examples, indent=2, ensure_ascii=False))
    return len(examples)


def load_corpus() -> list[dict]:
    if not CORPUS_PATH.exists():
        return []
    try:
        return json.loads(CORPUS_PATH.read_text())
    except json.JSONDecodeError:
        return []


def sample_examples(k: int = 5) -> list[str]:
    corpus = load_corpus()
    if not corpus:
        return []
    picked = random.sample(corpus, min(k, len(corpus)))
    return [ex["body"] for ex in picked]


def corpus_size() -> int:
    return len(load_corpus())
