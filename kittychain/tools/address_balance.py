"""Compute token balances and USD totals for an address across supported chains."""

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # noqa: F401
    from _kittychain_api import post_kittychain
else:
    from .base import Tool  # noqa: F401
    from ._kittychain_api import post_kittychain


def summarize_tokens_kittychain(payload: dict[str, Any]) -> dict[str, Any]:
    tokens_raw = payload.get("tokens") or []
    tokens: list[dict[str, Any]] = []
    for item in tokens_raw:
        tokens.append({
            "symbol": str(item.get("symbol") or "UNKNOWN"),
            "token_address": item.get("tokenAddress"),
            "quantity": float(item.get("quantity") or 0),
            "value_usd": float(item.get("valueUsd") or 0),
        })
    tokens.sort(key=lambda t: t["value_usd"], reverse=True)

    network_totals_raw = payload.get("networkTotals") or {}
    network_totals = {k: float(v) for k, v in network_totals_raw.items()}

    total_value_usd = float(payload.get("totalValueUsd") or 0)
    return {"tokens": tokens, "network_totals": network_totals, "total_value_usd": total_value_usd}


summarize_tokens = summarize_tokens_kittychain


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
Compute token balances and USD totals for an address across supported chains.
Before calling this tool, call address_pattern first to determine candidate chain names.
Pass those candidate chain names through the required chains field.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet address to inspect.",
            },
            "chains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required candidate chain names. Supported values: Ethereum, Solana, Arbitrum, Base, Avalanche C-Chain, BNB Chain, Blast, zkSync Era, Polygon, and more.",
            },
        },
        "required": ["address", "chains"],
    }

    _parent_agent = None

    def execute(self, address: str, chains: list[str]) -> str:
        if not address:
            raise ValueError("address is required")
        if not chains:
            raise ValueError("chains is required")
        data = post_kittychain("/api/address/balance", {"address": address, "chains": chains})
        summary = summarize_tokens_kittychain(data)
        return render_balance_text(summary)


def main(address: str, chains: list[str]) -> int:
    if not address:
        print("Error: address is required")
        return 1
    if not chains:
        print("Error: chains is required")
        return 1
    data = post_kittychain("/api/address/balance", {"address": address, "chains": chains})
    summary = summarize_tokens_kittychain(data)
    print(render_balance_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB", ["Ethereum", "Base"]))
