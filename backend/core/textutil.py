"""Shared text utilities — minimal, safe HTML → plain text for v1
(no rendering; tags stripped, structure preserved as line breaks)."""
from __future__ import annotations

import re
from html.parser import HTMLParser


class _HTMLToText(HTMLParser):
    _SKIP = {"script", "style", "head"}
    _BREAK = {"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(html)
        return parser.text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
