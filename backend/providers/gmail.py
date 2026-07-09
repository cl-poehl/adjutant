"""GmailProvider — Gmail behind the EmailProvider interface.

All Gmail-specific code (OAuth, wire-format parsing, MIME building, labels)
lives here and nowhere else.
"""
from __future__ import annotations

import base64
import os
import re
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr, parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.models import EmailMessage, EmailThread
from core.textutil import html_to_text
from providers.base import EmailProvider

# gmail.modify covers read + labels + drafts; gmail.send covers sending.
# Narrowest pair that covers the v1 loop (modify is a superset of readonly).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

PARENT_LABEL = "Adjutant"


def _decode_b64url(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


class GmailProvider(EmailProvider):
    name = "gmail"

    def __init__(self, credentials_path: str | None = None, token_path: str | None = None):
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_CREDENTIALS_PATH", "credentials.json"
        )
        self.token_path = token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        self._service = None
        self._profile_email: str | None = None
        self._label_cache: dict[str, str] = {}  # name -> id

    # ------------------------------------------------------------------ auth

    def _credentials(self) -> Credentials:
        creds: Credentials | None = None
        if Path(self.token_path).exists():
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(self.credentials_path).exists():
                raise FileNotFoundError(
                    f"Google OAuth client file not found at '{self.credentials_path}'. "
                    "Download it from Google Cloud Console (OAuth client, type Desktop) "
                    "and set GOOGLE_CREDENTIALS_PATH. See README."
                )
            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(self.token_path).write_text(creds.to_json())
        return creds

    @property
    def service(self):
        if self._service is None:
            self._service = build(
                "gmail", "v1", credentials=self._credentials(), cache_discovery=False
            )
        return self._service

    def get_profile_email(self) -> str:
        if self._profile_email is None:
            profile = self.service.users().getProfile(userId="me").execute()
            self._profile_email = profile.get("emailAddress", "").lower()
        return self._profile_email

    def _self_addresses(self) -> set[str]:
        """All addresses that count as 'me': the account itself plus any
        aliases (e.g. a university address whose mail is forwarded here),
        configured via MY_ALIASES (comma-separated)."""
        aliases = {
            a.strip().lower()
            for a in os.getenv("MY_ALIASES", "").split(",")
            if a.strip()
        }
        aliases.add(self.get_profile_email())
        return aliases

    # ----------------------------------------------------------------- read

    def list_threads(self, max_results: int = 25, query: str | None = None) -> list[str]:
        q = query or "in:inbox -in:chats"
        resp = (
            self.service.users()
            .threads()
            .list(userId="me", q=q, maxResults=max_results)
            .execute()
        )
        return [t["id"] for t in resp.get("threads", [])]

    def list_recent_thread_messages(
        self, max_results: int = 400, query: str | None = None
    ) -> list[tuple[str, str]]:
        """(thread_id, newest_message_id) pairs ordered by message recency,
        freshest first, one entry per thread.

        threads().list ranks a thread by an internal key that can lag the
        inbox's true recency — a long thread that just got a fresh reply can be
        ranked as old and fall outside the top-N. messages().list is ordered by
        message internalDate (real receive time) and already carries threadId
        per entry, so scanning the newest N messages and de-duping to their
        threads reliably surfaces every thread with recent activity — and the
        first message id we see per thread is that thread's newest, which lets
        the sync tell 'nothing new' from 'a fresh reply landed' without a fetch."""
        q = query or "in:inbox -in:chats"
        seen: set[str] = set()
        pairs: list[tuple[str, str]] = []
        token: str | None = None
        while len(pairs) < max_results:
            resp = (
                self.service.users()
                .messages()
                .list(userId="me", q=q, maxResults=500, pageToken=token)
                .execute()
            )
            for m in resp.get("messages", []):
                tid, mid = m.get("threadId"), m.get("id")
                if tid and tid not in seen:
                    seen.add(tid)
                    pairs.append((tid, mid))
            token = resp.get("nextPageToken")
            if not token or not resp.get("messages"):
                break
        return pairs

    def get_thread(self, thread_id: str) -> EmailThread:
        raw = (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        me = self._self_addresses()
        # Skip unsent drafts: a draft we created sits in the thread as a
        # message, but it is NOT something the user actually sent. Treating it
        # as a real message poisons classification and re-drafting (the model
        # reasons off its own stale draft). Only sent/received messages count.
        real = [m for m in raw.get("messages", []) if "DRAFT" not in m.get("labelIds", [])]
        messages = [self._parse_message(m, me) for m in real]
        subject = ""
        for m in real:
            subject = _header(m, "Subject")
            if subject:
                break
        return EmailThread(
            provider=self.name,
            provider_thread_id=thread_id,
            subject=subject,
            snippet=raw.get("messages", [{}])[-1].get("snippet", ""),
            messages=messages,
        )

    def _parse_message(self, msg: dict, my_addresses: set[str]) -> EmailMessage:
        sender_name, sender_email = parseaddr(_header(msg, "From"))
        date = None
        raw_date = _header(msg, "Date")
        if raw_date:
            try:
                date = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                date = None
        to = [addr for _, addr in
              (parseaddr(part) for part in _header(msg, "To").split(",")) if addr]
        return EmailMessage(
            provider_message_id=msg.get("id", ""),
            sender_name=sender_name,
            sender_email=sender_email.lower(),
            to=to,
            date=date,
            body_text=self._extract_body(msg.get("payload", {})),
            is_from_me=sender_email.lower() in my_addresses,
            rfc822_message_id=_header(msg, "Message-ID") or _header(msg, "Message-Id"),
            references=_header(msg, "References"),
            reply_to=_header(msg, "Reply-To"),
        )

    def _extract_body(self, payload: dict) -> str:
        """Walk MIME parts; prefer text/plain, fall back to stripped HTML."""
        plain, html = self._walk_parts(payload)
        if plain:
            return plain.strip()
        if html:
            return html_to_text(html)
        return ""

    def _walk_parts(self, payload: dict) -> tuple[str, str]:
        plain, html = "", ""
        mime = payload.get("mimeType", "")
        data = payload.get("body", {}).get("data")
        if data:
            if mime == "text/plain":
                plain += _decode_b64url(data)
            elif mime == "text/html":
                html += _decode_b64url(data)
        for part in payload.get("parts", []) or []:
            p, h = self._walk_parts(part)
            plain += p
            html += h
        return plain, html

    # ---------------------------------------------------------------- write

    def _build_reply_mime(self, thread: EmailThread, body: str, to: str | None = None) -> dict:
        """RFC-2822 reply: correct To / Subject / In-Reply-To / References so
        Gmail (and every other client) threads it properly."""
        target = thread.last_inbound or thread.last_message
        if target is None:
            raise ValueError(f"Thread {thread.provider_thread_id} has no messages")

        mime = MIMEText(body, "plain", "utf-8")
        to_addr = (to or "").strip() or target.reply_to or formataddr(
            (target.sender_name, target.sender_email)
        )
        mime["To"] = to_addr
        subject = thread.subject or ""
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        mime["Subject"] = subject or "Re:"
        if target.rfc822_message_id:
            mime["In-Reply-To"] = target.rfc822_message_id
            refs = f"{target.references} {target.rfc822_message_id}".strip()
            mime["References"] = refs
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        return {"raw": raw, "threadId": thread.provider_thread_id}

    def create_draft(self, thread: EmailThread, body: str) -> str:
        message = self._build_reply_mime(thread, body, to=self.suggested_recipient(thread))
        draft = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": message})
            .execute()
        )
        return draft["id"]

    def delete_draft(self, draft_id: str) -> None:
        try:
            self.service.users().drafts().delete(userId="me", id=draft_id).execute()
        except Exception:
            pass  # draft already gone — harmless

    def send_message(
        self,
        thread: EmailThread,
        body: str,
        stale_draft_id: str | None = None,
        to: str | None = None,
    ) -> str:
        """Send exactly `body` (the reviewed/edited text) as a fresh message,
        then discard the now-stale provider draft. Sending a fresh message —
        rather than drafts.send — guarantees what goes out is byte-for-byte
        what was approved in the dashboard."""
        message = self._build_reply_mime(thread, body, to=to or self.suggested_recipient(thread))
        sent = self.service.users().messages().send(userId="me", body=message).execute()
        if stale_draft_id:
            try:
                self.service.users().drafts().delete(userId="me", id=stale_draft_id).execute()
            except Exception:
                pass  # draft already gone — harmless
        return sent["id"]

    def send_email(self, to: str, subject: str, body: str) -> str:
        """Send a fresh, standalone email (not a thread reply). Used for
        notifications-to-self. `to` empty defaults to the account itself."""
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"] = (to or "").strip() or self.get_profile_email()
        mime["Subject"] = subject or "(no subject)"
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        sent = self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return sent["id"]

    # --------------------------------------------------------------- labels

    def _ensure_label(self, name: str) -> str:
        if not self._label_cache:
            resp = self.service.users().labels().list(userId="me").execute()
            self._label_cache = {l["name"]: l["id"] for l in resp.get("labels", [])}
        if name in self._label_cache:
            return self._label_cache[name]
        # Nested labels need the parent to exist first.
        if "/" in name:
            parent = name.rsplit("/", 1)[0]
            self._ensure_label(parent)
        created = (
            self.service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_cache[name] = created["id"]
        return created["id"]

    def suggested_recipient(self, thread: EmailThread) -> str:
        """Who a reply should go to. Normal threads: the last inbound sender.
        Forwarded (WG:/Fwd:) threads where every message is 'me': dig the
        original sender's address out of the forwarded header block."""
        me = self._self_addresses()
        if thread.last_inbound:
            return thread.last_inbound.sender_email
        # all-from-me (forwarded): find first email in the body that isn't mine
        for msg in reversed(thread.messages):
            for match in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", msg.body_text or ""):
                if match.lower() not in me:
                    return match
        return ""

    def apply_label(self, thread_id: str, label: str) -> None:
        label_id = self._ensure_label(f"{PARENT_LABEL}/{label}")
        self.service.users().threads().modify(
            userId="me", id=thread_id, body={"addLabelIds": [label_id]}
        ).execute()

    # --------------------------------------------------------- style corpus

    def list_sent_messages(self, max_results: int = 200) -> list[EmailMessage]:
        me = self._self_addresses()
        out: list[EmailMessage] = []
        page_token = None
        while len(out) < max_results:
            resp = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q="in:sent -in:chats",
                    maxResults=min(100, max_results - len(out)),
                    pageToken=page_token,
                )
                .execute()
            )
            for ref in resp.get("messages", []):
                full = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=ref["id"], format="full")
                    .execute()
                )
                out.append(self._parse_message(full, me))
                if len(out) >= max_results:
                    break
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out


def _header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""
