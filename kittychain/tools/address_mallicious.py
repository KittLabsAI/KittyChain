"""Check whether an address has malicious or risky signals using GoPlus."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from goplus.address import Address
from goplus.auth import Auth

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .base import Tool  # noqa: F401
    from ..config import Config

FLAG_DESCRIPTIONS = {
    "blacklist_doubt": "The address is suspected of malicious behavior and may be blacklisted.",
    "blackmail_activities": "The address is associated with blackmail-related activity.",
    "cybercrime": "The address is associated with cybercrime-related activity.",
    "darkweb_transactions": "The address is associated with dark web transactions.",
    "fake_kyc": "The address is associated with fake KYC or identity materials.",
    "fake_standard_interface": "The contract exposes standard interfaces that do not comply with the expected standard.",
    "fake_token": "The address is associated with a fake token or impersonated asset.",
    "financial_crime": "The address is associated with financial crime risk.",
    "gas_abuse": "The address may abuse gas mechanics or exploit other users' gas costs.",
    "honeypot_related_address": "The address is related to honeypot projects or scam tokens.",
    "malicious_address": "The address is flagged as malicious overall.",
    "malicious_mining_activities": "The address is associated with malicious mining activity.",
    "mixer": "The address is associated with a coin mixer.",
    "money_laundering": "The address is associated with money laundering risk.",
    "phishing_activities": "The address is associated with phishing activity.",
    "reinit": "The address or contract may be redeployable or re-initializable, which adds risk.",
    "sanctioned": "The address is associated with sanctioned entities.",
    "stealing_attack": "The address is associated with stealing attacks or asset theft.",
}
NON_FLAG_FIELDS = {"contract_address", "data_source", "number_of_malicious_contracts_created"}
DETAIL_LABELS = {
    "contract_address": "Related contract address",
    "data_source": "Data source",
    "number_of_malicious_contracts_created": "Number of malicious contracts created",
}


def _load_credentials() -> tuple[str, str]:
    apis = Config.from_file().apis
    if apis.goplus_api_key and apis.goplus_api_secret:
        return apis.goplus_api_key, apis.goplus_api_secret
    k = os.environ.get("GOPLUS_KEY", "")
    s = os.environ.get("GOPLUS_SECRET", "")
    return k, s


def _coerce_to_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if hasattr(data, "dict") and callable(data.dict):
        return data.dict()
    if hasattr(data, "model_dump") and callable(data.model_dump):
        return data.model_dump()
    if hasattr(data, "__dict__"):
        return dict(data.__dict__)
    raise TypeError("unsupported GoPlus response type")


def summarize_security_result(address: str, raw_data: Any) -> dict[str, Any]:
    payload = _coerce_to_dict(raw_data)
    address_details = payload.get("_result")
    if address_details is None:
        address_details = payload.get("result", {})
    if not isinstance(address_details, dict):
        address_details = _coerce_to_dict(address_details)
    normalized_details = {}
    for raw_key, value in address_details.items():
        key = raw_key.lstrip("_")
        if key == "discriminator":
            continue
        normalized_details[key] = value
    positive_flags = []
    for key, value in normalized_details.items():
        if key in NON_FLAG_FIELDS:
            continue
        if str(value) == "1":
            positive_flags.append(key)
    described_flags = [{"key": key, "label": FLAG_DESCRIPTIONS.get(key, key.replace("_", " "))} for key in positive_flags]
    return {
        "address": address,
        "is_malicious": bool(positive_flags),
        "positive_flags": positive_flags,
        "positive_flag_details": described_flags,
        "details": normalized_details,
    }


def render_security_text(summary: dict[str, Any]) -> str:
    lines = [f"Address: {summary['address']}", ""]
    if summary["is_malicious"]:
        lines.append("Security status: malicious or risky signals detected")
        lines.append("Risk findings:")
        for item in summary.get("positive_flag_details", []):
            lines.append(f"- {item['key']}: {item['label']}")
    else:
        lines.append("Security status: no positive malicious flags detected")
    if summary["details"].get("data_source"):
        lines.append(f"Data source: {summary['details']['data_source']}")
    if summary["details"].get("number_of_malicious_contracts_created") not in (None, "0", 0):
        lines.append(f"Related malicious contracts created: {summary['details']['number_of_malicious_contracts_created']}")
    lines.append("")
    lines.append("Details:")
    if summary["details"]:
        for key, value in sorted(summary["details"].items()):
            if key in FLAG_DESCRIPTIONS:
                lines.append(f"- {FLAG_DESCRIPTIONS[key]} Value: {value}")
            else:
                lines.append(f"- {DETAIL_LABELS.get(key, key)}: {value}")
    else:
        lines.append("- No address security details returned")
    return "\n".join(lines)


def run_security_lookup(address: str, key: str, secret: str) -> dict[str, Any]:
    access_token = Auth(key=key, secret=secret).get_access_token().result.access_token
    raw_data = Address(access_token=access_token).address_security(address=address)
    return summarize_security_result(address, raw_data)


class AddressMaliciousTool(Tool):
    name = "address_malicious"
    description = """
**Support ALL CHAINS.** 
Check whether an address has malicious or risky signals using GoPlus.
Returns flags for various risk categories including phishing, malware, mixing, sanctions, and more.
# Important Notes
- After calling this tool, always use web_browser, address_labels, address_balance, and address_transfers to verify the result.
- Using web_browser can provide additional insights such as token risk, token metadata, and related addresses.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The address to inspect.",
            },
        },
        "required": ["address"],
    }

    _parent_agent = None

    def execute(self, address: str) -> str:
        if not address:
            raise ValueError("address is required")
        key, secret = _load_credentials()
        if not key or not secret:
            raise ValueError("GOPLUS_KEY and GOPLUS_SECRET are required")
        summary = run_security_lookup(address, key, secret)
        return render_security_text(summary)


def main(address: str) -> int:
    if not address:
        print("Error: address is required")
        return 1
    key, secret = _load_credentials()
    if not key or not secret:
        print("Error: GOPLUS_KEY and GOPLUS_SECRET are required")
        return 1
    summary = run_security_lookup(address, key, secret)
    print(render_security_text(summary))
    return 0


# Backward-compatible class alias for legacy imports.
AddressMalliciousTool = AddressMaliciousTool


if __name__ == "__main__":
    address = "0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"
    raise SystemExit(main(address))
