"""Classifier — assigns a thread to a project (or none), rates its relevance,
and decides whether the latest message needs a reply from me."""
from __future__ import annotations

import os
from dataclasses import dataclass

from core.llm import CLASSIFY_MODEL, complete, extract_json
from core.models import EmailThread

# Senders we NEVER draft a reply to, even when the content looks reply-worthy —
# e.g. flat-hunting platforms, which you handle on the site, not by email reply.
# Comma-separated domains/substrings, matched against the latest inbound sender;
# extend via the NEVER_REPLY_SENDERS env var.
_NEVER_REPLY = [
    d.strip().lower()
    for d in os.getenv("NEVER_REPLY_SENDERS", "wg-gesucht.de").split(",")
    if d.strip()
]


def _never_reply_sender(thread: EmailThread) -> bool:
    msg = getattr(thread, "last_inbound", None) or getattr(thread, "last_message", None)
    email = (getattr(msg, "sender_email", "") or "").lower() if msg else ""
    return bool(email) and any(tok in email for tok in _NEVER_REPLY)

_SYSTEM = """You are an email triage assistant. You will be given the user's \
project list (name + description of what belongs in it) and an email thread.

Respond with ONLY a JSON object, no prose:
{
  "project": "<exact project name, or null if no project fits>",
  "relevance": "<one of: reply | read | skip>",
  "urgency": "<high ONLY for a genuine, near-term, human deadline or a real person \
blocked waiting on the user; otherwise normal>",
  "reason": "<one short sentence>"
}

Urgency bar (be strict — 'high' should be rare):
- "high" requires a SPECIFIC soon deadline (days, not weeks) or a named person who \
is actually blocked on the user's response. Most mail is "normal".
- NEVER "high": security alerts, login/verification codes, account/billing/subscription \
notices, document-portal or admin auto-notifications, system/maintenance notices, \
newsletters, job alerts, anything from a no-reply/automated sender. These are "normal" \
regardless of alarming wording.

Relevance scale:
- "reply": the latest inbound message involves the user (in the To OR CC line) and \
awaits a substantive response from them. (A thread forwarded by the user from \
another of their own accounts still counts as "reply" if the forwarded content \
awaits their response.)
  Treat it as "reply" whenever the THREAD (look at the whole thread, not only the last \
message) has ANY of the following still open and NOT yet answered by the user — even if \
the latest message is someone else agreeing, and EVEN IF THE USER IS ONLY CC'd:
    • a direct question to the user (e.g. "what time works for you?", "können \
wir …?", "wäre das ok?")
    • a meeting/call being scheduled where the user has not yet given their OWN \
availability or confirmation — even if other participants have already agreed a time \
(the user still owes their yes/no and slot)
    • a request for a decision, an action, feedback, or a document from the user
    • an introduction of the user to someone, or a loop-in to a collaboration / \
project, where a meeting or next step is in flight and the user is an expected \
participant
  Being CC'd rather than in "To" does NOT downgrade this: if the user is a named or \
expected participant — introduced by name, asked to join, or addressed as part of a \
group ("ihr", "euch", "you both", "wir") — it is "reply". A real person waiting on the \
user — especially a known collaborator — almost always means "reply", not "read". When \
torn between "reply" and "read", choose "reply": a needless draft is cheap, a missed \
reply is not.
- "read": worth the user's attention — personal or work-related information they \
should see — but genuinely no response is required (pure FYI, a confirmation, or \
they already sent the last word and nothing is asked of them).
- "skip": ONLY automated or bulk mail not worth attention — newsletters, marketing, \
promotions, job alerts, social-media notifications, receipts, automated alerts, mass \
mail. A genuine message from a REAL PERSON that involves the user (an introduction, a \
collaboration, coordination, a question) is NEVER "skip" — it is "reply" or "read".

Rules:
- "project" must be copied EXACTLY from the provided list or be null. Never invent one.
- When genuinely unsure between projects, pick null over guessing.
- Automated mail (no-reply senders, marketing, alerts) is always "skip"."""

_MAX_BODY = 1500   # chars per message in the prompt
_MAX_MSGS = 4      # most recent messages shown


@dataclass
class Classification:
    project_name: str | None
    relevance: str  # "reply" | "read" | "skip"
    urgency: str  # "high" | "normal"
    reason: str

    @property
    def needs_reply(self) -> bool:
        return self.relevance == "reply"


def render_thread(thread: EmailThread, max_msgs: int = _MAX_MSGS) -> str:
    lines = [f"Subject: {thread.subject or '(no subject)'}"]
    msgs = thread.messages[-max_msgs:]
    if len(thread.messages) > max_msgs:
        lines.append(f"[... {len(thread.messages) - max_msgs} earlier messages omitted ...]")
    for i, m in enumerate(msgs, 1):
        who = "ME" if m.is_from_me else f"{m.sender_display} <{m.sender_email}>"
        when = m.date.strftime("%Y-%m-%d %H:%M") if m.date else "unknown date"
        body = (m.body_text or "").strip()
        if len(body) > _MAX_BODY:
            body = body[:_MAX_BODY] + " [...truncated]"
        lines.append(f"--- Message {i} | From: {who} | {when} ---\n{body}")
    return "\n".join(lines)


def classify_thread(thread: EmailThread, projects: list[dict]) -> Classification:
    """`projects` = [{"name": ..., "description": ...}, ...]"""
    if projects:
        plist = "\n".join(f'- "{p["name"]}": {p["description"]}' for p in projects)
    else:
        plist = "(no projects defined yet)"
    user = f"PROJECTS:\n{plist}\n\nTHREAD:\n{render_thread(thread)}"

    # temperature=0: triage must be deterministic — the same email should always
    # get the same verdict, not occasionally flip reply<->read across syncs.
    raw = complete(CLASSIFY_MODEL, _SYSTEM, user, max_tokens=300, temperature=0)
    data = extract_json(raw)

    project = data.get("project")
    valid_names = {p["name"] for p in projects}
    if not isinstance(project, str) or project not in valid_names:
        project = None
    relevance = data.get("relevance")
    if relevance not in ("reply", "read", "skip"):
        relevance = "read"  # fail open: never silently bury mail
    # Hard rule: never draft to certain senders — downgrade reply -> read so the
    # mail stays visible but never gets a drafted response.
    if relevance == "reply" and _never_reply_sender(thread):
        relevance = "read"
    urgency = data.get("urgency")
    if urgency not in ("high", "normal"):
        urgency = "normal"
    return Classification(
        project_name=project,
        relevance=relevance,
        urgency=urgency,
        reason=str(data.get("reason", "")),
    )
