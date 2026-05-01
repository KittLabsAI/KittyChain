"""Look up token top holders via KittyChain API."""

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

CHAIN_ID_DESCRIPTION = (
    "Chain network id. Use: Ethereum=1, Polygon=137, BSC=56, Avalanche=43114, "
    "Arbitrum One=42161, Optimism=10, Base=8453, zkSync=324, Merlin=4200."
)

_CHAIN_ID_TO_NAME: dict[int, str] = {
    1: "Ethereum",
    56: "BNB Chain",
    137: "Polygon",
    42161: "Arbitrum",
    10: "Optimism",
    8453: "Base",
    43114: "Avalanche C-Chain",
    324: "zkSync Era",
    4200: "Merlin",
}


def _chain_name(chain_id: int) -> str:
    return _CHAIN_ID_TO_NAME.get(chain_id, str(chain_id))


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
Look up token top holders for a token contract on a specific chain via KittyChain API.
Returns top holders and holder amounts for the token contract.
# Important Notes
- After calling this tool, check the top holders with address_malicious.
- After calling this tool, always use web_fetch to verify the holder information.
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
        if not token_address:
            raise ValueError("token_address is required")
        chain = _chain_name(chain_id)
        data = post_kittychain("/api/token/holders", {"tokenAddress": token_address, "chain": chain})
        holders_raw = data.get("holders") or []
        top_holders = []
        for item in holders_raw:
            top_holders.append({
                "wallet_address": item.get("walletAddress"),
                "amount": float(item.get("amount") or 0),
                "usd_value": float(item.get("usdValue") or 0),
            })
        summary = {
            "token_address": token_address,
            "chain_id": int(chain_id),
            "top_holders": top_holders,
        }
        return render_text(summary)


def main(token_address: str, chain_id: int) -> int:
    if not token_address:
        print("Error: token_address is required")
        return 1
    tool = TokenHoldersTool()
    print(tool.execute(token_address, chain_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 1))
