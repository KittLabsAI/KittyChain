"""Look up Chainbase address labels for one or more EVM addresses."""

import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests import HTTPError

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from address_identity import parse_addresses  # type: ignore
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .address_identity import parse_addresses
    from .base import Tool  # noqa: F401
    from ..config import Config

CHAINBASE_LABELS_URL = "https://api.chainbase.online/v1/address/labels"
SUPPORTED_CHAINS = {
    "Ethereum": 1,
    "Polygon": 137,
    "BSC": 56,
    "Arbitrum One": 42161,
    "Optimism": 10,
    "Base": 8453
}
SUPPORTED_CHAIN_IDS = list(SUPPORTED_CHAINS.values())
RATE_LIMIT_PER_SECOND = 3
RATE_LIMIT_WINDOW_SECONDS = 1.0
MIN_REQUEST_INTERVAL_SECONDS = RATE_LIMIT_WINDOW_SECONDS / RATE_LIMIT_PER_SECOND


class ChainbaseAPIError(RuntimeError):
    """Raised when the Chainbase labels API returns an error."""


def _load_api_key() -> str:
    key = Config.from_file().apis.chainbase_api_key
    if key:
        return key
    return os.environ.get("CHAINBASE_API_KEY", "")


def _fetch_labels_for_chain(
    session: Any,
    api_key: str,
    address: str,
    chain_id: int,
    timeout: int = 20,
    sleep_func=time.sleep,
    max_attempts: int = 2,
) -> dict[str, Any]:
    last_error = None
    for attempt in range(1, max_attempts + 1):
        response = session.get(
            CHAINBASE_LABELS_URL,
            headers={"x-api-key": api_key},
            params={"chain_id": chain_id, "address": address},
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except HTTPError as exc:
            last_error = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429 and attempt < max_attempts:
                retry_after = getattr(exc.response, "headers", {}).get("Retry-After", "1")
                try:
                    sleep_seconds = float(retry_after)
                except (TypeError, ValueError):
                    sleep_seconds = 1.0
                sleep_func(max(sleep_seconds, 1.0))
                continue
            raise
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise ChainbaseAPIError(payload.get("message") or "Chainbase labels lookup failed")
        return payload
    raise ChainbaseAPIError("Chainbase labels lookup failed") from last_error


def summarize_label_results(
    addresses: str | list[str] | tuple[str, ...],
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_addresses = parse_addresses(addresses)
    collected: dict[str, dict[tuple[str, tuple[str, ...]], dict[str, Any]]] = {
        address: {} for address in normalized_addresses
    }

    for payload in payloads:
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            continue
        for address, labels in data.items():
            if address not in collected or not isinstance(labels, list):
                continue
            for label in labels:
                if not isinstance(label, dict):
                    continue
                category = str(label.get("category") or "").strip()
                tags = [str(tag) for tag in label.get("tags") or [] if str(tag).strip()]
                if not category:
                    continue
                dedupe_key = (category, tuple(tags))
                collected[address][dedupe_key] = {"category": category, "tags": tags}

    summaries = []
    for address in normalized_addresses:
        labels = sorted(
            collected[address].values(),
            key=lambda item: (item["category"], item["tags"]),
        )
        summaries.append({"address": address, "labels": labels})
    return summaries


def fetch_address_labels(
    addresses: str | list[str] | tuple[str, ...],
    api_key: str,
    session: Any | None = None,
    timeout: int = 20,
    time_func=time.time,
    sleep_func=time.sleep,
) -> dict[str, Any] | list[dict[str, Any]]:
    normalized_addresses = parse_addresses(addresses)
    session = session or requests.Session()
    payloads = []
    last_request_started_at: float | None = None
    for address in normalized_addresses:
        for chain_id in SUPPORTED_CHAIN_IDS:
            if last_request_started_at is not None:
                now = time_func()
                sleep_seconds = MIN_REQUEST_INTERVAL_SECONDS - (now - last_request_started_at)
                if sleep_seconds > 0:
                    sleep_func(sleep_seconds)
            last_request_started_at = time_func()
            payloads.append(
                _fetch_labels_for_chain(
                    session,
                    api_key,
                    address,
                    chain_id,
                    timeout=timeout,
                    sleep_func=sleep_func,
                )
            )
    summaries = summarize_label_results(normalized_addresses, payloads)
    if len(summaries) == 1:
        return summaries[0]
    return summaries


def render_text(summary: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(summary, list):
        return "\n\n".join(render_text(item) for item in summary)

    lines = [f"Address: {summary['address']}", "", "Labels:"]
    if summary["labels"]:
        for item in summary["labels"]:
            tag_text = ", ".join(item["tags"]) if item["tags"] else "none"
            lines.append(f"- category={item['category']} | tags={tag_text}")
    else:
        lines.append("- No labels found")
    return "\n".join(lines)


class AddressLabelsTool(Tool):
    name = "address_labels"
    description = """
Look up Chainbase address labels for one or more EVM addresses.
Returns label category and tags aggregated across supported chains.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "One or more EVM addresses, separated by commas or whitespace.",
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
            raise ValueError("CHAINBASE_API_KEY is required")
        summary = fetch_address_labels(address, api_key)
        return render_text(summary)


def main(address: str) -> int:
    if not address:
        print("Error: address is required")
        return 1
    api_key = _load_api_key()
    if not api_key:
        print("Error: CHAINBASE_API_KEY is required")
        return 1
    summary = fetch_address_labels(address, api_key)
    print(render_text(summary))
    return 0


if __name__ == "__main__":
    address = ["0x28c6c06298d514db089934071355e5743bf21d60", "0x28c71c57f806fb674d9fa9d1fd47056b8d3da8bb"]
    raise SystemExit(main(address))
