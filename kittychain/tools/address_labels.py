"""Look up address labels via KittyChain API."""

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from address_identity import parse_addresses  # type: ignore
    from base import Tool  # noqa: F401
    from _kittychain_api import post_kittychain
else:
    from .address_identity import parse_addresses
    from .base import Tool  # noqa: F401
    from ._kittychain_api import post_kittychain


def render_text(summary: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(summary, list):
        return "\n\n".join(render_text(item) for item in summary)

    lines = [f"Address: {summary['address']}", "", "Labels:"]
    if summary["labels"]:
        for item in summary["labels"]:
            tag_text = ", ".join(item["tags"]) if item["tags"] else "none"
            lines.append(f"- category={item['category']} | tags={tag_text}")
    else:
        lines.append("- No labels found")
    return "\n".join(lines)


def _map_items(data: dict[str, Any], addresses: list[str]) -> list[dict[str, Any]]:
    items_raw = data.get("items") or []
    by_address: dict[str, list[dict[str, Any]]] = {}
    for item in items_raw:
        addr = str(item.get("address") or "").lower()
        labels = []
        for label in item.get("labels") or []:
            labels.append({
                "category": str(label.get("category") or ""),
                "tags": [str(t) for t in (label.get("tags") or [])],
            })
        by_address[addr] = labels

    results = []
    for addr in addresses:
        labels = sorted(by_address.get(addr.lower(), []), key=lambda x: (x["category"], x["tags"]))
        results.append({"address": addr, "labels": labels})
    return results


class AddressLabelsTool(Tool):
    name = "address_labels"
    description = """
Look up address labels for one or more EVM addresses via KittyChain API.
Before calling this tool, call address_pattern first to determine candidate chain names.
Pass those candidate chain names through the required chains field.
Returns label category and tags aggregated across the selected supported chains.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "One or more EVM addresses, separated by commas or whitespace.",
            },
            "chains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required candidate chain names. Supported values: Ethereum, Polygon, BNB Chain, Arbitrum, Optimism, Base, and more.",
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
        normalized = parse_addresses(address)
        data = post_kittychain("/api/address/labels", {"address": address, "chains": chains})
        print("Raw API response:", data)
        summaries = _map_items(data, normalized)
        if len(summaries) == 1:
            return render_text(summaries[0])
        return render_text(summaries)


def main(address: str, chains: list[str]) -> int:
    if not address:
        print("Error: address is required")
        return 1
    if not chains:
        print("Error: chains is required")
        return 1
    tool = AddressLabelsTool()
    print(tool.execute(address, chains))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0x28c6c06298d514db089934071355e5743bf21d60", ["Ethereum", "Base"]))
