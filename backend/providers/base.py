"""EmailProvider — the provider seam.

Gmail implements this today; OutlookProvider (Microsoft Graph) implements the
same interface later. The dashboard, classifier, drafter, and DB only ever see
the normalized models from core.models — never provider wire formats.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import EmailMessage, EmailThread


class EmailProvider(ABC):
    """Normalized operations every email backend must support."""

    #: short identifier stored in the DB `provider` column (e.g. "gmail")
    name: str

    @abstractmethod
    def list_threads(self, max_results: int = 25, query: str | None = None) -> list[str]:
        """Return provider thread IDs for recent inbox threads, newest first."""

    def list_recent_thread_messages(
        self, max_results: int = 400, query: str | None = None
    ) -> list[tuple[str, str]]:
        """(thread_id, newest_message_id) pairs ordered by message recency,
        freshest first, one per thread. Providers whose thread listing already
        reflects true message recency can leave this default (it falls back to
        list_threads and reports no message ids); those whose thread-level
        ordering can lag (e.g. Gmail) override it to scan messages directly so a
        freshly-replied older thread isn't ranked as stale and missed."""
        return [(tid, "") for tid in self.list_threads(max_results=max_results, query=query)]

    @abstractmethod
    def get_thread(self, thread_id: str) -> EmailThread:
        """Fetch a full thread, parsed into the normalized model."""

    @abstractmethod
    def create_draft(self, thread: EmailThread, body: str) -> str:
        """Create a reply draft on the thread. Returns the provider draft ID."""

    def delete_draft(self, draft_id: str) -> None:
        """Best-effort removal of a provider-side draft. Used when a draft is
        regenerated so the superseded one doesn't linger in the mailbox.
        Default is a no-op; providers that support it should override."""

    @abstractmethod
    def send_message(
        self,
        thread: EmailThread,
        body: str,
        stale_draft_id: str | None = None,
        to: str | None = None,
    ) -> str:
        """Send `body` as a reply on the thread (correct headers so it threads
        and lands in Sent). `to` overrides the recipient (used when the user
        edits it — e.g. forwarded threads). If `stale_draft_id` is given, that
        provider-side draft is superseded and cleaned up. Returns the sent
        message ID.

        This is the ONLY way mail leaves the system, and it is only ever
        called from the explicit send endpoint."""

    def suggested_recipient(self, thread: EmailThread) -> str:
        """Best guess at who a reply should go to. Default: the last inbound
        sender. Providers may override to handle forwarded threads."""
        target = thread.last_inbound
        return target.sender_email if target else ""

    @abstractmethod
    def apply_label(self, thread_id: str, label: str) -> None:
        """Tag the thread with a label/category, creating it if missing."""

    @abstractmethod
    def list_sent_messages(self, max_results: int = 200) -> list[EmailMessage]:
        """Recent messages I sent — the raw material for the style corpus."""

    @abstractmethod
    def get_profile_email(self) -> str:
        """The authenticated account's address."""
