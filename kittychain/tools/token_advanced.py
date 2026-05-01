"""Look up advanced token data via KittyChain API."""

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
        "Token advanced data:",
        f"- total_fee: {data.get('totalFee')}",
        f"- lp_burned_percent: {data.get('lpBurnedPercent')}",
        f"- is_internal: {data.get('isInternal')}",
        f"- protocol_id: {data.get('protocolId')}",
        f"- progress: {data.get('progress')}",
        f"- token_tags: {', '.join(data.get('tokenTags') or [])}",
        f"- create_time: {data.get('createTime')}",
        f"- creator_address: {data.get('creatorAddress')}",
        f"- risk_control_level: {data.get('riskControlLevel')}",
        f"- top10_hold_percent: {data.get('top10HoldPercent')}",
    ]
    return "\n".join(lines)


class TokenAdvancedTool(Tool):
    name = "token_advanced"
    description = """
Look up advanced token data by chain and token contract address via KittyChain API.
Returns LP burn info, creator details, risk level, and top holder concentration.
    """
    parameters = {
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "Chain name or ID. Use: Ethereum, BSC, Arbitrum, Polygon, Base, Optimism, Avalanche, etc.",
            },
            "token_address": {
                "type": "string",
                "description": "The token contract address to inspect.",
            },
        },
        "required": ["chain", "token_address"],
    }

    def execute(self, chain: str, token_address: str) -> str:
        if not chain:
            raise ValueError("chain is required")
        if not token_address:
            raise ValueError("token_address is required")
        data = post_kittychain("/api/token/advanced", {"chain": chain, "tokenAddress": token_address})
        return render_text(data)


def main(chain: str, token_address: str) -> int:
    if not chain:
        print("Error: chain is required")
        return 1
    if not token_address:
        print("Error: token_address is required")
        return 1
    tool = TokenAdvancedTool()
    print(tool.execute(chain, token_address))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("ethereum", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"))
