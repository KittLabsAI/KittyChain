"""Aggregate counterparties and transferred asset values across default Alchemy networks."""

import argparse
import json
import os
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .base import Tool  # noqa: F401
    from ..config import Config

RPC_API_TEMPLATE = "https://{network}.g.alchemy.com/v2/{api_key}"
DEFAULT_NETWORKS = [
    "eth-mainnet",
    "arb-mainnet",
    "base-mainnet",
    "avax-mainnet",
    "bnb-mainnet",
    "blast-mainnet",
    "zksync-mainnet",
    "polygon-mainnet",
]


class AlchemyAPIError(RuntimeError):
    pass


def _load_api_key() -> str:
    key = Config.from_file().apis.alchemy_api_key
    if key:
        return key
    return os.environ.get("ALCHEMY_API_KEY", "")


def _build_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, context=_build_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AlchemyAPIError(f"HTTP {exc.code} calling {url}: {body}") from exc
    except URLError as exc:
        raise AlchemyAPIError(f"Network error calling {url}: {exc.reason}") from exc


def get_asset_transfers(
    api_key: str,
    network: str,
    from_address: str | None = None,
    to_address: str | None = None,
    from_block: str = "0x0",
    to_block: str = "latest",
    category: list[str] | None = None,
    exclude_zero_value: bool = False,
    with_metadata: bool = True,
    max_count: str | None = None,
    page_key: str | None = None,
) -> dict[str, Any]:
    url = RPC_API_TEMPLATE.format(network=network, api_key=api_key)
    transfer_params: dict[str, Any] = {
        "fromBlock": from_block,
        "toBlock": to_block,
        "excludeZeroValue": exclude_zero_value,
        "withMetadata": with_metadata,
        "category": category or ["erc20"],
    }
    if from_address:
        transfer_params["fromAddress"] = from_address
    if to_address:
        transfer_params["toAddress"] = to_address
    if max_count:
        transfer_params["maxCount"] = max_count
    if page_key:
        transfer_params["pageKey"] = page_key
    payload = {"jsonrpc": "2.0", "id": 1, "method": "alchemy_getAssetTransfers", "params": [transfer_params]}
    return _post_json(url, payload)


def fetch_all_transfers(address: str, api_key: str, networks: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    responses: list[dict[str, Any]] = []
    skipped_networks: list[dict[str, str]] = []
    for network in networks:
        try:
            responses.append({"network": network, "direction": "from", "payload": get_asset_transfers(api_key=api_key, network=network, from_address=address)})
            responses.append({"network": network, "direction": "to", "payload": get_asset_transfers(api_key=api_key, network=network, to_address=address)})
        except Exception as exc:
            skipped_networks.append({"network": network, "reason": str(exc)})
    return responses, skipped_networks


def summarize_transfers(address: str, responses: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_address = address.lower()
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for response in responses:
        network = response["network"]
        direction = response["direction"]
        transfers = response.get("payload", {}).get("result", {}).get("transfers", [])
        for transfer in transfers:
            asset = transfer.get("asset") or "UNKNOWN"
            from_address = (transfer.get("from") or "").lower()
            to_address = (transfer.get("to") or "").lower()
            counterparty = to_address if direction == "from" else from_address
            if not counterparty:
                continue
            timestamp = (transfer.get("metadata") or {}).get("blockTimestamp")
            value = transfer.get("value") or 0
            key = (network, direction, counterparty, asset)
            if key not in grouped:
                grouped[key] = {
                    "network": network,
                    "direction": direction,
                    "counterparty": counterparty,
                    "asset": asset,
                    "total_value": 0.0,
                    "first_timestamp": timestamp,
                    "last_timestamp": timestamp,
                }
            grouped[key]["total_value"] += float(value)
            if timestamp:
                if grouped[key]["first_timestamp"] is None or timestamp < grouped[key]["first_timestamp"]:
                    grouped[key]["first_timestamp"] = timestamp
                if grouped[key]["last_timestamp"] is None or timestamp > grouped[key]["last_timestamp"]:
                    grouped[key]["last_timestamp"] = timestamp
    items = sorted(grouped.values(), key=lambda item: (item["network"], item["direction"], -item["total_value"], item["counterparty"], item["asset"]))
    for item in items:
        item["total_value"] = round(item["total_value"], 8)
    return {"address": normalized_address, "items": items, "skipped_networks": []}


def render_transfers_text(summary: dict[str, Any]) -> str:
    lines = [f"Address: {summary['address']}", "", "Aggregated counterparties:"]
    if summary["items"]:
        for item in summary["items"]:
            lines.append(
                f"- network={item['network']}, direction={item['direction']}, counterparty={item['counterparty']}, "
                f"asset={item['asset']}, total_value={item['total_value']:.8f}, "
                f"first={item['first_timestamp']}, last={item['last_timestamp']}"
            )
    else:
        lines.append("- No transfers found")
    if summary.get("skipped_networks"):
        lines.append("")
        lines.append("Skipped networks:")
        for item in summary["skipped_networks"]:
            lines.append(f"- {item['network']}: {item['reason']}")
    return "\n".join(lines)


class AddressTransfersTool(Tool):
    name = "address_transfers"
    description = """
Aggregate counterparties and transferred asset values across default Alchemy networks.
Returns aggregated transfer data grouped by network, direction, counterparty, and asset.
# Important Notes
- After calling this tool, inspect the 3-5 most frequent counterparties and check each one with address_mallicious.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet address to inspect.",
            },
        },
        "required": ["address"],
    }

    _parent_agent = None

    def execute(self, address: str) -> str:
        if not address:
            raise ValueError("address is required")
        api_key = _load_api_key()
        if not api_key:
            raise ValueError("ALCHEMY_API_KEY is required")
        responses, skipped_networks = fetch_all_transfers(address, api_key, DEFAULT_NETWORKS)
        summary = summarize_transfers(address, responses)
        summary["skipped_networks"] = skipped_networks
        return render_transfers_text(summary)


def main(address: str) -> int:
    if not address:
        print("Error: address is required")
        return 1
    api_key = _load_api_key()
    if not api_key:
        print("Error: ALCHEMY_API_KEY is required")
        return 1
    responses, skipped_networks = fetch_all_transfers(address, api_key, DEFAULT_NETWORKS)
    summary = summarize_transfers(address, responses)
    summary["skipped_networks"] = skipped_networks
    print(render_transfers_text(summary))
    return 0


if __name__ == "__main__":
    address = "0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"
    raise SystemExit(main(address))
