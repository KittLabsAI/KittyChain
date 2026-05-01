"""Look up transaction detail via KittyChain API."""

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


def render_text(data: dict[str, Any]) -> str:
    lines = [
        f"Transaction: {data.get('txHash')}",
        f"Chain ID: {data.get('chainId')}",
        f"Block: {data.get('blockHeight')}",
        f"Time: {data.get('txTime')}",
        f"Status: {data.get('status')}",
        f"Gas Limit: {data.get('gasLimit')}",
        f"Gas Used: {data.get('gasUsed')}",
        f"Gas Price: {data.get('gasPrice')}",
        f"Tx Fee: {data.get('txFee')}",
        f"Nonce: {data.get('nonce')}",
        f"Amount: {data.get('amount')} {data.get('symbol')}",
        f"Method ID: {data.get('methodId')}",
        "",
        "From:",
    ]
    for item in data.get("from") or []:
        contract_flag = " (contract)" if item.get("isContract") else ""
        lines.append(f"- {item.get('address')}{contract_flag}")

    lines.append("")
    lines.append("To:")
    for item in data.get("to") or []:
        contract_flag = " (contract)" if item.get("isContract") else ""
        lines.append(f"- {item.get('address')}{contract_flag}")

    internal = data.get("internalTransactions") or []
    lines.append("")
    lines.append("Internal transactions:")
    if internal:
        for item in internal:
            lines.append(f"- {item.get('from')} -> {item.get('to')}: {item.get('amount')} ({item.get('status')})")
    else:
        lines.append("- None")

    transfers = data.get("tokenTransfers") or []
    lines.append("")
    lines.append("Token transfers:")
    if transfers:
        for item in transfers:
            lines.append(
                f"- {item.get('from')} -> {item.get('to')}: {item.get('amount')} {item.get('symbol')} (contract={item.get('tokenContractAddress')})"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)


class TransactionDetailTool(Tool):
    name = "transaction_detail"
    description = """
Look up transaction detail by chain and transaction hash via KittyChain API.
Returns full transaction information including status, gas, internal transactions, and token transfers.
    """
    parameters = {
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "Chain name, alias, or CHAIN ID value.",
            },
            "tx_hash": {
                "type": "string",
                "description": "Transaction hash to inspect.",
            },
            "i_type": {
                "type": "string",
                "description": "Optional layer type filter: 0 native transfer, 1 internal native transfer, 2 token transfer.",
            },
        },
        "required": ["chain", "tx_hash"],
    }

    def execute(self, chain: str, tx_hash: str, i_type: str = "") -> str:
        if not chain:
            raise ValueError("chain is required")
        if not tx_hash:
            raise ValueError("tx_hash is required")
        payload: dict[str, Any] = {"chain": chain, "txHash": tx_hash}
        if i_type:
            payload["iType"] = i_type
        data = post_kittychain("/api/transaction/detail", payload)
        return render_text(data)


def main(chain: str, tx_hash: str) -> int:
    if not chain:
        print("Error: chain is required")
        return 1
    if not tx_hash:
        print("Error: tx_hash is required")
        return 1
    tool = TransactionDetailTool()
    print(tool.execute(chain, tx_hash))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("ethereum", "0xb27d1f6d9f1b7c57bbe8f0c0e14f544ae43b180a2cb23631e45f2817a9652298"))
