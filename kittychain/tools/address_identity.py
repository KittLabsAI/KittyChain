"""Look up ENS identity and exchange attribution for an address on Dune."""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dune_client.client import DuneClient
from requests.exceptions import RetryError

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if __package__ in (None, ""):
    sys.path.insert(0, str(PROJECT_ROOT))
    from base import Tool  # noqa: F401
    from config import Config
else:
    from .base import Tool  # noqa: F401
    from ..config import Config

ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def normalize_address(address: str) -> str:
    normalized = address.strip().lower()
    if not ADDRESS_PATTERN.fullmatch(normalized):
        raise ValueError("address must be a 42-character 0x-prefixed hex string")
    return normalized


def parse_addresses(addresses: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(addresses, str):
        raw_items = [item for item in re.split(r"[\s,]+", addresses.strip()) if item]
    else:
        raw_items = [str(item).strip() for item in addresses if str(item).strip()]
    if not raw_items:
        raise ValueError("at least one address is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        address = normalize_address(item)
        if address not in seen:
            seen.add(address)
            normalized.append(address)
    return normalized


def _load_api_key() -> str:
    key = Config.from_file().apis.dune_api_key
    if key:
        return key
    return os.environ.get("DUNE_API_KEY") or os.environ.get("DUNE_API_TOKEN", "")


def _build_address_predicate(addresses: str | list[str] | tuple[str, ...]) -> str:
    normalized_addresses = parse_addresses(addresses)
    if len(normalized_addresses) == 1:
        return f"address = {normalized_addresses[0]}"
    return f"address IN ({', '.join(normalized_addresses)})"


def build_identity_sql(address: str | list[str] | tuple[str, ...], include_order_by: bool = True) -> str:
    predicate = _build_address_predicate(address)
    sql = f"""
SELECT
    'identity' AS section,
    concat('0x', lower(to_hex(address))) AS address,
    blockchain,
    name,
    category,
    source,
    label_type,
    CAST(NULL AS varchar) AS cex_name,
    CAST(NULL AS varchar) AS distinct_name,
    CAST(NULL AS varchar) AS added_by,
    CAST(NULL AS varchar) AS added_date,
    CAST(NULL AS varchar) AS first_deposit_token_standard,
    CAST(NULL AS varchar) AS first_deposit_token_address,
    CAST(NULL AS varchar) AS deposit_first_block_time,
    CAST(NULL AS varchar) AS consolidation_first_block_time,
    CAST(NULL AS bigint) AS deposit_count,
    CAST(NULL AS bigint) AS consolidation_count,
    CAST(NULL AS double) AS amount_deposited
FROM labels.ens
WHERE {predicate}
""".strip()
    if include_order_by:
        sql = f"{sql}\nORDER BY address, blockchain, name"
    return sql


def build_cex_address_sql(address: str | list[str] | tuple[str, ...], include_order_by: bool = True) -> str:
    predicate = _build_address_predicate(address)
    sql = f"""
SELECT
    'exchange_address' AS section,
    concat('0x', lower(to_hex(address))) AS address,
    blockchain,
    CAST(NULL AS varchar) AS name,
    CAST(NULL AS varchar) AS category,
    CAST(NULL AS varchar) AS source,
    CAST(NULL AS varchar) AS label_type,
    cex_name,
    distinct_name,
    added_by,
    CAST(added_date AS varchar) AS added_date,
    CAST(NULL AS varchar) AS first_deposit_token_standard,
    CAST(NULL AS varchar) AS first_deposit_token_address,
    CAST(NULL AS varchar) AS deposit_first_block_time,
    CAST(NULL AS varchar) AS consolidation_first_block_time,
    CAST(NULL AS bigint) AS deposit_count,
    CAST(NULL AS bigint) AS consolidation_count,
    CAST(NULL AS double) AS amount_deposited
FROM cex.addresses
WHERE {predicate}
""".strip()
    if include_order_by:
        sql = f"{sql}\nORDER BY address, blockchain, cex_name, distinct_name"
    return sql


def build_deposit_address_sql(address: str | list[str] | tuple[str, ...], include_order_by: bool = True) -> str:
    predicate = _build_address_predicate(address)
    sql = f"""
SELECT
    'deposit_address' AS section,
    concat('0x', lower(to_hex(address))) AS address,
    blockchain,
    CAST(NULL AS varchar) AS name,
    CAST(NULL AS varchar) AS category,
    CAST(NULL AS varchar) AS source,
    CAST(NULL AS varchar) AS label_type,
    cex_name,
    CAST(NULL AS varchar) AS distinct_name,
    CAST(NULL AS varchar) AS added_by,
    CAST(NULL AS varchar) AS added_date,
    first_deposit_token_standard,
    CASE
        WHEN first_deposit_token_address IS NULL THEN NULL
        ELSE concat('0x', lower(to_hex(first_deposit_token_address)))
    END AS first_deposit_token_address,
    CAST(deposit_first_block_time AS varchar) AS deposit_first_block_time,
    CAST(consolidation_first_block_time AS varchar) AS consolidation_first_block_time,
    CAST(deposit_count AS bigint) AS deposit_count,
    CAST(consolidation_count AS bigint) AS consolidation_count,
    amount_deposited
FROM cex.deposit_addresses
WHERE {predicate}
""".strip()
    if include_order_by:
        sql = f"{sql}\nORDER BY address, blockchain, cex_name"
    return sql


def build_lookup_sql(address: str | list[str] | tuple[str, ...]) -> str:
    sql = "\nUNION ALL\n".join(
        [
            build_identity_sql(address, include_order_by=False),
            build_cex_address_sql(address, include_order_by=False),
            build_deposit_address_sql(address, include_order_by=False),
        ]
    )
    return f"{sql}\nORDER BY address, blockchain, section"


def summarize_lookup_rows(
    address: str,
    identity_rows: list[dict[str, Any]] | None = None,
    exchange_rows: list[dict[str, Any]] | None = None,
    deposit_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = {
        "address": normalize_address(address) if len(address) == 42 else address,
        "identity": {"found": False, "rows": list(identity_rows or [])},
        "exchange": {
            "is_exchange": False,
            "address_rows": list(exchange_rows or []),
            "is_deposit_address": False,
            "deposit_rows": list(deposit_rows or [])},
    }
    summary["identity"]["found"] = bool(summary["identity"]["rows"])
    summary["exchange"]["is_exchange"] = bool(summary["exchange"]["address_rows"])
    summary["exchange"]["is_deposit_address"] = bool(summary["exchange"]["deposit_rows"])
    return summary


def summarize_lookup_results(
    addresses: str | list[str] | tuple[str, ...],
    identity_rows: list[dict[str, Any]] | None = None,
    exchange_rows: list[dict[str, Any]] | None = None,
    deposit_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized_addresses = parse_addresses(addresses)
    identity_rows = list(identity_rows or [])
    exchange_rows = list(exchange_rows or [])
    deposit_rows = list(deposit_rows or [])

    return [
        summarize_lookup_rows(
            address,
            identity_rows=[row for row in identity_rows if row.get("address") == address],
            exchange_rows=[row for row in exchange_rows if row.get("address") == address],
            deposit_rows=[row for row in deposit_rows if row.get("address") == address],
        )
        for address in normalized_addresses
    ]


def _run_sql_with_backoff(
    client: DuneClient,
    query_sql: str,
    ping_frequency: int = 5,
    max_attempts: int = 3,
    sleep_func=time.sleep,
):
    delay_seconds = 2
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.run_sql(query_sql=query_sql, ping_frequency=ping_frequency)
        except RetryError as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            sleep_func(delay_seconds)
            delay_seconds *= 2
    raise RuntimeError(
        "Dune API rate limited the request repeatedly (HTTP 429). Please wait and retry."
    ) from last_error


def run_lookup(address: str | list[str] | tuple[str, ...], api_key: str) -> dict[str, Any] | list[dict[str, Any]]:
    normalized_addresses = parse_addresses(address)
    client = DuneClient(api_key=api_key)
    lookup_result = _run_sql_with_backoff(client, build_lookup_sql(normalized_addresses))
    lookup_rows = lookup_result.get_rows()
    summaries = summarize_lookup_results(
        normalized_addresses,
        identity_rows=[row for row in lookup_rows if row.get("section") == "identity"],
        exchange_rows=[row for row in lookup_rows if row.get("section") == "exchange_address"],
        deposit_rows=[row for row in lookup_rows if row.get("section") == "deposit_address"],
    )
    if len(summaries) == 1:
        return summaries[0]
    return summaries


def render_text(summary: dict[str, Any] | list[dict[str, Any]]) -> str:
    if isinstance(summary, list):
        return "\n\n".join(render_text(item) for item in summary)

    identity = summary["identity"]
    exchange = summary["exchange"]
    lines = [f"Address: {summary['address']}", ""]
    lines.append("Identity:")
    if identity["found"]:
        for row in identity["rows"]:
            parts = [row.get("name") or "unknown-name", row.get("blockchain") or "unknown-chain"]
            if row.get("source"):
                parts.append(f"source={row['source']}")
            if row.get("category"):
                parts.append(f"category={row['category']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- No ENS/identity rows found")
    lines.append("")
    lines.append("Exchange ownership:")
    if exchange["is_exchange"]:
        for row in exchange["address_rows"]:
            parts = [row.get("cex_name") or "unknown-cex", row.get("blockchain") or "unknown-chain"]
            if row.get("distinct_name"):
                parts.append(f"label={row['distinct_name']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- Not found in cex.addresses")
    lines.append("")
    lines.append("User deposit address for exchanges:")
    if exchange["is_deposit_address"]:
        for row in exchange["deposit_rows"]:
            parts = [row.get("cex_name") or "unknown-cex", row.get("blockchain") or "unknown-chain"]
            if row.get("deposit_count") is not None:
                parts.append(f"deposit_count={row['deposit_count']}")
            lines.append(f"- {' | '.join(parts)}")
    else:
        lines.append("- Not found in cex.deposit_addresses")
    return "\n".join(lines)


class AddressIdentityTool(Tool):
    name = "address_identity"
    description = """
Look up ENS identity and exchange attribution for an address on Dune.
Returns identity labels (ENS names), exchange ownership, and user deposit addresses.
# Important Notes
- Always use ask_user to confirm whether to run this tool and remind the user it may take longer.
- This lookup can be 比较慢, especially for multiple addresses, and is useful for checking ENS and CEX attribution.
- After calling this tool, use address_mallicious and web_browser to look up the address on https://www.oklink.com/ to verify the result and gather more insights such as token risk, token metadata, and related addresses.
    """
    parameters = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The EVM address to inspect.",
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
            raise ValueError("DUNE_API_KEY is required")
        summary = run_lookup(address, api_key)
        return render_text(summary)


def main(address: str | list[str] | tuple[str, ...]) -> int:
    api_key = _load_api_key()
    if not api_key:
        print("Error: DUNE_API_KEY is required")
        return 1
    summary = run_lookup(address, api_key)
    print(render_text(summary))
    return 0


if __name__ == "__main__":
    addresses = ["0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB", "0xae61fa529ab284bdb10de06cac1ab7e60ffa0784"]
    raise SystemExit(main(addresses))
