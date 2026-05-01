"""Look up token detail data via KittyChain API."""

from __future__ import annotations

import json
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


def render_text(payload: dict[str, Any]) -> str:
    name = payload.get("name")
    symbol = payload.get("symbol")
    categories = payload.get("categories")
    links = payload.get("links") or []
    listing_markets = payload.get("listingMarkets") or []
    usdt_summary = payload.get("usdtTickersSummary") or {}

    category_text = ", ".join(str(item) for item in categories) if isinstance(categories, list) and categories else "-"
    listing_market_text = ", ".join(listing_markets) if listing_markets else "-"

    lines = [
        f"Token data: {name} ({symbol})",
        f"id: {payload.get('id')}",
        f"categories: {category_text}",
        "links:",
    ]
    if links:
        for link in links:
            label = link.get("label", "")
            url = link.get("url", "")
            lines.append(f"- {label}: {url}")
    else:
        lines.append("- -")

    lines.extend(
        [
            f"market_cap_rank: {payload.get('marketCapRank')}",
            f"developer_data: {json.dumps(payload.get('developerData') or {}, ensure_ascii=False, sort_keys=True)}",
            f"listing_markets: {listing_market_text}",
            "usdt_tickers_summary:",
        ]
    )

    if isinstance(usdt_summary, dict):
        for key, value in usdt_summary.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No USDT tickers summary")

    return "\n".join(lines)


class TokenDetailTool(Tool):
    name = "token_detail"
    description = """
Look up token detail data by token name or symbol via KittyChain API.
Returns categories, links, market-cap ranks, developer data, listing markets, and USDT ticker summaries.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_name": {
                "type": "string",
                "description": "Optional exact token name to search, for example 'USD Coin'.",
            },
            "token_symbol": {
                "type": "string",
                "description": "Optional exact token symbol to search, for example 'USDC'.",
            },
        },
    }

    def execute(self, token_name: str = "", token_symbol: str = "") -> str:
        normalized_name = _normalize_query_value(token_name)
        normalized_symbol = _normalize_query_value(token_symbol)
        if normalized_name is None and normalized_symbol is None:
            return "Error: token_name or token_symbol is required"
        payload: dict[str, Any] = {}
        if normalized_name:
            payload["tokenName"] = normalized_name
        if normalized_symbol:
            payload["tokenSymbol"] = normalized_symbol
        data = post_kittychain("/api/token/detail", payload)
        return render_text(data)


# Backward-compatible alias
TokenDataTool = TokenDetailTool


def main(token_name: str = "", token_symbol: str = "") -> int:
    tool = TokenDetailTool()
    result = tool.execute(token_name=token_name, token_symbol=token_symbol)
    print(result)
    return 0 if not result.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main(token_symbol="btc"))
