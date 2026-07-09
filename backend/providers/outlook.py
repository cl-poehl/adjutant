"""OutlookProvider — Microsoft 365 / Exchange behind the EmailProvider interface.

Implements the same normalized operations as GmailProvider via Microsoft Graph.
Nothing outside this file knows Graph exists.

Setup (one-time):
1. Azure portal → App registrations → New registration
   - Supported account types: "Accounts in any organizational directory and
     personal Microsoft accounts" (or your tenant only)
   - No redirect URI needed (device-code flow); enable "Allow public client
     flows" under Authentication.
2. API permissions → Microsoft Graph → Delegated: Mail.ReadWrite, Mail.Send,
   User.Read. A university tenant may require ADMIN CONSENT for these —
   check with IT before relying on this provider.
3. .env: OUTLOOK_CLIENT_ID=<app id>, optionally OUTLOOK_TENANT_ID=<tenant>
   (defaults to "organizations"), EMAIL_PROVIDER=outlook.
4. First use prints a device-code URL — sign in with the Outlook account.

Status: implemented to the Graph v1.0 spec but NOT yet exercised against a
real tenant. Verify list → fetch → draft → send on a test mailbox first.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import msal
import requests

from core.models import EmailMessage, EmailThread
from core.textutil import html_to_text
from providers.base import EmailProvider

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.ReadWrite", "Mail.Send", "User.Read"]

_MSG_FIELDS = (
    "id,conversationId,subject,from,toRecipients,replyTo,receivedDateTime,"
    "body,bodyPreview,internetMessageId,isDraft"
)


class OutlookProvider(EmailProvider):
    name = "outlook"

    def __init__(self) -> None:
        self.client_id = os.getenv("OUTLOOK_CLIENT_ID", "")
        self.tenant = os.getenv("OUTLOOK_TENANT_ID", "organizations")
        self.token_path = os.getenv("OUTLOOK_TOKEN_PATH", "outlook_token.json")
        self._profile_email: str | None = None
        self._cache = msal.SerializableTokenCache()
        if Path(self.token_path).exists():
            self._cache.deserialize(Path(self.token_path).read_text())
        if not self.client_id:
            raise RuntimeError(
                "OUTLOOK_CLIENT_ID is not set — register an app in Azure "
                "(see providers/outlook.py docstring) and add it to .env."
            )
        self._app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant}",
            token_cache=self._cache,
        )

    # ------------------------------------------------------------------ auth

    def _token(self) -> str:
        accounts = self._app.get_accounts()
        result = (
            self._app.acquire_token_silent(SCOPES, account=accounts[0])
            if accounts
            else None
        )
        if not result:
            flow = self._app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise RuntimeError(f"Device flow failed: {flow.get('error_description')}")
            print(f"\n>>> OUTLOOK SIGN-IN <<<\n{flow['message']}\n", flush=True)
            result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Outlook auth failed: {result.get('error_description')}")
        if self._cache.has_state_changed:
            Path(self.token_path).write_text(self._cache.serialize())
        return result["access_token"]

    def _req(self, method: str, path: str, **kwargs) -> dict | None:
        resp = requests.request(
            method,
            f"{GRAPH}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=30,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def get_profile_email(self) -> str:
        if self._profile_email is None:
            me = self._req("GET", "/me")
            self._profile_email = (
                me.get("mail") or me.get("userPrincipalName", "")
            ).lower()
        return self._profile_email

    def _self_addresses(self) -> set[str]:
        aliases = {
            a.strip().lower()
            for a in os.getenv("MY_ALIASES", "").split(",")
            if a.strip()
        }
        aliases.add(self.get_profile_email())
        return aliases

    # ----------------------------------------------------------------- read

    def list_threads(self, max_results: int = 25, query: str | None = None) -> list[str]:
        # Graph has no thread listing — list recent inbox messages, dedupe by
        # conversationId preserving recency order. `query` (Gmail syntax) is
        # ignored; recency windowing comes from the message list itself.
        data = self._req(
            "GET",
            "/me/mailFolders/inbox/messages"
            f"?$top={min(max_results * 4, 200)}"
            "&$select=conversationId,receivedDateTime"
            "&$orderby=receivedDateTime desc",
        )
        seen: list[str] = []
        for m in data.get("value", []):
            cid = m.get("conversationId")
            if cid and cid not in seen:
                seen.append(cid)
            if len(seen) >= max_results:
                break
        return seen

    def get_thread(self, thread_id: str) -> EmailThread:
        data = self._req(
            "GET",
            f"/me/messages?$filter=conversationId eq '{thread_id}'"
            f"&$top=50&$select={_MSG_FIELDS}",
        )
        me = self._self_addresses()
        raw = sorted(
            data.get("value", []), key=lambda m: m.get("receivedDateTime", "")
        )
        messages = [self._parse_message(m, me) for m in raw if not m.get("isDraft")]
        return EmailThread(
            provider=self.name,
            provider_thread_id=thread_id,
            subject=raw[0].get("subject", "") if raw else "",
            snippet=raw[-1].get("bodyPreview", "") if raw else "",
            messages=messages,
        )

    def _parse_message(self, m: dict, my_addresses: set[str]) -> EmailMessage:
        frm = (m.get("from") or {}).get("emailAddress", {})
        sender_email = (frm.get("address") or "").lower()
        date = None
        if m.get("receivedDateTime"):
            try:
                date = datetime.fromisoformat(
                    m["receivedDateTime"].replace("Z", "+00:00")
                )
            except ValueError:
                date = None
        body = m.get("body") or {}
        text = body.get("content", "")
        if (body.get("contentType") or "").lower() == "html":
            text = html_to_text(text)
        reply_to = ""
        if m.get("replyTo"):
            reply_to = (m["replyTo"][0].get("emailAddress", {}).get("address") or "")
        return EmailMessage(
            provider_message_id=m.get("id", ""),
            sender_name=frm.get("name", ""),
            sender_email=sender_email,
            to=[
                (r.get("emailAddress", {}).get("address") or "").lower()
                for r in m.get("toRecipients", [])
            ],
            date=date,
            body_text=text.strip(),
            is_from_me=sender_email in my_addresses,
            rfc822_message_id=m.get("internetMessageId", ""),
            references="",  # Graph threads via conversationId; not needed
            reply_to=reply_to,
        )

    # ---------------------------------------------------------------- write

    def _target_message_id(self, thread: EmailThread) -> str:
        target = thread.last_inbound or thread.last_message
        if target is None:
            raise ValueError(f"Thread {thread.provider_thread_id} has no messages")
        return target.provider_message_id

    def create_draft(self, thread: EmailThread, body: str) -> str:
        # createReply gives Graph-side threading + correct recipients for free.
        draft = self._req(
            "POST", f"/me/messages/{self._target_message_id(thread)}/createReply"
        )
        self._req(
            "PATCH",
            f"/me/messages/{draft['id']}",
            json={"body": {"contentType": "Text", "content": body}},
        )
        return draft["id"]

    def send_message(
        self,
        thread: EmailThread,
        body: str,
        stale_draft_id: str | None = None,
        to: str | None = None,
    ) -> str:
        # Fresh reply draft from the exact approved text, then send it.
        # (Graph createReply sets recipients; `to` override is a later refinement.)
        draft_id = self.create_draft(thread, body)
        self._req("POST", f"/me/messages/{draft_id}/send")
        if stale_draft_id and stale_draft_id != draft_id:
            try:
                self._req("DELETE", f"/me/messages/{stale_draft_id}")
            except requests.HTTPError:
                pass  # already gone
        return draft_id

    def apply_label(self, thread_id: str, label: str) -> None:
        # Outlook categories ≈ Gmail labels; tag the latest message.
        data = self._req(
            "GET",
            f"/me/messages?$filter=conversationId eq '{thread_id}'"
            "&$top=1&$select=id,categories&$orderby=receivedDateTime desc",
        )
        for m in data.get("value", []):
            cats = set(m.get("categories", []))
            cats.add(f"Adjutant/{label}")
            self._req(
                "PATCH", f"/me/messages/{m['id']}", json={"categories": sorted(cats)}
            )

    # --------------------------------------------------------- style corpus

    def list_sent_messages(self, max_results: int = 200) -> list[EmailMessage]:
        me = self._self_addresses()
        out: list[EmailMessage] = []
        url = (
            f"/me/mailFolders/sentitems/messages?$top=100&$select={_MSG_FIELDS}"
            "&$orderby=receivedDateTime desc"
        )
        while url and len(out) < max_results:
            data = self._req("GET", url)
            for m in data.get("value", []):
                out.append(self._parse_message(m, me))
                if len(out) >= max_results:
                    break
            next_link = data.get("@odata.nextLink", "")
            url = next_link.replace(GRAPH, "") if next_link else None
        return out
