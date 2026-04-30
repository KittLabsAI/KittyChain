from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.okx_client import request as okx_request

SAMPLE_CHAIN_INDEX = "1"
SAMPLE_TOKEN_ADDRESS = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def search_tokens(chains: str = "1", search: str = "weth", cursor: str | None = None, limit: str | None = None) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/search",
        params={"chains": chains, "search": search, "cursor": cursor, "limit": limit},
    )


def get_token_basic_info(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
) -> Any:
    return okx_request(
        "POST",
        "/api/v6/dex/market/token/basic-info",
        payload={"chainIndex": chain_index, "tokenContractAddress": token_contract_address},
    )


def get_token_top_liquidity(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/top-liquidity",
        params={"chainIndex": chain_index, "tokenContractAddress": token_contract_address},
    )


def get_token_price_info(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
) -> Any:
    return okx_request(
        "POST",
        "/api/v6/dex/market/price-info",
        payload={"chainIndex": chain_index, "tokenContractAddress": token_contract_address},
    )


def get_token_advanced_info(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/advanced-info",
        params={"chainIndex": chain_index, "tokenContractAddress": token_contract_address},
    )


def get_token_trades(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
    after: str | None = None,
    limit: str = "10",
    tag_filter: str | None = None,
    wallet_address_filter: str | None = None,
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/trades",
        params={
            "chainIndex": chain_index,
            "tokenContractAddress": token_contract_address,
            "after": after,
            "limit": limit,
            "tagFilter": tag_filter,
            "walletAddressFilter": wallet_address_filter,
        },
    )


def get_hot_tokens(ranking_type: str = "4", chain_index: str | None = None, limit: str = "10") -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/hot-token",
        params={"rankingType": ranking_type, "chainIndex": chain_index, "limit": limit},
    )


def get_token_holders(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
    tag_filter: str | None = None,
    cursor: str | None = None,
    limit: str = "10",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/holder",
        params={
            "chainIndex": chain_index,
            "tokenContractAddress": token_contract_address,
            "tagFilter": tag_filter,
            "cursor": cursor,
            "limit": limit,
        },
    )


def get_token_cluster_top_holders(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
    range_filter: str = "1",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/cluster/top-holders",
        params={
            "chainIndex": chain_index,
            "tokenContractAddress": token_contract_address,
            "range": range_filter,
        },
    )


def get_token_top_traders(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
    tag_filter: str | None = None,
    cursor: str | None = None,
    limit: str = "10",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/token/top-trader",
        params={
            "chainIndex": chain_index,
            "tokenContractAddress": token_contract_address,
            "tagFilter": tag_filter,
            "cursor": cursor,
            "limit": limit,
        },
    )


def _print_result(name: str, payload: Any) -> None:
    print(f"\n{name}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_all() -> None:
    calls = [
        ("search_tokens", search_tokens),
        ("get_token_basic_info", get_token_basic_info),
        ("get_token_top_liquidity", get_token_top_liquidity),
        ("get_token_price_info", get_token_price_info),
        ("get_token_advanced_info", get_token_advanced_info),
        ("get_token_trades", get_token_trades),
        ("get_hot_tokens", get_hot_tokens),
        ("get_token_holders", get_token_holders),
        ("get_token_cluster_top_holders", get_token_cluster_top_holders),
        ("get_token_top_traders", get_token_top_traders),
    ]
    for name, func in calls:
        _print_result(name, func())


if __name__ == "__main__":
    _run_all()
