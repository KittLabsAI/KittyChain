"""Search token candidates via KittyChain API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from _kittychain_api import post_kittychain
else:
    from .base import Tool
    from ._kittychain_api import post_kittychain


def _normalize_query_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def render_text(results: list[dict[str, Any]]) -> str:
    if not results:
        return "Token search results:\n- No matching tokens found"

    lines = ["Token search results:"]
    for index, item in enumerate(results, start=1):
        platforms = item.get("platforms") or {}
        if platforms:
            platform_text = ", ".join(f"{key}: {value}" for key, value in platforms.items())
        else:
            platform_text = "-"
        lines.extend(
            [
                "",
                f"{index}. {item['name']} ({item['symbol']})",
                f"   id: {item['id']}",
                f"   platforms: {platform_text}",
            ]
        )
    return "\n".join(lines)


class TokenSearchTool(Tool):
    name = "token_search"
    description = """
Search token candidates by exact token symbol or token name via KittyChain API.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_symbol": {
                "type": "string",
                "description": "Optional exact token symbol to match, case-insensitive.",
            },
            "token_name": {
                "type": "string",
                "description": "Optional exact token name to match, case-insensitive.",
            },
        },
    }

    def execute(self, token_symbol: str = "", token_name: str = "") -> str:
        normalized_symbol = _normalize_query_value(token_symbol)
        normalized_name = _normalize_query_value(token_name)
        if normalized_symbol is None and normalized_name is None:
            return "Error: token_symbol or token_name is required"
        payload: dict[str, Any] = {}
        if normalized_symbol:
            payload["tokenSymbol"] = normalized_symbol
        if normalized_name:
            payload["tokenName"] = normalized_name
        data = post_kittychain("/api/token/search", payload)
        items = data.get("items") or []
        return render_text(items)


def main(token_symbol: str = "", token_name: str = "") -> int:
    tool = TokenSearchTool()
    result = tool.execute(token_symbol=token_symbol, token_name=token_name)
    print(result)
    return 0 if not result.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("FITFI", ""))
