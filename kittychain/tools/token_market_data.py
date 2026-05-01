"""Look up token price data via KittyChain API."""

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


def render_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Token price results:\n- No matching tokens found"

    lines = ["Token price results:"]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                "",
                f"{index}. price_usd: {row.get('price_usd')}",
                f"   market_cap_usd: {row.get('market_cap_usd')}",
                f"   volume_24h_usd: {row.get('volume_24h_usd')}",
                f"   price_change_24h_pct: {row.get('price_change_24h_pct')}",
                f"   last_updated: {row.get('last_updated')}",
            ]
        )
    return "\n".join(lines)


class TokenPriceTool(Tool):
    name = "token_price"
    description = """
Look up token price data by chain and token contract address via KittyChain API.
Returns price, market cap, volume, and 24h price change.
    """
    parameters = {
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "Chain name or ID. Use: Ethereum, BSC, Arbitrum, Polygon, Base, Optimism, Avalanche, etc.",
            },
            "token_address": {
                "type": "string",
                "description": "The token contract address to inspect.",
            },
        },
        "required": ["chain", "token_address"],
    }

    def execute(self, chain: str = "", token_address: str = "") -> str:
        if not chain:
            return "Error: chain is required"
        if not token_address:
            return "Error: token_address is required"
        data = post_kittychain("/api/token/price", {"chain": chain, "tokenAddress": token_address})
        items_raw = data.get("items") or []
        rows = []
        for item in items_raw:
            rows.append({
                "price_usd": item.get("priceUsd"),
                "market_cap_usd": item.get("marketCapUsd"),
                "volume_24h_usd": item.get("volume24hUsd"),
                "price_change_24h_pct": item.get("priceChange24hPct"),
                "last_updated": item.get("lastUpdated"),
            })
        return render_text(rows)


# Backward-compatible alias
TokenMarketDataTool = TokenPriceTool


def main(chain: str = "", token_address: str = "") -> int:
    tool = TokenPriceTool()
    result = tool.execute(chain=chain, token_address=token_address)
    print(result)
    return 0 if not result.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main(chain="ethereum", token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"))
