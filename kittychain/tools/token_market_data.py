"""Look up CoinGecko market data for tokens by name or symbol."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COINGECKO_COINS_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
_USER_AGENT = "KittyChain token_market_data/1.0"

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from config import Config
else:
    from .base import Tool
    from ..config import Config


def _load_coingecko_api_key() -> str:
    return Config.from_file().apis.coingecko_api_key


def _normalize_items(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        item = str(value).strip()
        if item:
            normalized.append(item)
    return normalized


def fetch_token_market_data(
    token_names: list[str] | None,
    token_symbols: list[str] | None,
    api_key: str,
    session: Any | None = None,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    names = _normalize_items(token_names)
    symbols = _normalize_items(token_symbols)
    if not names and not symbols:
        raise ValueError("token_names or token_symbols is required")

    params: dict[str, str] = {"vs_currency": "usd"}
    if names:
        params["names"] = ",".join(names)
    if symbols:
        params["symbols"] = ",".join(symbols)
        params["include_tokens"] = "all"

    session = session or requests.Session()
    response = session.get(
        COINGECKO_COINS_MARKETS_URL,
        params=params,
        timeout=timeout,
        headers={
            "x-cg-demo-api-key": api_key,
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("CoinGecko coins/markets response must be a JSON array")
    results: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "id": item.get("id"),
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "current_price": item.get("current_price"),
                "market_cap": item.get("market_cap"),
                "market_cap_rank": item.get("market_cap_rank"),
                "fully_diluted_valuation": item.get("fully_diluted_valuation"),
                "total_volume": item.get("total_volume"),
                "last_updated": item.get("last_updated"),
            }
        )
    return results


def render_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Token market data results:\n- No matching tokens found"

    lines = ["Token market data results:"]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                "",
                f"{index}. {row.get('name')} ({row.get('symbol')})",
                f"   id: {row.get('id')}",
                f"   current_price: {row.get('current_price')}",
                f"   market_cap: {row.get('market_cap')}",
                f"   market_cap_rank: {row.get('market_cap_rank')}",
                f"   fully_diluted_valuation: {row.get('fully_diluted_valuation')}",
                f"   total_volume: {row.get('total_volume')}",
                f"   last_updated: {row.get('last_updated')}",
            ]
        )
    return "\n".join(lines)


class TokenMarketDataTool(Tool):
    name = "token_market_data"
    description = """
Look up CoinGecko token market data by token names or token symbols.
Returns market cap, volume, price, rank, FDV, and last update time.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional token names to look up, for example ['USD Coin'].",
            },
            "token_symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional token symbols to look up, for example ['USDC'].",
            },
        },
    }

    def execute(self, token_names: list[str] | None = None, token_symbols: list[str] | None = None) -> str:
        if not _normalize_items(token_names) and not _normalize_items(token_symbols):
            return "Error: token_names or token_symbols is required"
        api_key = _load_coingecko_api_key()
        if not api_key:
            raise ValueError("COINGECKO_API_KEY is required")
        rows = fetch_token_market_data(token_names, token_symbols, api_key)
        return render_text(rows)


def main(token_names: list[str] | None = None, token_symbols: list[str] | None = None) -> int:
    if not _normalize_items(token_names) and not _normalize_items(token_symbols):
        print("Error: token_names or token_symbols is required")
        return 1
    api_key = _load_coingecko_api_key()
    if not api_key:
        print("Error: COINGECKO_API_KEY is required")
        return 1
    print(render_text(fetch_token_market_data(token_names, token_symbols, api_key)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(token_symbols=["sfund"]))
