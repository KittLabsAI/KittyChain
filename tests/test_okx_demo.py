from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

from kittychain.config import ApiConfig, Config
from demo.okx_client import OKXCredentials, build_headers, load_credentials, request


def test_load_credentials_reads_okx_config_fields():
    credentials = load_credentials(
        Config(apis=ApiConfig(okx_api_key="key", okx_secret_key="secret", okx_passphrase="pass"))
    )

    assert credentials == OKXCredentials(api_key="key", secret_key="secret", passphrase="pass")


def test_load_credentials_rejects_missing_values():
    with pytest.raises(ValueError, match="okx_api_key, okx_secret_key, okx_passphrase"):
        load_credentials(Config())


def test_build_headers_signs_get_path_with_query_string():
    credentials = OKXCredentials(api_key="key", secret_key="secret", passphrase="pass")

    headers = build_headers(
        credentials,
        "GET",
        "/api/v6/dex/market/token/search?chains=1&search=weth",
        timestamp="2026-04-30T00:00:00.000Z",
    )

    assert headers["OK-ACCESS-KEY"] == "key"
    assert headers["OK-ACCESS-PASSPHRASE"] == "pass"
    assert headers["OK-ACCESS-TIMESTAMP"] == "2026-04-30T00:00:00.000Z"
    assert headers["OK-ACCESS-SIGN"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, *, headers=None, data=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return FakeResponse({"code": "0"})


def test_request_signs_get_query_string():
    session = FakeSession()

    payload = request(
        "GET",
        "/api/v6/dex/market/token/search",
        params={"chains": "1", "search": "weth"},
        session=session,
        credentials=OKXCredentials(api_key="key", secret_key="secret", passphrase="pass"),
        timestamp="2026-04-30T00:00:00.000Z",
    )

    assert payload == {"code": "0"}
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://web3.okx.com/api/v6/dex/market/token/search?chains=1&search=weth"
    assert call["headers"]["OK-ACCESS-SIGN"]
    assert call["data"] is None


def test_request_signs_post_json_body():
    session = FakeSession()

    request(
        "POST",
        "/api/v6/dex/market/token/price-info",
        payload={"tokens": [{"chainIndex": "1", "tokenContractAddress": "0xabc"}]},
        session=session,
        credentials=OKXCredentials(api_key="key", secret_key="secret", passphrase="pass"),
        timestamp="2026-04-30T00:00:00.000Z",
    )

    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://web3.okx.com/api/v6/dex/market/token/price-info"
    assert call["data"] == '{"tokens":[{"chainIndex":"1","tokenContractAddress":"0xabc"}]}'


def test_token_search_calls_expected_path(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "demo.token_api.okx_request",
        lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {"code": "0"},
    )

    from demo.token_api import search_tokens

    assert search_tokens(chains="1", search="weth") == {"code": "0"}
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/api/v6/dex/market/token/search"
    assert calls[0][2]["params"]["chains"] == "1"
    assert calls[0][2]["params"]["search"] == "weth"


def test_portfolio_overview_calls_expected_path(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "demo.address_api.okx_request",
        lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {"code": "0"},
    )

    from demo.address_api import get_portfolio_overview

    assert get_portfolio_overview(chain_index="1", wallet_address="0xabc", time_frame="3") == {"code": "0"}
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/api/v6/dex/market/portfolio/overview"
    assert calls[0][2]["params"]["chainIndex"] == "1"
    assert calls[0][2]["params"]["walletAddress"] == "0xabc"
    assert calls[0][2]["params"]["timeFrame"] == "3"


def test_transactions_by_address_calls_expected_path(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "demo.transaction_api.okx_request",
        lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {"code": "0"},
    )

    from demo.transaction_api import get_transactions_by_address

    assert get_transactions_by_address(address="0xabc", chains="1") == {"code": "0"}
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/api/v6/dex/post-transaction/transactions-by-address"
    assert calls[0][2]["params"]["address"] == "0xabc"
    assert calls[0][2]["params"]["chains"] == "1"


@pytest.mark.parametrize("script", ["token_api.py", "address_api.py", "transaction_api.py"])
def test_demo_scripts_can_run_directly_to_imports(script, tmp_path):
    site_paths = [path for path in sys.path if "site-packages" in path or "dist-packages" in path]
    result = subprocess.run(
        [sys.executable, f"demo/{script}"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "HOME": str(tmp_path), "PYTHONPATH": os.pathsep.join(site_paths)},
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert "ModuleNotFoundError: No module named 'demo'" not in result.stderr
    assert "Missing OKX config fields" in result.stderr
