"""Classifier — assigns a thread to a project (or none), rates its relevance,
and decides whether the latest message needs a reply from me."""
from __future__ import annotations

from dataclasses import dataclass

from core.llm import CLASSIFY_MODEL, complete, extract_json
from core.models import EmailThread

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
- "reply": the latest message is inbound, addressed to the user personally, and \
awaits a substantive response from them. (A thread forwarded by the user from \
another of their own accounts still counts as "reply" if the forwarded content \
awaits their response.)
  Treat it as "reply" whenever the latest inbound message does ANY of these — \
even if most of the message is informational/FYI:
    • asks the user a direct question (e.g. "what time works for you?", "können \
wir …?", "wäre das ok?")
    • proposes or tries to schedule a meeting/call and waits on the user to \
confirm or pick a time
    • requests a decision, an action, feedback, or a document from the user
  A real person waiting on the user — especially a known collaborator — almost \
always means "reply", not "read". When torn between "reply" and "read", choose \
"reply": a needless draft is cheap, a missed reply is not.
- "read": worth the user's attention — personal or work-related information they \
should see — but genuinely no response is required (pure FYI, a confirmation, or \
they already sent the last word and nothing is asked of them).
- "skip": not worth their attention: newsletters, marketing, promotions, job \
alerts, social-media notifications, receipts, automated alerts, mass mail.

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

    raw = complete(CLASSIFY_MODEL, _SYSTEM, user, max_tokens=300)
    data = extract_json(raw)

    project = data.get("project")
    valid_names = {p["name"] for p in projects}
    if not isinstance(project, str) or project not in valid_names:
        project = None
    relevance = data.get("relevance")
    if relevance not in ("reply", "read", "skip"):
        relevance = "read"  # fail open: never silently bury mail
    urgency = data.get("urgency")
    if urgency not in ("high", "normal"):
        urgency = "normal"
    return Classification(
        project_name=project,
        relevance=relevance,
        urgency=urgency,
        reason=str(data.get("reason", "")),
    )
