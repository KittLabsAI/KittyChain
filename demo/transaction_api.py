from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.okx_client import request as okx_request

SAMPLE_CHAIN_INDEX = "8453"
SAMPLE_WALLET_ADDRESS = "0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"
SAMPLE_TX_HASH = "0xa49232d1a4d275fd115b241414c5fe9a1c0532de339d9bce2371e03574ee4cab"


def get_transactions_by_address(
    address: str = SAMPLE_WALLET_ADDRESS,
    chains: str = "1",
    token_contract_address: str | None = None,
    begin: str | None = None,
    end: str | None = None,
    cursor: str | None = None,
    limit: str = "20",
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/post-transaction/transactions-by-address",
        params={
            "address": address,
            "chains": chains,
            "tokenContractAddress": token_contract_address,
            "begin": begin,
            "end": end,
            "cursor": cursor,
            "limit": limit,
        },
    )


def get_transaction_detail(
    chain_index: str = SAMPLE_CHAIN_INDEX,
    tx_hash: str = SAMPLE_TX_HASH,
    itype: str | None = None,
) -> Any:
    return okx_request(
        "GET",
        "/api/v6/dex/post-transaction/transaction-detail-by-txhash",
        params={"chainIndex": chain_index, "txHash": tx_hash, "iType": itype},
    )


def _print_result(name: str, payload: Any) -> None:
    print(f"\n{name}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_all() -> None:
    calls = [
        ("get_transactions_by_address", get_transactions_by_address),
        # ("get_transaction_detail", get_transaction_detail),
    ]
    for name, func in calls:
        _print_result(name, func())


if __name__ == "__main__":
    _run_all()
