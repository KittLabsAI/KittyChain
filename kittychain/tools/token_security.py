"""Check token security and risk signals via KittyChain API."""

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


FLAG_DESCRIPTIONS = {
    "anti_whale_modifiable": "Anti-whale settings can be modified.",
    "buy_tax": "Buy tax",
    "can_take_back_ownership": "Ownership can be taken back.",
    "cannot_buy": "Token buying is restricted.",
    "cannot_sell_all": "Holders may not be able to sell all tokens.",
    "creator_address": "Creator address",
    "creator_balance": "Creator balance",
    "creator_percent": "Creator ownership percent",
    "external_call": "Contract contains external call risk.",
    "fake_token": "Fake token information",
    "hidden_owner": "Hidden owner pattern detected.",
    "honeypot_with_same_creator": "Related honeypot found from the same creator.",
    "is_airdrop_scam": "Token is flagged as an airdrop scam.",
    "is_anti_whale": "Anti-whale restrictions exist.",
    "is_blacklisted": "Blacklist logic exists.",
    "is_in_dex": "Token has active DEX trading pairs.",
    "is_honeypot": "Token is flagged as a honeypot.",
    "is_mintable": "Token supply is mintable.",
    "is_open_source": "Contract source is open.",
    "is_proxy": "Contract is a proxy.",
    "is_true_token": "Token is identified as the true token contract.",
    "is_whitelisted": "Whitelist logic exists.",
    "owner_address": "Owner address",
    "owner_balance": "Owner balance",
    "owner_change_balance": "Owner can change balances.",
    "owner_percent": "Owner ownership percent.",
    "personal_slippage_modifiable": "Personal slippage can be modified.",
    "selfdestruct": "Contract can self-destruct.",
    "sell_tax": "Sell tax",
    "slippage_modifiable": "Slippage settings can be modified.",
    "token_name": "Token name",
    "token_symbol": "Token symbol",
    "total_supply": "Total supply",
    "trading_cooldown": "Trading cooldown exists.",
    "transfer_pausable": "Transfers can be paused.",
    "trust_list": "Trust list logic exists.",
}
SAFE_POSITIVE_FLAGS = {"is_open_source", "is_true_token"}
NON_FLAG_FIELDS = {
    "token_name",
    "token_symbol",
    "holders",
    "lp_holders",
    "dex",
    "buy_tax",
    "sell_tax",
    "holder_count",
    "lp_holder_count",
    "total_supply",
    "lp_total_supply",
    "note",
    "other_potential_risks",
}


def _field_label(key: str, for_detail: bool = False) -> str:
    label = FLAG_DESCRIPTIONS.get(key)
    if label:
        return label.rstrip(".") if for_detail else label
    return key.replace("_", " ").capitalize()


