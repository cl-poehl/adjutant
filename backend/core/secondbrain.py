"""Second brain — answer questions over the user's own notes & bookmarks.

No embeddings infra needed: retrieval is lexical (term-overlap scoring with a
light TF-IDF-ish weighting), which is plenty for a personal corpus. The top
chunks are handed to the model, which answers ONLY from them and cites note ids.
This keeps it honest — it can say "not in your notes" instead of hallucinating.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.llm import DRAFT_MODEL, complete
from db.models import Note

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "on",
    "with", "as", "at", "by", "be", "this", "that", "are", "was", "what", "how",
    "why", "when", "which", "who", "do", "does", "i", "my", "me", "you", "your",
}


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 1]


def retrieve(session: Session, question: str, k: int = 6) -> list[tuple[Note, float]]:
    """Top-k notes for a question by IDF-weighted term overlap."""
    notes = session.scalars(select(Note)).all()
    if not notes:
        return []
    q_terms = set(_tokens(question))
    if not q_terms:
        return []

    # document frequency for IDF
    docs_terms = {n.id: Counter(_tokens(f"{n.title} {n.content} {n.tags}")) for n in notes}
    df = Counter()
    for terms in docs_terms.values():
        for t in set(terms):
            df[t] += 1
    n_docs = len(notes)

    scored: list[tuple[Note, float]] = []
    for note in notes:
        tf = docs_terms[note.id]
        total = sum(tf.values()) or 1
        score = 0.0
        for t in q_terms:
            if t in tf:
                idf = math.log(1 + n_docs / (1 + df[t]))
                score += (tf[t] / total) * idf
        # small boost when a query term hits the title
        title_terms = set(_tokens(note.title))
        score += 0.15 * len(q_terms & title_terms)
        if score > 0:
            scored.append((note, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:k]


_SYSTEM = """You are the user's second brain. Answer the question using ONLY the \
provided notes & bookmarks (their own saved material). Cite the notes you use inline \
as [#<id>]. If the notes don't contain the answer, say so plainly — do NOT use outside \
knowledge or guess. Be concise and direct. When you state a fact, attach its [#id]."""


def ask(session: Session, question: str) -> dict:
    hits = retrieve(session, question)
    if not hits:
        return {
            "answer": "Nothing in your notes touches that yet. Add some notes or "
                      "bookmarks and ask again.",
            "sources": [],
        }
    context = "\n\n".join(
        f"[#{note.id}] {note.title or note.kind}"
        + (f" ({note.url})" if note.url else "")
        + f"\n{note.content}"
        for note, _ in hits
    )
    user = f"NOTES:\n{context}\n\nQUESTION: {question}"
    answer = complete(DRAFT_MODEL, _SYSTEM, user, max_tokens=900)
    return {
        "answer": answer.strip(),
        "sources": [
            {"id": note.id, "kind": note.kind, "title": note.title or "(untitled)",
             "url": note.url}
            for note, _ in hits
        ],
    }
