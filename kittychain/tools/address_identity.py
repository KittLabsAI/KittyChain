"""Look up ENS identity and exchange attribution for addresses via KittyChain API."""

import re
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

ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def normalize_address(address: str) -> str:
    normalized = address.strip().lower()
    if not ADDRESS_PATTERN.fullmatch(normalized):
        raise ValueError("address must be a 42-character 0x-prefixed hex string")
    return normalized


def parse_addresses(addresses: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(addresses, str):
        raw_items = [item for item in re.split(r"[\s,]+", addresses.strip()) if item]
    else:
        raw_items = [str(item).strip() for item in addresses if str(item).strip()]
    if not raw_items:
        raise ValueError("at least one address is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        address = normalize_address(item)
        if address not in seen:
            seen.add(address)
            normalized.append(address)
    return normalized


def render_text(summary: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(summary, list):
        return "\n\n".join(render_text(item) for item in summary)

    identity = summary["identity"]
    exchange = summary["exchange"]
    lines = [f"Address: {summary['address']}", ""]
    lines.append("Identity:")
    if identity["found"]:
        for row in identity["rows"]:
            parts = [row.get("name") or "unknown-name", row.get("blockchain") or "unknown-chain"]
            if row.get("source"):
                parts.append(f"source={row['source']}")
            if row.get("category"):
                parts.append(f"category={row['category']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- No ENS/identity rows found")
    lines.append("")
    lines.append("Exchange ownership:")
    if exchange["is_exchange"]:
        for row in exchange["address_rows"]:
            parts = [row.get("cex_name") or "unknown-cex", row.get("blockchain") or "unknown-chain"]
            if row.get("distinct_name"):
                parts.append(f"label={row['distinct_name']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- Not found in cex.addresses")
    lines.append("")
    lines.append("User deposit address for exchanges:")
    if exchange["is_deposit_address"]:
        for row in exchange["deposit_rows"]:
            parts = [row.get("cex_name") or "unknown-cex", row.get("blockchain") or "unknown-chain"]
            if row.get("deposit_count") is not None:
                parts.append(f"deposit_count={row['deposit_count']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- Not found in cex.deposit_addresses")
    return "\n".join(lines)


def _map_item(item: dict[str, Any]) -> dict[str, Any]:
    address = item.get("address", "")
    identity_raw = item.get("identity") or {}
    exchange_raw = item.get("exchange") or {}

    identity_rows = []
    for row in identity_raw.get("rows") or []:
        identity_rows.append({
            "blockchain": row.get("blockchain"),
            "name": row.get("name"),
            "category": row.get("category"),
            "source": row.get("source"),
            "label_type": row.get("labelType"),
        })

    address_rows = []
    for row in exchange_raw.get("addressRows") or []:
        address_rows.append({
            "blockchain": row.get("blockchain"),
            "cex_name": row.get("cexName"),
            "distinct_name": row.get("distinctName"),
            "added_by": row.get("addedBy"),
            "added_date": row.get("addedDate"),
        })

    deposit_rows = []
    for row in exchange_raw.get("depositRows") or []:
        deposit_rows.append({
            "blockchain": row.get("blockchain"),
            "cex_name": row.get("cexName"),
            "deposit_count": row.get("depositCount"),
            "first_deposit_token_standard": row.get("firstDepositTokenStandard"),
            "first_deposit_token_address": row.get("firstDepositTokenAddress"),
            "deposit_first_block_time": row.get("depositFirstBlockTime"),
            "consolidation_first_block_time": row.get("consolidationFirstBlockTime"),
            "amount_deposited": row.get("amountDeposited"),
        })

    return {
        "address": address,
        "identity": {"found": identity_raw.get("found", False), "rows": identity_rows},
        "exchange": {
            "is_exchange": exchange_raw.get("isExchange", False),
            "address_rows": address_rows,
            "is_deposit_address": exchange_raw.get("isDepositAddress", False),
            "deposit_rows": deposit_rows,
        },
    }


class AddressIdentityTool(Tool):
    name = "address_identity"
    description = """
Look up ENS identity and exchange attribution for addresses via KittyChain API.
Returns identity labels (ENS names), exchange ownership, and user deposit addresses.
# Important Notes
- Always use ask_user to confirm whether to run this tool and remind the user it may take longer.
- This lookup can be slow (比较慢), especially for multiple addresses, and is useful for checking ENS and CEX attribution.
- After calling this tool, use address_malicious and web_fetch to look up the address on https://www.oklink.com/ to verify the result.
    """
    parameters = {
        "type": "object",
        "properties": {
            "addresses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "EVM address array. Must contain 1 to 10 items.",
            },
        },
        "required": ["addresses"],
    }

    _parent_agent = None

    def execute(self, addresses: list[str]) -> str:
        if not addresses:
            raise ValueError("addresses is required")
        if len(addresses) > 10:
            raise ValueError("maximum 10 addresses allowed")
        normalized = [normalize_address(a) for a in addresses]
        data = post_kittychain("/api/address/identity", {"addresses": normalized})
        items_raw = data.get("items") or []
        summaries = [_map_item(item) for item in items_raw]
        if len(summaries) == 1:
            return render_text(summaries[0])
        return render_text(summaries)


def main(addresses: list[str]) -> int:
    if not addresses:
        print("Error: addresses is required")
        return 1
    tool = AddressIdentityTool()
    print(tool.execute(addresses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(["0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"]))
