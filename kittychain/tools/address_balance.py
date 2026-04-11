"""Compute token balances and USD totals for an address across default Alchemy networks."""

import argparse
import json
import os
import ssl
import sys
from collections import defaultdict
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .base import Tool  # noqa: F401
    from ..config import Config

DATA_API_BASE = "https://api.g.alchemy.com/data/v1"
getcontext().prec = 50
DEFAULT_NETWORKS = [
    "eth-mainnet",
    "solana-mainnet",
    "arb-mainnet",
    "base-mainnet",
    "avax-mainnet",
    "bnb-mainnet",
    "blast-mainnet",
    "zksync-mainnet",
    "polygon-mainnet",
]


class AlchemyAPIError(RuntimeError):
    pass


def _load_api_key() -> str:
    key = Config.from_file().apis.alchemy_api_key
    if key:
        return key
    return os.environ.get("ALCHEMY_API_KEY", "")


def _build_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, context=_build_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AlchemyAPIError(f"HTTP {exc.code} calling {url}: {body}") from exc
    except URLError as exc:
        raise AlchemyAPIError(f"Network error calling {url}: {exc.reason}") from exc


def get_tokens_by_wallet(
    api_key: str,
    address: str,
    networks: list[str],
    with_metadata: bool = True,
    with_prices: bool = True,
    include_native_tokens: bool = True,
    include_erc20_tokens: bool = True,
) -> dict[str, Any]:
    url = f"{DATA_API_BASE}/{api_key}/assets/tokens/by-address"
    payload = {
        "addresses": [{"address": address, "networks": networks}],
        "withMetadata": with_metadata,
        "withPrices": with_prices,
        "includeNativeTokens": include_native_tokens,
        "includeErc20Tokens": include_erc20_tokens,
    }
    return _post_json(url, payload)


def summarize_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    tokens = payload.get("data", {}).get("tokens", [])
    grouped: dict[str, dict[str, Decimal | str | None]] = defaultdict(
        lambda: {"symbol": "", "token_address": None, "quantity": Decimal("0"), "value_usd": Decimal("0")}
    )
    network_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for token in tokens:
        metadata = token.get("tokenMetadata") or {}
        network = token.get("network") or "unknown-network"
        token_address = token.get("tokenAddress")
        symbol = metadata.get("symbol")
        decimals = metadata.get("decimals")
        if decimals is None:
            decimals = 18
        display_symbol = symbol or f"UNKNOWN@{network}"
        group_key = symbol or f"{network}:{token_address or 'native'}"
        price_items = token.get("tokenPrices") or []
        if not price_items:
            continue
        price_value = price_items[0].get("value")
        if price_value is None:
            continue
        raw_balance = token.get("tokenBalance") or "0x0"
        quantity = Decimal(int(raw_balance, 16)) / (Decimal(10) ** int(decimals))
        value_usd = quantity * Decimal(str(price_value))
        entry = grouped[group_key]
        entry["symbol"] = display_symbol
        existing_token_address = entry["token_address"]
        if existing_token_address is None:
            entry["token_address"] = token_address
        elif token_address != existing_token_address:
            entry["token_address"] = None
        entry["quantity"] = Decimal(entry["quantity"]) + quantity
        entry["value_usd"] = Decimal(entry["value_usd"]) + value_usd
        network_totals[network] += value_usd
    summarized_tokens = sorted(
        (
            {
                "symbol": entry["symbol"],
                "token_address": entry["token_address"],
                "quantity": float(entry["quantity"]),
                "value_usd": float(entry["value_usd"]),
            }
            for entry in grouped.values()
            if Decimal(entry["quantity"]) != 0 and Decimal(entry["value_usd"]) != 0
        ),
        key=lambda item: item["value_usd"],
        reverse=True,
    )
    total_value_usd = round(sum(item["value_usd"] for item in summarized_tokens), 8)
    summarized_networks = {
        network: round(float(value), 8)
        for network, value in sorted(network_totals.items(), key=lambda item: item[1], reverse=True)
        if value != 0
    }
    return {"tokens": summarized_tokens, "network_totals": summarized_networks, "total_value_usd": total_value_usd}


def render_balance_text(summary: dict[str, Any]) -> str:
    lines = ["Token balances:"]
    if summary["tokens"]:
        for item in summary["tokens"]:
            token_address_text = f", tokenAddress={item['token_address']}" if item.get("token_address") else ""
            lines.append(
                f"- {item['symbol']}{token_address_text}: quantity={item['quantity']:.8f}, value_usd={item['value_usd']:.8f}"
            )
    else:
        lines.append("- No non-zero token balances with non-zero USD value were found")
    lines.append("")
    lines.append("Network totals:")
    if summary.get("network_totals"):
        for network, value in summary["network_totals"].items():
            lines.append(f"- {network}: value_usd={value:.8f}")
    else:
        lines.append("- No network totals available")
    lines.append("")
    lines.append(f"Total portfolio value (USD): {summary['total_value_usd']:.8f}")
    return "\n".join(lines)


class AddressBalanceTool(Tool):
    name = "address_balance"
    description = """
Compute token balances and USD totals for an address across default Alchemy networks.
Supports ETH, SOL, ARB, BASE, AVAX, BNB, BLAST, ZKSYNC, and Polygon.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet address to inspect.",
            },
        },
        "required": ["address"],
    }

    _parent_agent = None

    def execute(self, address: str) -> str:
        if not address:
            raise ValueError("address is required")
        api_key = _load_api_key()
        if not api_key:
            raise ValueError("ALCHEMY_API_KEY is required")
        payload = get_tokens_by_wallet(api_key=api_key, address=address, networks=DEFAULT_NETWORKS)
        summary = summarize_tokens(payload)
        return render_balance_text(summary)


def main(address: str) -> int:
    if not address:
        print("Error: address is required")
        return 1
    api_key = _load_api_key()
    if not api_key:
        print("Error: ALCHEMY_API_KEY is required")
        return 1
    payload = get_tokens_by_wallet(api_key=api_key, address=address, networks=DEFAULT_NETWORKS)
    summary = summarize_tokens(payload)
    print(render_balance_text(summary))
    return 0


if __name__ == "__main__":
    address = "0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"
    raise SystemExit(main(address))
