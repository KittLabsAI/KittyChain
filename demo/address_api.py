from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.okx_client import request as okx_request

SAMPLE_CHAIN_INDEX = "1"
SAMPLE_WALLET_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
SAMPLE_TOKEN_ADDRESS = "0xdac17f958d2ee523a2206206994597c13d831ec7"


def get_portfolio_overview(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    wallet_address: str = SAMPLE_WALLET_ADDRESS,
    time_frame: str = "3",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/portfolio/overview",
        params={"chainIndex": chain_index, "walletAddress": wallet_address, "timeFrame": time_frame},
    )


def get_recent_pnl(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    wallet_address: str = SAMPLE_WALLET_ADDRESS,
    cursor: str | None = None,
    limit: str = "10",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/portfolio/recent-pnl",
        params={"chainIndex": chain_index, "walletAddress": wallet_address, "cursor": cursor, "limit": limit},
    )


def get_latest_pnl(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    wallet_address: str = SAMPLE_WALLET_ADDRESS,
    token_contract_address: str = SAMPLE_TOKEN_ADDRESS,
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/portfolio/token/latest-pnl",
        params={
            "chainIndex": chain_index,
            "walletAddress": wallet_address,
            "tokenContractAddress": token_contract_address,
        },
    )


def get_dex_history(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    wallet_address: str = SAMPLE_WALLET_ADDRESS,
    begin: str = "1700000000000",
    end: str = "1710000000000",
    token_contract_address: str | None = None,
    tx_type: str | None = None,
    cursor: str | None = None,
    limit: str = "10",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/market/portfolio/dex-history",
        params={
            "chainIndex": chain_index,
            "walletAddress": wallet_address,
            "begin": begin,
            "end": end,
            "tokenContractAddress": token_contract_address,
            "txType": tx_type,
            "cursor": cursor,
            "limit": limit,
        },
    )


def _print_result(name: str, payload: Any) -> None:
    print(f"\n{name}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_all() -> None:
    calls = [
        ("get_portfolio_overview", get_portfolio_overview),
        ("get_recent_pnl", get_recent_pnl),
        ("get_latest_pnl", get_latest_pnl),
        ("get_dex_history", get_dex_history),
    ]
    for name, func in calls:
        _print_result(name, func())


if __name__ == "__main__":
    _run_all()
