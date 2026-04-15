"""Helpers for internal CSV-backed tools."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_csv_rows(path: str) -> list[dict[str, str]]:
    with Path(path).expanduser().open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def filter_rows(rows: list[dict[str, str]], biz_type: str | None = None) -> list[dict[str, str]]:
    if not biz_type:
        return rows
    return [row for row in rows if row.get("biz_type") == biz_type]


def parse_json_dict(raw: str) -> dict:
    value = (raw or "").strip()
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def stringify_tokens(tokens: list[str]) -> str:
    text = " ".join(token for token in tokens if token).strip()
    for source, target in (
        ("( ", "("),
        (" )", ")"),
        (" ,", ","),
        (" ;", ";"),
        (" :", ":"),
    ):
        text = text.replace(source, target)
    return text
