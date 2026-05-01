"""Check whether an address has malicious or risky signals via KittyChain API."""

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
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No address security details returned")
    return "\n".join(lines)


def _map_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": data.get("address", ""),
        "is_malicious": data.get("isMalicious", False),
        "positive_flags": data.get("positiveFlags") or [],
        "positive_flag_details": [
            {"key": d.get("key"), "label": d.get("label")}
            for d in (data.get("positiveFlagDetails") or [])
        ],
        "details": data.get("details") or {},
    }


class AddressMaliciousTool(Tool):
    name = "address_malicious"
    description = """
**Support ALL CHAINS.**
Check whether an address has malicious or risky signals via KittyChain API.
Returns flags for various risk categories including phishing, malware, mixing, sanctions, and more.
# Important Notes
- After calling this tool, always use web_fetch, address_labels, address_balance, and address_transfers to verify the result.
- Using web_fetch can provide additional insights such as token risk, token metadata, and related addresses.
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
        data = post_kittychain("/api/address/malicious", {"address": address})
        summary = _map_response(data)
        return render_security_text(summary)


def main(address: str) -> int:
    if not address:
        print("Error: address is required")
        return 1
    tool = AddressMaliciousTool()
    print(tool.execute(address))
    return 0


# Backward-compatible class alias for legacy imports.
AddressMalliciousTool = AddressMaliciousTool


if __name__ == "__main__":
    raise SystemExit(main("0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"))
