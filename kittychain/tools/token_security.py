"""Check token security and risk signals using GoPlus."""

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from goplus.auth import Auth
from goplus.token import Token

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

TOKEN_SECURITY_URL_TEMPLATE = "https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
CHAIN_ID_DESCRIPTION = (
    "Chain network id. Use: 1=Ethereum, 56=BSC, 42161=Arbitrum, 137=Polygon, 324=zkSync Era, "
    "59144=Linea Mainnet, 8453=Base, 534352=Scroll, 10=Optimism, 43114=Avalanche, 250=Fantom, "
    "25=Cronos, 66=OKC, 128=HECO, 100=Gnosis, tron=Tron, 321=KCC, 201022=FON, 5000=Mantle, "
    "204=opBNB, 42766=ZKFair, 81457=Blast, 169=Manta Pacific, 80094=Berachain, 2741=Abstract, "
    "177=Hashkey Chain, 146=Sonic, 1514=Story, 130=Unichain, 480=World Chain, 1868=Soneium, "
    "48900=Zircuit, 5734951=Jovay, 143=Monad, 9745=Plasma, 4200=Merlin."
)
FLAG_DESCRIPTIONS = {
    "anti_whale_modifiable": "Anti-whale settings can be modified.",
    "buy_tax": "Buy tax",
    "can_take_back_ownership": "Ownership can be taken back.",
    "cannot_buy": "Token buying is restricted.",
    "cannot_sell_all": "Holders may not be able to sell all tokens.",
    "creator_address": "Creator address",
    "creator_balance": "Creator balance",
    "creator_percent": "Creator ownership percent",
    "dex": "DEX info",
    "external_call": "Contract contains external call risk.",
    "fake_token": "Fake token information",
    "holder_count": "Holder count",
    "holders": "Holders",
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
    "lp_holder_count": "LP holder count",
    "lp_holders": "LP holders",
    "lp_total_supply": "LP total supply",
    "note": "Note",
    "other_potential_risks": "Other potential risks",
    "owner_address": "Owner address",
    "owner_balance": "Owner balance",
    "owner_change_balance": "Owner can change balances.",
    "owner_percent": "Owner ownership percent",
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


def _is_empty_detail_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    text = str(value).strip()
    if not text:
        return True
    try:
        return Decimal(text) == 0
    except (InvalidOperation, ValueError):
        return False


def _aggregate_dex_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _load_credentials() -> tuple[str, str]:
    apis = Config.from_file().apis
    if apis.goplus_api_key and apis.goplus_api_secret:
        return apis.goplus_api_key, apis.goplus_api_secret
    k = os.environ.get("GOPLUS_KEY", "")
    s = os.environ.get("GOPLUS_SECRET", "")
    return k, s


def _normalize_details(raw_details: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for raw_key, value in raw_details.items():
        key = raw_key.lstrip("_")
        if key == "discriminator":
            continue
        normalized[key] = value
    return normalized


def _coerce_to_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if hasattr(data, "to_dict") and callable(data.to_dict):
        return data.to_dict()
    if hasattr(data, "dict") and callable(data.dict):
        return data.dict()
    if hasattr(data, "model_dump") and callable(data.model_dump):
        return data.model_dump()
    if hasattr(data, "__dict__"):
        return dict(data.__dict__)
    raise TypeError("unsupported GoPlus response type")


def summarize_token_security_result(token_address: str, chain_id: int | str, raw_data: dict[str, Any]) -> dict[str, Any]:
    normalized_address = normalize_address(token_address)
    token_entries = raw_data.get("result") or {}
    if not isinstance(token_entries, dict):
        token_entries = {}
    raw_details = token_entries.get(normalized_address) or token_entries.get(token_address) or {}
    if not raw_details and len(token_entries) == 1:
        raw_details = next(iter(token_entries.values()))
    if not isinstance(raw_details, dict):
        raw_details = {}

    details = _normalize_details(raw_details)
    positive_flags = []
    for key, value in details.items():
        if key in NON_FLAG_FIELDS or key in SAFE_POSITIVE_FLAGS:
            continue
        if str(value) == "1":
            positive_flags.append(key)

    return {
        "token_address": normalized_address,
        "chain_id": chain_id,
        "security": {
            "is_malicious": bool(positive_flags),
            "positive_flags": positive_flags,
            "positive_flag_details": [
                {"key": key, "label": _field_label(key)}
                for key in positive_flags
            ],
            "details": details,
        },
        "holders": list(details.get("holders") or []),
        "lp_holders": list(details.get("lp_holders") or []),
        "dex": list(details.get("dex") or []),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [f"Token: {summary['token_address']}", f"Chain ID: {summary['chain_id']}", ""]
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
            if _is_empty_detail_value(value):
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
            lines.append(f"- name={item['name']} | liquidity={item['liquidity']:.8f}")
    else:
        lines.append("- No DEX info returned")
    return "\n".join(lines)


def run_token_security_lookup(token_address: str, chain_id: int | str, key: str, secret: str) -> dict[str, Any]:
    normalized_address = normalize_address(token_address)
    access_token = Auth(key=key, secret=secret).get_access_token().result.access_token
    raw_data = Token(access_token=access_token).token_security(chain_id=str(chain_id), addresses=[normalized_address])
    payload = _coerce_to_dict(raw_data)
    if payload.get("result") in (None, {}):
        raise RuntimeError(
            f"GoPlus token security lookup returned no result. code={payload.get('code')} message={payload.get('message')}"
        )
    return summarize_token_security_result(normalized_address, chain_id, payload)


class TokenSecurityTool(Tool):
    name = "token_security"
    description = """
Check token security and risk data using GoPlus.
Returns security information, holders, LP holders, and DEX information.
# Important Notes
- After calling this tool, check the top holders with address_malicious.
- After calling this tool, always use web_browser tool to verify the token information.
    """
    parameters = {
        "type": "object",
        "properties": {
            "token_address": {
                "type": "string",
                "description": "The token contract address to inspect.",
            },
            "chain_id": {
                "type": "string",
                "description": CHAIN_ID_DESCRIPTION,
            },
        },
        "required": ["token_address", "chain_id"],
    }

    _parent_agent = None

    def execute(self, token_address: str, chain_id: str) -> str:
        if not token_address:
            raise ValueError("token_address is required")
        if not chain_id:
            raise ValueError("chain_id is required")
        key, secret = _load_credentials()
        if not key or not secret:
            raise ValueError("GOPLUS_KEY and GOPLUS_SECRET are required")
        summary = run_token_security_lookup(token_address, chain_id, key, secret)
        return render_text(summary)


def main(token_address: str, chain_id: str) -> int:
    if not token_address:
        print("Error: token_address is required")
        return 1
    if not chain_id:
        print("Error: chain_id is required")
        return 1
    key, secret = _load_credentials()
    if not key or not secret:
        print("Error: GOPLUS_KEY and GOPLUS_SECRET are required")
        return 1
    summary = run_token_security_lookup(token_address, chain_id, key, secret)
    print(render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "1"))
