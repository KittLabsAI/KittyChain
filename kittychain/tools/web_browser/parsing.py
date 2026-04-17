"""Parsing helpers for web_browser."""

from __future__ import annotations

import re


def extract_page_text(value: str) -> str:
    return value


_SNAPSHOT_LINE_RE = re.compile(r'^(?P<ref>@e\d+)\s+\[(?P<meta>[^\]]+)\](?:\s+"(?P<text>[^"]*)")?(?:\s+(?P<rest>.*))?$')


def parse_snapshot_output(output: str) -> list[dict]:
    elements: list[dict] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _SNAPSHOT_LINE_RE.match(line)
        if not match:
            continue
        meta = match.group("meta")
        parts = meta.split()
        tag = parts[0] if parts else ""
        item = {"ref": match.group("ref"), "tag": tag}
        text = match.group("text")
        if text:
            item["text"] = text
        rest = match.group("rest") or ""
        placeholder = re.search(r'placeholder="([^"]*)"', rest)
        if placeholder:
            item["placeholder"] = placeholder.group(1)
        type_match = re.search(r'type="([^"]*)"', meta)
        if type_match:
            item["type"] = type_match.group(1)
        elements.append(item)
    return elements
