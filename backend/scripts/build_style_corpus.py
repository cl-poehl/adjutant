"""Pull my sent mail and build the style corpus (few-shot examples for drafting).

Usage (from backend/):  python -m scripts.build_style_corpus [max_messages]
First run triggers the Google OAuth consent flow in your browser.
"""
from __future__ import annotations

import sys

from core import style
from providers import get_provider


def main() -> None:
    max_messages = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    provider = get_provider()
    print(f"Pulling up to {max_messages} sent messages from {provider.name} "
          f"({provider.get_profile_email()})…")
    kept = style.build_corpus(provider, max_messages=max_messages)
    print(f"Done. Kept {kept} usable examples → {style.CORPUS_PATH}")
    if kept < 20:
        print("Note: fewer than 20 examples — drafts will still work but will "
              "carry less of your voice. Consider raising max_messages.")


if __name__ == "__main__":
    main()
