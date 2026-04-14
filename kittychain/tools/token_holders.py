"""Look up Chainbase token top holders."""

import os
import sys
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

TOKEN_TOP_HOLDERS_URL = "https://api.chainbase.online/v1/token/top-holders"
CHAIN_ID_DESCRIPTION = (
    "Chain network id. Use: Ethereum=1, Polygon=137, BSC=56, Avalanche=43114, "
    "Arbitrum One=42161, Optimism=10, Base=8453, zkSync=324, Merlin=4200."
)


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
                import time

                time.sleep(max(sleep_seconds, 1.0))
                continue
            raise
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise ChainbaseAPIError(payload.get("message") or "Chainbase token lookup failed")
        return payload
    raise ChainbaseAPIError("Chainbase token lookup failed") from last_error


def fetch_token_holders(
    token_address: str,
    chain_id: int,
    api_key: str,
    session: Any | None = None,
    timeout: int = 20,
    time_func=None,
    sleep_func=None,
) -> dict[str, Any]:
    normalized_address = normalize_address(token_address)
    session = session or requests.Session()
    del time_func, sleep_func

    top_holders_payload = _chainbase_get(
        session,
        TOKEN_TOP_HOLDERS_URL,
        api_key,
        {"chain_id": chain_id, "contract_address": normalized_address},
        timeout=timeout,
    )

    top_holders = top_holders_payload.get("data") or []

    return {
        "token_address": normalized_address,
        "chain_id": int(chain_id),
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
        "",
        "Top holders:",
    ]
    if summary["top_holders"]:
        for item in summary["top_holders"]:
            lines.append(
                f"- wallet_address={item['wallet_address']} | amount={item['amount']:.8f} | usd_value={item['usd_value']:.8f}"
            )
    else:
        lines.append("- No holder data found")
    return "\n".join(lines)


class TokenHoldersTool(Tool):
    name = "token_holders"
    description = """
Look up Chainbase token top holders for a token contract on a specific chain.
Returns top holders and holder amounts for the token contract.
# Important Notes
- After calling this tool, check the top holders with address_malicious.
- After calling this tool, always use web_browser tool to verify the holder information.
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
        },
        "required": ["token_address", "chain_id"],
    }

    _parent_agent = None

    def execute(self, token_address: str, chain_id: int) -> str:
        api_key = _load_api_key()
        if not api_key:
            raise ValueError("CHAINBASE_API_KEY is required")
        summary = fetch_token_holders(token_address, chain_id, api_key)
        return render_text(summary)


def main(token_address: str, chain_id: int) -> int:
    if not token_address:
        print("Error: token_address is required")
        return 1
    api_key = _load_api_key()
    if not api_key:
        print("Error: CHAINBASE_API_KEY is required")
        return 1
    summary = fetch_token_holders(token_address, chain_id, api_key)
    print(render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
        )
    )
