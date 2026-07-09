"""Push notifications for important things — Telegram and/or email-to-self.

Channels are opt-in via env, so nothing fires unless configured:
  NOTIFY_CHANNELS   comma list, e.g. "telegram,email"  (default: auto-detect)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID                  (for telegram)
  NOTIFY_EMAIL      address for email-to-self (default: the Gmail account)

Telegram uses the Bot API over stdlib urllib (no new deps). Email reuses the
Gmail provider's send_email(). Failures are swallowed + logged — a notification
must never break a sync.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

log = logging.getLogger("adjutant.notify")


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def configured_channels() -> list[str]:
    """Which channels are usable right now, honoring NOTIFY_CHANNELS if set."""
    explicit = [c.strip() for c in _env("NOTIFY_CHANNELS").split(",") if c.strip()]
    available = []
    if _env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"):
        available.append("telegram")
    # email works whenever the gmail provider is usable
    if os.getenv("EMAIL_PROVIDER", "gmail") == "gmail":
        available.append("email")
    if explicit:
        return [c for c in explicit if c in available]
    return available


def send_telegram(text: str) -> bool:
    token, chat = _env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return r.status == 200
    except Exception as exc:
        log.warning("telegram send failed: %s", exc)
        return False


def send_email(subject: str, body: str) -> bool:
    from providers import get_provider  # lazy: avoid import cycle
    try:
        provider = get_provider()
        if not hasattr(provider, "send_email"):
            return False
        provider.send_email(_env("NOTIFY_EMAIL"), subject, body)
        return True
    except Exception as exc:
        log.warning("email notify failed: %s", exc)
        return False


def notify(title: str, body: str = "") -> dict:
    """Fan a notification out to every configured channel."""
    channels = configured_channels()
    sent, failed = [], []
    text = f"*{title}*\n{body}".strip() if body else title
    for ch in channels:
        ok = send_telegram(text) if ch == "telegram" else send_email(title, body or title)
        (sent if ok else failed).append(ch)
    if channels:
        log.info("notify '%s' -> sent=%s failed=%s", title[:60], sent, failed)
    return {"channels": channels, "sent": sent, "failed": failed}


_AUTOMATED = (
    "no-reply", "noreply", "no_reply", "do-not-reply", "donotreply", "do_not_reply",
    "notifications@", "notification@", "mailer-daemon", "automated", "bounce",
    "@accounts.", "alerts@", "newsletter",
)


def _is_automated(item: dict) -> bool:
    blob = f"{item.get('from_email', '')} {item.get('sender', '')}".lower()
    return any(k in blob for k in _AUTOMATED)


def notify_sync_highlights(summary: dict, items: list[dict]) -> dict | None:
    """Called after a sync. Pushes a short alert ONLY for mail worth interrupting
    a day for: high-urgency AND a reply is actually owed AND a real (non-automated)
    sender. Security/account/maintenance/no-reply noise never qualifies."""
    if not configured_channels():
        return None
    urgent = [
        i for i in items
        if i.get("urgency") == "high"
        and i.get("needs_reply")
        and not _is_automated(i)
    ]
    if not urgent:
        return None
    lines = [f"• {i['subject'][:80]} — {i['sender'][:40]}" for i in urgent[:6]]
    extra = f"\n…and {len(urgent) - 6} more" if len(urgent) > 6 else ""
    title = f"📬 {len(urgent)} email{'s' if len(urgent) != 1 else ''} that need{'s' if len(urgent) == 1 else ''} you"
    return notify(title, "\n".join(lines) + extra)
