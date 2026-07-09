"""Drafter — writes a reply in MY voice, grounded in few-shot examples from my
sent mail. Output is a suggestion only; it never leaves without explicit review
and a Send click in the dashboard."""
from __future__ import annotations

from datetime import date as _date

from core import founder, style
from core.classify import render_thread
from core.llm import DRAFT_MODEL, complete
from core.models import EmailThread

_SYSTEM = """You ghost-write email replies for the user. Goal: a reply the user \
could send with at most tiny edits, indistinguishable from one they wrote.

Study the writing samples below — greeting style, sign-off, sentence length, \
formality, warmth, punctuation habits, directness — and mirror all of it.

Reason about the situation BEFORE writing. Getting the facts right matters more \
than matching the style:
- Timeline. Every message shows its date, and you are given today's date. Work \
out how much time has passed between messages and up to today. A relative time \
reference inside an EARLIER message ("next week", "tomorrow", "for the next four \
months", "until Friday") is relative to THAT message's date — recompute what it \
means as of today. A plan the user announced earlier may by now have already \
started, ended, or changed; never restate such a phrase verbatim as if it were \
still true today.
- Conditional offers. If the sender's offer depends on a condition ("if you're \
still at X", "while you're in town", "should you be available then"), check \
whether that condition still holds given the timeline. Do NOT accept an option \
whose precondition is no longer true — pick the option that fits the user's \
actual current situation instead.
- The real ask. What does the latest message actually want, and what is the \
truthful, useful reply given where things genuinely stand right now?
- Timing must be grounded, never guessed. If the sender raises dates, \
availability, or a position's timing AND the user's availability is stated in \
the facts (thread or profile), give it concretely rather than vaguely. If it is \
NOT stated, do NOT infer or guess a start date/year from indirect reasoning — \
keep that part general and let the user fill it. A wrong specific date is worse \
than a general sentence.

Rules:
- Output ONLY the body of the reply. No subject line, no commentary, no quoting \
of the original message, no bracketed placeholders.
- Reply to the latest inbound message; use the full thread for context.
- Match the thread's language (reply in German if the thread is in German, etc.).
- Be as long or as short as the user would be — their samples show their norm.
- Ground every specific — place, date, duration, plan, commitment — in the \
thread or the context provided. Never invent one, and never carry an out-of-date \
specific from an earlier message into the reply without updating it to today. If \
a detail you'd need isn't available, keep that part general rather than guessing."""


def generate_draft(
    thread: EmailThread,
    project_name: str | None = None,
    project_description: str | None = None,
    n_examples: int = 5,
    today: _date | None = None,
) -> str:
    today = today or _date.today()
    examples = style.sample_examples(n_examples)
    parts: list[str] = []

    if examples:
        sample_block = "\n\n".join(
            f"<sample {i}>\n{ex}\n</sample {i}>" for i, ex in enumerate(examples, 1)
        )
        parts.append(f"WRITING SAMPLES (replies the user actually sent):\n{sample_block}")
    else:
        parts.append(
            "WRITING SAMPLES: none available yet — write in a natural, concise, "
            "friendly-professional register."
        )

    profile = founder.load_profile()
    if profile.strip():
        parts.append(
            "ABOUT THE USER (facts to GROUND the reply — their role, timeline, "
            "location, background. Use only what's relevant to this specific "
            "email; never quote or dump it, and prefer these facts over guessing):\n"
            + profile.strip()
        )

    if project_name:
        parts.append(
            f"PROJECT CONTEXT: this thread belongs to the project \"{project_name}\""
            + (f" — {project_description}" if project_description else "")
        )

    parts.append(f"TODAY'S DATE: {today.isoformat()} — use it for the timeline reasoning above.")
    parts.append(f"THREAD TO REPLY TO:\n{render_thread(thread, max_msgs=6)}")
    parts.append("Write the reply (body text only — no reasoning, no preamble).")

    return complete(
        DRAFT_MODEL, _SYSTEM, "\n\n".join(parts), max_tokens=3000, think=True
    ).strip()
