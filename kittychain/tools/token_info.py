"""Look up Chainbase token price, price history, and top holders."""

import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests import HTTPError

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from address_identity import normalize_address  # type: ignore
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .address_identity import normalize_address
    from .base import Tool  # noqa: F401
    from ..config import Config

TOKEN_PRICE_URL = "https://api.chainbase.online/v1/token/price"
TOKEN_PRICE_HISTORY_URL = "https://api.chainbase.online/v1/token/price/history"
TOKEN_TOP_HOLDERS_URL = "https://api.chainbase.online/v1/token/top-holders"
CHAIN_ID_DESCRIPTION = (
    "Chain network id. Use: Ethereum=1, Polygon=137, BSC=56, Avalanche=43114, "
    "Arbitrum One=42161, Optimism=10, Base=8453, zkSync=324, Merlin=4200."
)
TIME_DESCRIPTION = (
    "Unix timestamp integer used by Chainbase price history. "
    "Maps to from_timestamp/end_timestamp, for example 1704067200."
)
RATE_LIMIT_PER_SECOND = 3
MIN_REQUEST_INTERVAL_SECONDS = 1.0 / RATE_LIMIT_PER_SECOND


class ChainbaseAPIError(RuntimeError):
    """Raised when the Chainbase token APIs return an error."""


def _load_api_key() -> str:
    key = Config.from_file().apis.chainbase_api_key
    if key:
        return key
    return os.environ.get("CHAINBASE_API_KEY", "")


def _chainbase_get(
    session: Any,
    url: str,
    api_key: str,
    params: dict[str, Any],
    timeout: int = 20,
    sleep_func=time.sleep,
    max_attempts: int = 2,
) -> dict[str, Any]:
    last_error = None
    for attempt in range(1, max_attempts + 1):
        response = session.get(
            url,
            headers={"x-api-key": api_key},
            params=params,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except HTTPError as exc:
            last_error = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429 and attempt < max_attempts:
                retry_after = getattr(exc.response, "headers", {}).get("Retry-After", "1")
                try:
                    sleep_seconds = float(retry_after)
                except (TypeError, ValueError):
                    sleep_seconds = 1.0
                sleep_func(max(sleep_seconds, 1.0))
                continue
            raise
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise ChainbaseAPIError(payload.get("message") or "Chainbase token lookup failed")
        return payload
    raise ChainbaseAPIError("Chainbase token lookup failed") from last_error


def _rate_limited_get(
    session: Any,
    url: str,
    api_key: str,
    params: dict[str, Any],
    timeout: int,
    last_request_started_at: float | None,
    time_func,
    sleep_func,
) -> tuple[dict[str, Any], float]:
    if last_request_started_at is not None:
        now = time_func()
        sleep_seconds = MIN_REQUEST_INTERVAL_SECONDS - (now - last_request_started_at)
        if sleep_seconds > 0:
            sleep_func(sleep_seconds)
    started_at = time_func()
    payload = _chainbase_get(
        session,
        url,
        api_key,
        params,
        timeout=timeout,
        sleep_func=sleep_func,
    )
    return payload, started_at


def fetch_token_info(
    token_address: str,
    chain_id: int,
    start_time: int,
    end_time: int,
    api_key: str,
    session: Any | None = None,
    timeout: int = 20,
    time_func=time.time,
    sleep_func=time.sleep,
) -> dict[str, Any]:
    normalized_address = normalize_address(token_address)
    session = session or requests.Session()

    last_request_started_at: float | None = None
    current_price_payload, last_request_started_at = _rate_limited_get(
        session,
        TOKEN_PRICE_URL,
        api_key,
        {"chain_id": chain_id, "contract_address": normalized_address},
        timeout,
        last_request_started_at,
        time_func,
        sleep_func,
    )
    price_history_payload, last_request_started_at = _rate_limited_get(
        session,
        TOKEN_PRICE_HISTORY_URL,
        api_key,
        {
            "chain_id": chain_id,
            "contract_address": normalized_address,
            "from_timestamp": start_time,
            "end_timestamp": end_time,
        },
        timeout,
        last_request_started_at,
        time_func,
        sleep_func,
    )
    top_holders_payload, last_request_started_at = _rate_limited_get(
        session,
        TOKEN_TOP_HOLDERS_URL,
        api_key,
        {"chain_id": chain_id, "contract_address": normalized_address},
        timeout,
        last_request_started_at,
        time_func,
        sleep_func,
    )

    current_price = current_price_payload.get("data") or {}
    price_history = price_history_payload.get("data") or []
    top_holders = top_holders_payload.get("data") or []

    return {
        "token_address": normalized_address,
        "chain_id": int(chain_id),
        "current_price_usd": float(current_price.get("price") or 0),
        "price_history": [
            {
                "price_usd": float(item.get("price") or 0),
                "updated_at": item.get("updated_at"),
            }
            for item in price_history
        ],
        "top_holders": [
            {
                "wallet_address": item.get("wallet_address"),
                "amount": float(item.get("original_amount") or item.get("amount") or 0),
                "usd_value": float(item.get("usd_value") or 0),
            }
            for item in top_holders
        ],
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        f"Token: {summary['token_address']}",
        f"Chain ID: {summary['chain_id']}",
        f"Current price (USD): {summary['current_price_usd']:.8f}",
        "",
        "Historical prices (USD):",
    ]
    if summary["price_history"]:
        for item in summary["price_history"]:
            lines.append(f"- {item['updated_at']}: price_usd={item['price_usd']:.8f}")
    else:
        lines.append("- No historical prices found")
    lines.append("")
    lines.append("Top holders:")
    if summary["top_holders"]:
        for item in summary["top_holders"]:
            lines.append(
                f"- wallet_address={item['wallet_address']} | amount={item['amount']:.8f} | usd_value={item['usd_value']:.8f}"
            )
    else:
        lines.append("- No holder data found")
    return "\n".join(lines)


class TokenInfoTool(Tool):
    name = "token_info"
    description = """
Look up Chainbase token data for a token contract on a specific chain and time range.
Returns current price (USD), historical price points (USD), and top holders.
# Important Notes
- After calling this tool, check the top holders with address_mallicious.
- After calling this tool, always use web_fetch tool to verify the token information.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_address": {
                "type": "string",
                "description": "The token contract address to inspect.",
            },
            "chain_id": {
                "type": "integer",
                "description": CHAIN_ID_DESCRIPTION,
            },
            "start_time": {
                "type": "integer",
                "description": f"{TIME_DESCRIPTION} This value is sent as from_timestamp.",
            },
            "end_time": {
                "type": "integer",
                "description": f"{TIME_DESCRIPTION} This value is sent as end_timestamp and the interval should not exceed 90 days.",
            },
        },
        "required": ["token_address", "chain_id", "start_time", "end_time"],
    }

    _parent_agent = None

    def execute(self, token_address: str, chain_id: int, start_time: int, end_time: int) -> str:
        api_key = _load_api_key()
        if not api_key:
            raise ValueError("CHAINBASE_API_KEY is required")
        summary = fetch_token_info(token_address, chain_id, start_time, end_time, api_key)
        return render_text(summary)


def main(token_address: str, chain_id: int, start_time: int, end_time: int) -> int:
    if not token_address:
        print("Error: token_address is required")
        return 1
    api_key = _load_api_key()
    if not api_key:
        print("Error: CHAINBASE_API_KEY is required")
        return 1
    summary = fetch_token_info(token_address, chain_id, start_time, end_time, api_key)
    print(render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
            1704067200,
            1704153600,
        )
    )
