"""Infer likely chains from an address string pattern."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # type: ignore
else:
    from .base import Tool

_HEX_40_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_HEX_64_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
_HEX_64_NO_PREFIX_RE = re.compile(r"^[a-fA-F0-9]{64}$")
_BTC_LEGACY_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
_BTC_BECH32_RE = re.compile(r"^bc1[ac-hj-np-z02-9]{11,87}$", re.IGNORECASE)
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_SOLANA_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_XRP_RE = re.compile(r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
_STELLAR_RE = re.compile(r"^G[A-Z2-7]{55}$")
_CARDANO_RE = re.compile(r"^addr1[0-9a-z]{4,}$")
_NEAR_ACCOUNT_RE = re.compile(r"^[a-z0-9._-]+\.near$")
_LTC_BECH32_RE = re.compile(r"^ltc1[ac-hj-np-z02-9]{11,87}$", re.IGNORECASE)
_LTC_BASE58_RE = re.compile(r"^[LM][1-9A-HJ-NP-Za-km-z]{26,33}$")
_DOGE_RE = re.compile(r"^D[1-9A-HJ-NP-Za-km-z]{25,34}$")
_BCH_CASHADDR_RE = re.compile(r"^(bitcoincash:)?[qp][a-z0-9]{41}$", re.IGNORECASE)
_MONERO_RE = re.compile(r"^[48][1-9A-HJ-NP-Za-km-z]{94,105}$")
_TEZOS_RE = re.compile(r"^(tz1|tz2|tz3|KT1)[1-9A-HJ-NP-Za-km-z]{33}$")
_MULTIVERSX_RE = re.compile(r"^erd1[0-9a-z]{20,}$")
_CRONOS_POS_RE = re.compile(r"^cro1[0-9a-z]{20,}$")
_BNB_BEACON_RE = re.compile(r"^bnb1[0-9a-z]{20,}$")
_ZILLIQA_RE = re.compile(r"^zil1[0-9a-z]{20,}$")
_NANO_RE = re.compile(r"^(nano|xrb)_[0-9a-z]{20,}$")
_FILECOIN_RE = re.compile(r"^[ft][134][a-z2-7]{10,}$")

_COSMOS_PREFIX_CHAINS = {
    "cosmos1": ["Cosmos Hub"],
    "osmo1": ["Osmosis"],
    "celestia1": ["Celestia"],
    "sei1": ["Sei"],
    "inj1": ["Injective"],
    "juno1": ["Juno"],
    "dym1": ["Dymension"],
    "stars1": ["Stargaze"],
    "akash1": ["Akash"],
    "evmos1": ["Evmos"],
    "dydx1": ["dYdX Chain"],
}

_GENERIC_COSMOS_RE = re.compile(r"^[a-z]{3,20}1[0-9a-z]{20,}$")
_EVM_CHAINS = [
    "Ethereum",
    "BNB Chain",
    "Polygon",
    "Arbitrum",
    "Optimism",
    "Base",
    "Avalanche C-Chain",
    "Linea",
    "zkSync Era",
    "Scroll",
    "Mantle",
]


def infer_possible_chains(address: str) -> list[str]:
    candidate = address.strip()
    if not candidate:
        return []

    lowered = candidate.lower()
    if _HEX_40_RE.fullmatch(candidate):
        return list(_EVM_CHAINS)
    if _HEX_64_RE.fullmatch(candidate):
        return ["Aptos", "Sui"]
    if _HEX_64_NO_PREFIX_RE.fullmatch(candidate):
        return ["NEAR (implicit account)"]
    if _BTC_BECH32_RE.fullmatch(candidate) or _BTC_LEGACY_RE.fullmatch(candidate):
        return ["Bitcoin"]
    if _TRON_RE.fullmatch(candidate):
        return ["TRON"]
    if _XRP_RE.fullmatch(candidate):
        return ["XRP Ledger"]
    if _STELLAR_RE.fullmatch(candidate):
        return ["Stellar"]
    if _CARDANO_RE.fullmatch(lowered):
        return ["Cardano"]
    if _NEAR_ACCOUNT_RE.fullmatch(lowered):
        return ["NEAR"]
    if _LTC_BECH32_RE.fullmatch(candidate) or _LTC_BASE58_RE.fullmatch(candidate):
        return ["Litecoin"]
    if _DOGE_RE.fullmatch(candidate):
        return ["Dogecoin"]
    if _BCH_CASHADDR_RE.fullmatch(lowered):
        return ["Bitcoin Cash"]
    if _MONERO_RE.fullmatch(candidate):
        return ["Monero"]
    if _TEZOS_RE.fullmatch(candidate):
        return ["Tezos"]
    if _MULTIVERSX_RE.fullmatch(lowered):
        return ["MultiversX"]
    if _CRONOS_POS_RE.fullmatch(lowered):
        return ["Cronos POS"]
    if _BNB_BEACON_RE.fullmatch(lowered):
        return ["BNB Beacon Chain"]
    if _ZILLIQA_RE.fullmatch(lowered):
        return ["Zilliqa"]
    if _NANO_RE.fullmatch(lowered):
        return ["Nano"]
    if _FILECOIN_RE.fullmatch(lowered):
        return ["Filecoin"]
    for prefix, chains in _COSMOS_PREFIX_CHAINS.items():
        if lowered.startswith(prefix):
            return list(chains)
    if _GENERIC_COSMOS_RE.fullmatch(lowered):
        return ["Cosmos-style Bech32 chain"]
    if _SOLANA_RE.fullmatch(candidate):
        return ["Solana"]
    return []


def render_address_pattern_text(address: str, chains: list[str]) -> str:
    lines = [f"Address: {address}", ""]
    if chains:
        lines.append("Possible chains:")
        for chain in chains:
            lines.append(f"- {chain}")
        lines.append("")
        lines.append("Note: this is pattern-based matching, so shared address formats can only narrow the candidates.")
    else:
        lines.append("Possible chains: none matched")
        lines.append("")
        lines.append("Note: I could not map this address pattern to a known chain family.")
    return "\n".join(lines)


class AddressPatternTool(Tool):
    name = "address_pattern"
    description = """
Infer the most likely chain family for an address from its string pattern.
Use this first when the user gives an address and the chain is unclear.
Returns a short list of possible chains when multiple networks share the same format.
# Important Notes
- if this tool return EVM-compatible chains, call `address_malicious`+`address_balance`+`address_labels`+`address_transfers` for further information.
- if this tool return other chains, call `address_malicious`+`web_browser`+`web_search` for further information.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet or contract address to classify by pattern.",
            },
        },
        "required": ["address"],
    }

    def execute(self, address: str) -> str:
        address = address.strip()
        if not address:
            return "Error: address is required"
        return render_address_pattern_text(address, infer_possible_chains(address))


def main(address: str) -> int:
    output = AddressPatternTool().execute(address)
    print(output)
    return 0 if not output.startswith("Error:") else 1


if __name__ == "__main__":
    raise SystemExit(main("0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"))
