"""Get token transfer totals by address via KittyChain API."""

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


def render_transfers_text(summary: dict[str, Any]) -> str:
    lines = [f"Address: {summary['address']}", "", "Aggregated counterparties:"]
    if summary["items"]:
        for item in summary["items"]:
            lines.append(
                f"- network={item['network']}, direction={item['direction']}, counterparty={item['counterparty']}, "
                f"asset={item['asset']}, total_value={item['total_value']:.8f}, "
                f"first={item['first_timestamp']}, last={item['last_timestamp']}"
            )
    else:
        lines.append("- No transfers found")
    if summary.get("skipped_networks"):
        lines.append("")
        lines.append("Skipped networks:")
        for item in summary["skipped_networks"]:
            lines.append(f"- {item['network']}: {item['reason']}")
    return "\n".join(lines)


def _map_response(data: dict[str, Any]) -> dict[str, Any]:
    items_raw = data.get("items") or []
    items = []
    for item in items_raw:
        items.append({
            "network": item.get("network"),
            "direction": item.get("direction"),
            "counterparty": item.get("counterparty"),
            "asset": item.get("asset"),
            "total_value": float(item.get("totalValue") or 0),
            "first_timestamp": item.get("firstTimestamp"),
            "last_timestamp": item.get("lastTimestamp"),
        })

    skipped_raw = data.get("skippedNetworks") or []
    skipped = []
    for item in skipped_raw:
        if isinstance(item, dict):
            skipped.append({"network": item.get("network"), "reason": item.get("reason")})

    return {
        "address": data.get("address", ""),
        "items": items,
        "skipped_networks": skipped,
    }


class AddressTransfersTool(Tool):
    name = "address_transfers"
    description = """
Get token transfer totals by address via KittyChain API.
Before calling this tool, call address_pattern first to determine candidate chain names.
Pass those candidate chain names through the required chains field.
Returns aggregated transfer data grouped by network, direction, counterparty, and asset.
# Important Notes
- After calling this tool, inspect the 3-5 most frequent counterparties and check each one with address_malicious.
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
                "description": "Required candidate chain names. Supported values: Ethereum, Arbitrum, Base, Avalanche C-Chain, BNB Chain, Blast, zkSync Era, Polygon, and more.",
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
        data = post_kittychain("/api/address/transfers", {"address": address, "chains": chains})
        summary = _map_response(data)
        return render_transfers_text(summary)


def main(address: str, chains: list[str]) -> int:
    if not address:
        print("Error: address is required")
        return 1
    if not chains:
        print("Error: chains is required")
        return 1
    tool = AddressTransfersTool()
    print(tool.execute(address, chains))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB", ["Base"]))