def _aggregate_dex_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from decimal import Decimal, InvalidOperation

    grouped: dict[str, Decimal] = {}
    for row in rows:
        name = str(row.get("name") or "unknown")
        liquidity_text = str(row.get("liquidity") or "0").strip()
        try:
            liquidity = Decimal(liquidity_text)
        except (InvalidOperation, ValueError):
            liquidity = Decimal("0")
        grouped[name] = grouped.get(name, Decimal("0")) + liquidity
    return [
        {"name": name, "liquidity": liquidity}
        for name, liquidity in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def render_text(summary: dict[str, Any]) -> str:
    lines = [f"Token: {summary['token_address']}", f"Chain: {summary['chain']}", ""]
    security = summary["security"]
    if security["is_malicious"]:
        lines.append("Security status: malicious or risky signals detected")
        lines.append("Risk findings:")
        for item in security["positive_flag_details"]:
            lines.append(f"- {item['label']}")
    else:
        lines.append("Security status: no positive malicious flags detected")
    lines.append("")
    lines.append("Security details:")
    if security["details"]:
        for key, value in sorted(security["details"].items()):
            if key in {"holders", "lp_holders", "dex"}:
                continue
            if value in (None, "", "0", 0, [], {}):
                continue
            label = _field_label(key, for_detail=True)
            lines.append(f"- {label}: {value}")
    if lines[-1] == "Security details:":
        lines.append("- No token security details returned")
    lines.append("")
    lines.append("Holders:")
    if summary["holders"]:
        for item in summary["holders"]:
            lines.append(
                f"- address={item.get('address')} | balance={item.get('balance')} | percent={item.get('percent')} | tag={item.get('tag')}"
            )
    else:
        lines.append("- No holders returned")
    lines.append("")
    lines.append("LP holders:")
    if summary["lp_holders"]:
        for item in summary["lp_holders"]:
            lines.append(
                f"- address={item.get('address')} | balance={item.get('balance')} | percent={item.get('percent')} | tag={item.get('tag')}"
            )
    else:
        lines.append("- No LP holders returned")
    lines.append("")
    lines.append("DEX info:")
    aggregated_dex = _aggregate_dex_rows(summary["dex"])
    if aggregated_dex:
        for item in aggregated_dex:
            from decimal import Decimal
            lines.append(f"- name={item['name']} | liquidity={float(item['liquidity']):.8f}")
    else:
        lines.append("- No DEX info returned")
    return "\n".join(lines)


def _map_response(token_address: str, chain: str, data: dict[str, Any]) -> dict[str, Any]:
    details_raw = data.get("details") or {}
    details = {}
    for raw_key, value in details_raw.items():
        key = raw_key.lstrip("_")
        if key == "discriminator":
            continue
        details[key] = value

    positive_flags = data.get("positiveFlags") or []
    positive_flag_details = [
        {"key": d.get("key"), "label": d.get("label")}
        for d in (data.get("positiveFlagDetails") or [])
    ]

    holders_raw = data.get("holders") or []
    holders = []
    for h in holders_raw:
        holders.append({
            "address": h.get("address"),
            "balance": h.get("balance"),
            "percent": h.get("percent"),
            "tag": h.get("tag"),
        })

    lp_holders_raw = data.get("lpHolders") or []
    lp_holders = []
    for h in lp_holders_raw:
        lp_holders.append({
            "address": h.get("address"),
            "balance": h.get("balance"),
            "percent": h.get("percent"),
            "tag": h.get("tag"),
        })

    dex_raw = data.get("dex") or []

    return {
        "token_address": token_address,
        "chain": chain,
        "security": {
            "is_malicious": data.get("isMalicious", False),
            "positive_flags": positive_flags,
            "positive_flag_details": positive_flag_details,
            "details": details,
        },
        "holders": holders,
        "lp_holders": lp_holders,
        "dex": dex_raw,
    }


class TokenSecurityTool(Tool):
    name = "token_security"
    description = """
Check token security and risk data via KittyChain API.
Returns security information, holders, LP holders, and DEX information.
# Important Notes
- After calling this tool, check the top holders with address_malicious.
- After calling this tool, always use web_fetch to verify the token information.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_address": {
                "type": "string",
                "description": "The token contract address to inspect.",
            },
            "chain": {
                "type": "string",
                "description": "Chain name or ID. Use: Ethereum, BSC, Arbitrum, Polygon, Base, Optimism, Avalanche, etc.",
            },
        },
        "required": ["token_address", "chain"],
    }

    _parent_agent = None

    def execute(self, token_address: str, chain: str) -> str:
        if not token_address:
            raise ValueError("token_address is required")
        if not chain:
            raise ValueError("chain is required")
        data = post_kittychain("/api/token/security", {"tokenAddress": token_address, "chain": chain})
        summary = _map_response(token_address, chain, data)
        return render_text(summary)


def main(token_address: str, chain: str) -> int:
    if not token_address:
        print("Error: token_address is required")
        return 1
    if not chain:
        print("Error: chain is required")
        return 1
    tool = TokenSecurityTool()
    print(tool.execute(token_address, chain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "ethereum"))
