"""Look up CoinGecko token detail data by token name or symbol."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COINGECKO_SEARCH_URL = "https://api.coingecko.com/api/v3/search"
COINGECKO_COIN_URL_TEMPLATE = "https://api.coingecko.com/api/v3/coins/{token_id}"
_USER_AGENT = "KittyChain token_data/1.0"

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from config import Config
else:
    from .base import Tool
    from ..config import Config


def _load_coingecko_api_key() -> str:
    return Config.from_file().apis.coingecko_api_key


def _normalize_query_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _request_headers(api_key: str) -> dict[str, str]:
    return {
        "x-cg-demo-api-key": api_key,
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }


def _match_search_coin(coin: dict[str, Any], token_name: str | None, token_symbol: str | None) -> tuple[int, int]:
    score = 0
    rank = coin.get("market_cap_rank")
    normalized_rank = rank if isinstance(rank, int) else 10**9
    if token_name is not None and str(coin.get("name") or "").strip().casefold() == token_name.casefold():
        score += 2
    if token_symbol is not None and str(coin.get("symbol") or "").strip().casefold() == token_symbol.casefold():
        score += 2
    return score, normalized_rank


def _select_token_id(payload: Any, token_name: str | None, token_symbol: str | None) -> str:
    coins = payload.get("coins") if isinstance(payload, dict) else None
    if not isinstance(coins, list):
        raise ValueError("CoinGecko search response must include a coins array")

    best_id = ""
    best_score = -1
    best_rank = 10**9
    fallback_id = ""
    for item in coins:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("id") or "").strip()
        if not token_id:
            continue
        if not fallback_id:
            fallback_id = token_id
        score, rank = _match_search_coin(item, token_name, token_symbol)
        if score > best_score or (score == best_score and rank < best_rank):
            best_id = token_id
            best_score = score
            best_rank = rank

    if best_id:
        return best_id
    if fallback_id:
        return fallback_id
    raise ValueError("No matching token found")


def fetch_token_data(
    token_name: str | None,
    token_symbol: str | None,
    api_key: str,
    session: Any | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    normalized_name = _normalize_query_value(token_name)
    normalized_symbol = _normalize_query_value(token_symbol)
    if normalized_name is None and normalized_symbol is None:
        raise ValueError("token_name or token_symbol is required")

    session = session or requests.Session()
    search_response = session.get(
        COINGECKO_SEARCH_URL,
        params={"query": normalized_name or normalized_symbol},
        timeout=timeout,
        headers=_request_headers(api_key),
    )
    search_response.raise_for_status()
    token_id = _select_token_id(search_response.json(), normalized_name, normalized_symbol)

    details_response = session.get(
        COINGECKO_COIN_URL_TEMPLATE.format(token_id=quote(token_id, safe="")),
        params={
            "localization": "false",
            "tickers": "true",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "true",
            "sparkline": "false",
            "include_categories_details": "false",
            "dex_pair_format": "contract_address",
        },
        timeout=timeout,
        headers=_request_headers(api_key),
    )
    details_response.raise_for_status()
    payload = details_response.json()
    if not isinstance(payload, dict):
        raise ValueError("CoinGecko coins/{id} response must be a JSON object")
    return payload


def _collect_link_values(label: str, value: Any) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            results.append((label, normalized))
        elif label == "twitter_screen_name" and normalized:
            results.append((label, f"https://twitter.com/{normalized.lstrip('@')}"))
        elif label == "facebook_username" and normalized:
            results.append((label, f"https://facebook.com/{normalized}"))
        elif label == "telegram_channel_identifier" and normalized:
            results.append((label, f"https://t.me/{normalized.lstrip('@')}"))
        return results

    if isinstance(value, list):
        for item in value:
            results.extend(_collect_link_values(label, item))
        return results

    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_label = f"{label}.{key}"
            results.extend(_collect_link_values(nested_label, nested_value))
        return results

    return results


def _extract_links(links: Any) -> list[tuple[str, str]]:
    if not isinstance(links, dict):
        return []

    seen: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []
    for label, value in links.items():
        for item in _collect_link_values(str(label), value):
            if item in seen:
                continue
            seen.add(item)
            results.append(item)
    return results


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _market_name(ticker: Any) -> str:
    market = ticker.get("market") if isinstance(ticker, dict) else None
    if not isinstance(market, dict):
        return ""
    return str(market.get("name") or "").strip()


def _usdt_ticker_rows(tickers: Any) -> list[dict[str, Any]]:
    if not isinstance(tickers, list):
        return []

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        if not isinstance(ticker, dict):
            continue
        if str(ticker.get("target") or "").strip().upper() != "USDT":
            continue
        rows.append(
            {
                "market_name": _market_name(ticker),
                "base": str(ticker.get("base") or "").strip(),
                "target": str(ticker.get("target") or "").strip(),
                "converted_last_usd": _safe_float((ticker.get("converted_last") or {}).get("usd")),
                "converted_volume_usd": _safe_float((ticker.get("converted_volume") or {}).get("usd")),
                "bid_ask_spread_percentage": _safe_float(ticker.get("bid_ask_spread_percentage")),
                "coin_mcap_usd": _safe_float(ticker.get("coin_mcap_usd")),
            }
        )
    return rows


def _listing_markets(tickers: Any) -> list[str]:
    if not isinstance(tickers, list):
        return []
    seen: set[str] = set()
    markets: list[str] = []
    for ticker in tickers:
        name = _market_name(ticker)
        if not name or name in seen:
            continue
        seen.add(name)
        markets.append(name)
    return markets


def _summarize_usdt_tickers(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    last_sum = sum(row["converted_last_usd"] for row in rows)
    volume_sum = sum(row["converted_volume_usd"] for row in rows)
    mcap_sum = sum(row["coin_mcap_usd"] for row in rows)
    if volume_sum > 0:
        spread_weighted_avg = sum(row["bid_ask_spread_percentage"] * row["converted_volume_usd"] for row in rows) / volume_sum
    else:
        spread_weighted_avg = None
    return {
        "converted_last_usd_sum": last_sum,
        "converted_volume_usd_sum": volume_sum,
        "bid_ask_spread_percentage_weighted_avg": spread_weighted_avg,
        "coin_mcap_usd_sum": mcap_sum,
    }


def render_text(payload: dict[str, Any]) -> str:
    name = payload.get("name")
    symbol = payload.get("symbol")
    categories = payload.get("categories")
    links = _extract_links(payload.get("links"))
    listing_markets = _listing_markets(payload.get("tickers"))
    usdt_rows = _usdt_ticker_rows(payload.get("tickers"))
    usdt_summary = _summarize_usdt_tickers(usdt_rows)

    category_text = ", ".join(str(item) for item in categories) if isinstance(categories, list) and categories else "-"
    listing_market_text = ", ".join(listing_markets) if listing_markets else "-"

    lines = [
        f"Token data: {name} ({symbol})",
        f"id: {payload.get('id')}",
        f"categories: {category_text}",
        "links:",
    ]
    if links:
        for label, url in links:
            lines.append(f"- {label}: {url}")
    else:
        lines.append("- -")

    lines.extend(
        [
            f"market_cap_rank: {payload.get('market_cap_rank')}",
            f"market_cap_rank_with_rehypothecated: {payload.get('market_cap_rank_with_rehypothecated')}",
            f"developer_data: {json.dumps(payload.get('developer_data') or {}, ensure_ascii=False, sort_keys=True)}",
            f"listing_markets: {listing_market_text}",
            "usdt_tickers_summary:",
            f"- converted_last.usd_sum: {usdt_summary['converted_last_usd_sum']}",
            f"- converted_volume.usd_sum: {usdt_summary['converted_volume_usd_sum']}",
            f"- bid_ask_spread_percentage_weighted_avg: {usdt_summary['bid_ask_spread_percentage_weighted_avg']}",
            f"- coin_mcap_usd_sum: {usdt_summary['coin_mcap_usd_sum']}",
            "usdt_tickers_details:",
        ]
    )

    if usdt_rows:
        for index, row in enumerate(usdt_rows, start=1):
            pair = f"{row['base']}/{row['target']}".strip("/")
            lines.extend(
                [
                    f"{index}. {row['market_name']} {pair}".rstrip(),
                    f"   converted_last.usd: {row['converted_last_usd']}",
                    f"   converted_volume.usd: {row['converted_volume_usd']}",
                    f"   bid_ask_spread_percentage: {row['bid_ask_spread_percentage']}",
                    f"   coin_mcap_usd: {row['coin_mcap_usd']}",
                ]
            )
    else:
        lines.append("- No USDT tickers found")

    return "\n".join(lines)


class TokenDataTool(Tool):
    name = "token_data"
    description = """
Look up CoinGecko token detail data by token name or symbol.
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
        api_key = _load_coingecko_api_key()
        if not api_key:
            raise ValueError("COINGECKO_API_KEY is required")
        return render_text(fetch_token_data(normalized_name, normalized_symbol, api_key))


def main(token_name: str = "", token_symbol: str = "") -> int:
    normalized_name = _normalize_query_value(token_name)
    normalized_symbol = _normalize_query_value(token_symbol)
    if normalized_name is None and normalized_symbol is None:
        print("Error: token_name or token_symbol is required")
        return 1
    api_key = _load_coingecko_api_key()
    if not api_key:
        print("Error: COINGECKO_API_KEY is required")
        return 1
    print(render_text(fetch_token_data(normalized_name, normalized_symbol, api_key)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(token_symbol="btc"))
