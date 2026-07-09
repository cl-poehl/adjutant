"""Normalized internal email model.

Every provider (Gmail today, Outlook later) parses its wire format into these
models. Nothing outside providers/ ever sees raw provider JSON.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    """One message within a thread, provider-agnostic."""

    provider_message_id: str = ""
    sender_name: str = ""
    sender_email: str = ""
    to: list[str] = Field(default_factory=list)
    date: datetime | None = None
    body_text: str = ""
    is_from_me: bool = False
    # RFC 2822 threading headers, needed to build correctly-threaded replies.
    rfc822_message_id: str = ""
    references: str = ""
    reply_to: str = ""

    @property
    def sender_display(self) -> str:
        return self.sender_name or self.sender_email


class EmailThread(BaseModel):
    """A whole conversation, provider-agnostic."""

    provider: str
    provider_thread_id: str
    subject: str = ""
    snippet: str = ""
    messages: list[EmailMessage] = Field(default_factory=list)

    @property
    def last_message(self) -> EmailMessage | None:
        return self.messages[-1] if self.messages else None

    @property
    def last_inbound(self) -> EmailMessage | None:
        """Most recent message NOT sent by me — the one a reply answers."""
        for msg in reversed(self.messages):
            if not msg.is_from_me:
                return msg
        return None

    @property
    def last_sender(self) -> str:
        last = self.last_message
        return last.sender_display if last else ""
