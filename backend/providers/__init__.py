"""Provider registry. Adding Outlook later = one entry here, zero changes elsewhere."""
from __future__ import annotations

import os
from functools import lru_cache

from providers.base import EmailProvider
from providers.gmail import GmailProvider
from providers.outlook import OutlookProvider

_REGISTRY: dict[str, type[EmailProvider]] = {
    "gmail": GmailProvider,
    "outlook": OutlookProvider,  # Microsoft Graph — see providers/outlook.py docstring
}


@lru_cache(maxsize=None)
def get_provider(name: str | None = None) -> EmailProvider:
    name = (name or os.getenv("EMAIL_PROVIDER", "gmail")).lower()
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"Unknown email provider '{name}'. Available: {list(_REGISTRY)}")
