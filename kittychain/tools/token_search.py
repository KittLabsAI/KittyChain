"""Search token candidates from cached CoinGecko token lists."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_LIST_PATH = PROJECT_ROOT / "tools" / "data" / "token_list.json"
COINGECKO_COINS_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
_USER_AGENT = "KittyChain token_search/1.0"
_CACHE_REFRESH_SECONDS = 24 * 60 * 60
_CACHE_DEXSCREENER_FALLBACK_SECONDS = 7 * 24 * 60 * 60

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
    from config import Config
else:
    from .base import Tool
    from ..config import Config


def _normalize_query_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_match_value(value: str | None) -> str | None:
    normalized = _normalize_query_value(value)
    if normalized is None:
        return None
    return normalized.casefold()


def _load_coingecko_api_key() -> str:
    return Config.from_file().apis.coingecko_api_key


def _cache_age_seconds(path: Path, now: float) -> float | None:
    if not path.exists():
        return None
    return max(0.0, now - path.stat().st_mtime)


def _read_token_list_cache(path: Path = TOKEN_LIST_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def _write_token_list_cache(items: list[dict[str, Any]], path: Path = TOKEN_LIST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2) + "\n")


def _refresh_token_list_cache(api_key: str, session: Any | None = None, timeout: int = 20) -> list[dict[str, Any]]:
    session = session or requests.Session()
    response = session.get(
        COINGECKO_COINS_LIST_URL,
        params={"include_platform": "true"},
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
        raise ValueError("CoinGecko coins/list response must be a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def _matches_token(token: dict[str, Any], token_symbol: str | None, token_name: str | None) -> bool:
    symbol = _normalize_match_value(str(token.get("symbol") or ""))
    name = _normalize_match_value(str(token.get("name") or ""))
    return (token_symbol is not None and symbol == token_symbol) or (token_name is not None and name == token_name)


def _normalize_platforms(platforms: Any) -> dict[str, str]:
    if not isinstance(platforms, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in platforms.items():
        platform_key = str(key or "").strip()
        address = str(value or "").strip()
        if platform_key and address:
            result[platform_key] = address
    return result


def _search_cached_tokens(items: list[dict[str, Any]], token_symbol: str | None, token_name: str | None) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in items:
        if not _matches_token(item, token_symbol, token_name):
            continue
        matches.append(
            {
                "id": str(item.get("id") or "").strip(),
                "symbol": str(item.get("symbol") or "").strip(),
                "name": str(item.get("name") or "").strip(),
                "platforms": _normalize_platforms(item.get("platforms")),
            }
        )
    return matches


def _search_dexscreener(
    token_symbol: str | None,
    token_name: str | None,
    session: Any | None = None,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    query = token_symbol or token_name
    if query is None:
        return []

    session = session or requests.Session()
    response = session.get(
        DEXSCREENER_SEARCH_URL,
        params={"q": query},
        timeout=timeout,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()

    grouped: dict[str, dict[str, Any]] = {}
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        base_token = pair.get("baseToken") or {}
        if not isinstance(base_token, dict) or not _matches_token(base_token, token_symbol, token_name):
            continue
        address = str(base_token.get("address") or "").strip()
        chain = str(pair.get("chainId") or "").strip()
        if not address or not chain:
            continue
        item = grouped.setdefault(
            address,
            {
                "id": address,
                "symbol": str(base_token.get("symbol") or "").strip(),
                "name": str(base_token.get("name") or "").strip(),
                "platforms": {},
            },
        )
        item["platforms"][chain] = address
    return list(grouped.values())


def fetch_token_search(
    token_symbol: str | None,
    token_name: str | None,
    session: Any | None = None,
    timeout: int = 20,
    now: float | None = None,
) -> list[dict[str, Any]]:
    normalized_symbol = _normalize_match_value(token_symbol)
    normalized_name = _normalize_match_value(token_name)
    if normalized_symbol is None and normalized_name is None:
        raise ValueError("token_symbol or token_name is required")

    session = session or requests.Session()
    current_time = time.time() if now is None else now
    cache_age = _cache_age_seconds(TOKEN_LIST_PATH, current_time)
    api_key = _load_coingecko_api_key()

    if api_key and (cache_age is None or cache_age > _CACHE_REFRESH_SECONDS):
        items = _refresh_token_list_cache(api_key, session=session, timeout=timeout)
        _write_token_list_cache(items, TOKEN_LIST_PATH)
        return _search_cached_tokens(items, normalized_symbol, normalized_name)

    if cache_age is not None and cache_age <= _CACHE_DEXSCREENER_FALLBACK_SECONDS:
        return _search_cached_tokens(_read_token_list_cache(TOKEN_LIST_PATH), normalized_symbol, normalized_name)

    if api_key:
        return _search_cached_tokens(_read_token_list_cache(TOKEN_LIST_PATH), normalized_symbol, normalized_name)

    return _search_dexscreener(normalized_symbol, normalized_name, session=session, timeout=timeout)


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
Search token candidates by token symbol or token name.
Uses the local CoinGecko token cache first and refreshes it when stale.
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
        return render_text(fetch_token_search(normalized_symbol, normalized_name))


def main(token_symbol: str = "", token_name: str = "") -> int:
    normalized_symbol = _normalize_query_value(token_symbol)
    normalized_name = _normalize_query_value(token_name)
    if normalized_symbol is None and normalized_name is None:
        print("Error: token_symbol or token_name is required")
        return 1
    print(render_text(fetch_token_search(normalized_symbol, normalized_name)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("FITFI", ""))
