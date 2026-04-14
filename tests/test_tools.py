import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from requests import HTTPError
from requests.exceptions import RetryError

from kittychain.config import ApiConfig, Config
import kittychain.tools.agent as agent_module
import kittychain.tools.address_pattern as address_pattern_module
import kittychain.tools.address_identity as address_identity_module
import kittychain.tools.address_labels as address_labels_module
import kittychain.tools.address_mallicious as address_mallicious_module
import kittychain.tools.address_transfers as address_transfers_module
import kittychain.tools.ask_user as ask_user_module
import kittychain.tools.address_balance as address_balance_module
import kittychain.tools.bash as bash_module
import kittychain.tools.brief as brief_module
import kittychain.tools.edit as edit_module
import kittychain.tools.glob as glob_module
import kittychain.tools.grep as grep_module
import kittychain.tools.read as read_module
import kittychain.tools.social_search as social_search_module
import kittychain.tools.skill as skill_module
import kittychain.tools.token_holders as token_holders_module
import kittychain.tools.token_data as token_data_module
import kittychain.tools.token_market_data as token_market_data_module
import kittychain.tools.token_search as token_search_module
import kittychain.tools.token_security as token_security_module
import kittychain.tools.todo_write as todo_write_module
import kittychain.tools.web_browser as web_browser_module
import kittychain.tools.web_fetch as web_fetch_module
import kittychain.tools.web_search as web_search_module
import kittychain.tools.write as write_module
import kittychain.tools.write_report as write_report_module
from kittychain.tools.address_balance import render_balance_text, summarize_tokens
from kittychain.tools.address_identity import (
    _run_sql_with_backoff,
    build_cex_address_sql,
    build_deposit_address_sql,
    build_identity_sql,
    normalize_address,
    parse_addresses,
    render_text,
    summarize_lookup_rows,
    summarize_lookup_results,
)
from kittychain.tools.address_labels import (
    AddressLabelsTool,
    fetch_address_labels,
    main as address_labels_main,
    summarize_label_results,
)
from kittychain.tools.address_mallicious import render_security_text, summarize_security_result
from kittychain.tools.address_transfers import fetch_all_transfers, render_transfers_text, summarize_transfers
from kittychain.tools.token_holders import TokenHoldersTool, fetch_token_holders, main as token_holders_main
from kittychain.tools.token_data import TokenDataTool, fetch_token_data, main as token_data_main, render_text as render_token_data_text
from kittychain.tools.token_market_data import TokenMarketDataTool, fetch_token_market_data, main as token_market_data_main
from kittychain.tools.token_search import TokenSearchTool, fetch_token_search, main as token_search_main
from kittychain.tools.token_security import TokenSecurityTool, main as token_security_main, summarize_token_security_result


class ToolsTests(unittest.TestCase):
    def test_config_package_exposes_api_config(self):
        self.assertEqual(Config.from_file("/tmp/does-not-exist.json").apis, ApiConfig())

    def test_normalize_address_lowercases_and_validates(self):
        self.assertEqual(
            normalize_address("0xAbCDEFabcdefABCDEFabcdefABCDEFabcdef1234"),
            "0xabcdefabcdefabcdefabcdefabcdefabcdef1234",
        )
        with self.assertRaises(ValueError):
            normalize_address("0x1234")

    def test_parse_addresses_supports_multiple_inputs_and_deduplicates(self):
        self.assertEqual(
            parse_addresses(
                "0xAbCDEFabcdefABCDEFabcdefABCDEFabcdef1234,\n0xabcdefabcdefabcdefabcdefabcdefabcdef1234 "
                "0x1111111111111111111111111111111111111111"
            ),
            [
                "0xabcdefabcdefabcdefabcdefabcdefabcdef1234",
                "0x1111111111111111111111111111111111111111",
            ],
        )

    def test_address_pattern_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("address_pattern")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "address_pattern")

    def test_address_malicious_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("address_malicious")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "address_malicious")

    def test_web_browser_tool_is_registered_and_web_fetch_is_not(self):
        from kittychain.tools import get_tool

        tool = get_tool("web_browser")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "web_browser")
        self.assertIsNone(get_tool("web_fetch"))

    def test_write_report_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("write_report")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "write_report")

    def test_social_search_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("social_search")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "social_search")

    def test_token_search_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("token_search")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "token_search")

    def test_token_search_uses_package_data_path(self):
        self.assertEqual(
            token_search_module.TOKEN_LIST_PATH,
            Path(__file__).resolve().parent.parent / "kittychain" / "tools" / "data" / "token_list.json",
        )

    def test_social_search_tool_requires_query_lookback_days_and_depth(self):
        self.assertEqual(
            social_search_module.SocialSearchTool.parameters["required"],
            ["query", "lookback_days", "depth"],
        )

    def test_social_search_execute_combines_default_sources_and_reports_x_status(self):
        tool = social_search_module.SocialSearchTool()

        with (
            patch.object(social_search_module, "_search_reddit", return_value=[{"title": "Reddit thread"}]),
            patch.object(social_search_module, "_search_hackernews", return_value=[{"title": "HN post"}]),
            patch.object(social_search_module, "_search_polymarket", return_value=[{"title": "PM market"}]),
            patch.object(social_search_module, "_search_x", return_value={"available": False, "items": [], "reason": "AUTH_TOKEN/CT0 not configured"}),
        ):
            output = tool.execute(query="kittychian", lookback_days=30, depth="quick")

        self.assertIn('Social search results for "kittychian"', output)
        self.assertIn("reddit: 1 result", output)
        self.assertIn("hackernews: 1 result", output)
        self.assertIn("polymarket: 1 result", output)
        self.assertIn("x: unavailable (AUTH_TOKEN/CT0 not configured)", output)

    def test_infer_possible_chains_handles_known_formats_and_added_networks(self):
        self.assertEqual(
            address_pattern_module.infer_possible_chains("0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"),
            [
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
            ],
        )
        self.assertEqual(
            address_pattern_module.infer_possible_chains("addr1qxyz"),
            ["Cardano"],
        )
        self.assertEqual(
            address_pattern_module.infer_possible_chains("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb"),
            ["Tezos"],
        )
        self.assertEqual(
            address_pattern_module.infer_possible_chains("erd1qqqqqqqqqqqqqpgq9qv6t4g0z2vh7s0k8z9x4e"),
            ["MultiversX"],
        )
        self.assertEqual(
            address_pattern_module.infer_possible_chains("bitcoincash:qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a"),
            ["Bitcoin Cash"],
        )
        self.assertEqual(
            address_pattern_module.infer_possible_chains("nano_3e3j5tko6r7d4bz3x4k7s4a8q5m9o6t3e8d9k1c2y7n6m5p4q3r2s1t"),
            ["Nano"],
        )

    def test_tools_require_networks_parameter(self):
        self.assertEqual(
            address_balance_module.AddressBalanceTool.parameters["required"],
            ["address", "networks"],
        )
        self.assertEqual(
            address_labels_module.AddressLabelsTool.parameters["required"],
            ["address", "networks"],
        )
        self.assertEqual(
            address_transfers_module.AddressTransfersTool.parameters["required"],
            ["address", "networks"],
        )

    def test_resolve_supported_networks_validates_chain_names(self):
        self.assertEqual(
            address_balance_module.resolve_supported_networks(["Ethereum", "Base"]),
            ["eth-mainnet", "base-mainnet"],
        )
        self.assertEqual(
            address_transfers_module.resolve_supported_networks(["Ethereum", "Base"]),
            ["eth-mainnet", "base-mainnet"],
        )
        self.assertEqual(
            address_labels_module.resolve_supported_chain_ids(["Ethereum", "Base"]),
            [1, 8453],
        )

        with self.assertRaises(ValueError):
            address_balance_module.resolve_supported_networks(["Unknown"])
        with self.assertRaises(ValueError):
            address_labels_module.resolve_supported_chain_ids(["Unknown"])
        with self.assertRaises(ValueError):
            address_transfers_module.resolve_supported_networks(["Unknown"])

    def test_address_pattern_tool_execute_reports_candidates(self):
        tool = address_pattern_module.AddressPatternTool()

        output = tool.execute(address="TNPeeaaFB7K9cmo4uQpcU32zGK8G1NYqeL")

        self.assertIn("Address: TNPeeaaFB7K9cmo4uQpcU32zGK8G1NYqeL", output)
        self.assertIn("- TRON", output)

    def test_address_pattern_tool_handles_unknown_format(self):
        tool = address_pattern_module.AddressPatternTool()

        output = tool.execute(address="not-an-address")

        self.assertIn("Possible chains: none matched", output)
        self.assertIn("could not map this address pattern", output.lower())

    def test_individual_sql_builders_target_only_their_own_tables(self):
        address = "0xabcdefabcdefabcdefabcdefabcdefabcdef1234"

        identity_sql = build_identity_sql(address)
        self.assertIn("labels.ens", identity_sql)
        self.assertNotIn("cex.addresses", identity_sql)
        self.assertNotIn("cex.deposit_addresses", identity_sql)

        cex_sql = build_cex_address_sql(address)
        self.assertIn("cex.addresses", cex_sql)
        self.assertNotIn("labels.ens", cex_sql)
        self.assertNotIn("cex.deposit_addresses", cex_sql)

        deposit_sql = build_deposit_address_sql(address)
        self.assertIn("cex.deposit_addresses", deposit_sql)
        self.assertNotIn("labels.ens", deposit_sql)
        self.assertNotIn("cex.addresses", deposit_sql)

    def test_build_lookup_sql_queries_all_three_sources_once(self):
        sql_builder = getattr(address_identity_module, "build_lookup_sql", None)
        self.assertIsNotNone(sql_builder)

        sql = sql_builder("0xabcdefabcdefabcdefabcdefabcdefabcdef1234")
        self.assertIn("labels.ens", sql)
        self.assertIn("cex.addresses", sql)
        self.assertIn("cex.deposit_addresses", sql)
        self.assertEqual(sql.count("UNION ALL"), 2)
        self.assertEqual(sql.upper().count("ORDER BY"), 1)
        self.assertIn("CAST(NULL AS varchar) AS cex_name", sql)
        self.assertIn("CAST(NULL AS varchar) AS name", sql)
        self.assertIn("CAST(NULL AS bigint) AS deposit_count", sql)

    def test_sql_builders_support_multiple_addresses(self):
        addresses = [
            "0xabcdefabcdefabcdefabcdefabcdefabcdef1234",
            "0x1111111111111111111111111111111111111111",
        ]
        identity_sql = build_identity_sql(addresses)
        self.assertIn("address IN (0xabcdefabcdefabcdefabcdefabcdefabcdef1234, 0x1111111111111111111111111111111111111111)", identity_sql)
        self.assertIn("AS address", identity_sql)

    def test_summarize_lookup_rows_groups_identity_and_exchange_hits(self):
        identity_rows = [
            {"section": "identity", "blockchain": "ethereum", "name": "vitalik.eth", "category": "ens"}
        ]
        exchange_rows = [
            {"section": "exchange_address", "blockchain": "ethereum", "cex_name": "binance", "distinct_name": "binance 14"}
        ]
        deposit_rows = [
            {"section": "deposit_address", "blockchain": "base", "cex_name": "binance", "deposit_count": 12}
        ]
        summary = summarize_lookup_rows(
            "0xabc",
            identity_rows=identity_rows,
            exchange_rows=exchange_rows,
            deposit_rows=deposit_rows,
        )
        self.assertTrue(summary["identity"]["found"])
        self.assertEqual(summary["identity"]["rows"][0]["name"], "vitalik.eth")
        self.assertTrue(summary["exchange"]["is_exchange"])
        self.assertEqual(summary["exchange"]["address_rows"][0]["cex_name"], "binance")
        self.assertTrue(summary["exchange"]["is_deposit_address"])
        self.assertEqual(summary["exchange"]["deposit_rows"][0]["blockchain"], "base")

    def test_summarize_lookup_results_groups_rows_per_address(self):
        summaries = summarize_lookup_results(
            [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
            identity_rows=[
                {"address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "name": "alice.eth", "blockchain": "ethereum"}
            ],
            exchange_rows=[
                {"address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "cex_name": "binance", "blockchain": "base"}
            ],
            deposit_rows=[],
        )
        self.assertEqual(len(summaries), 2)
        self.assertTrue(summaries[0]["identity"]["found"])
        self.assertFalse(summaries[0]["exchange"]["is_exchange"])
        self.assertFalse(summaries[1]["identity"]["found"])
        self.assertTrue(summaries[1]["exchange"]["is_exchange"])

    def test_summarize_label_results_merges_multiple_chains_without_chain_names(self):
        address = "0x28c6c06298d514db089934071355e5743bf21d60"
        summaries = summarize_label_results(
            [address],
            [
                {
                    "data": {
                        address: [
                            {"category": "cex", "tags": ["Binance Hot Wallet", "Centralized Exchange"]},
                            {"category": "institution", "tags": ["Binance 14"]},
                        ]
                    }
                },
                {
                    "data": {
                        address: [
                            {"category": "cex", "tags": ["Binance Hot Wallet", "Centralized Exchange"]},
                            {"category": "donor", "tags": ["Ukraine Donations Donor"]},
                        ]
                    }
                },
            ],
        )

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["address"], address)
        self.assertEqual(
            summaries[0]["labels"],
            [
                {"category": "cex", "tags": ["Binance Hot Wallet", "Centralized Exchange"]},
                {"category": "donor", "tags": ["Ukraine Donations Donor"]},
                {"category": "institution", "tags": ["Binance 14"]},
            ],
        )
        self.assertTrue(all("chain" not in item for item in summaries[0]["labels"]))

    def test_fetch_address_labels_queries_each_address_on_all_supported_chains(self):
        calls = []

        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
                address = params["address"]
                return FakeResponse(
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            address: [
                                {"category": "cex", "tags": [f"Label for {params['chain_id']}"]},
                            ]
                        },
                    }
                )

        summaries = fetch_address_labels(
            [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
            "test-key",
            networks=list(address_labels_module.SUPPORTED_CHAINS),
            session=FakeSession(),
        )

        self.assertEqual(len(calls), len(address_labels_module.SUPPORTED_CHAINS) * 2)
        self.assertEqual(
            sorted({call["params"]["chain_id"] for call in calls}),
            sorted(address_labels_module.SUPPORTED_CHAINS.values()),
        )
        self.assertTrue(all(call["headers"]["x-api-key"] == "test-key" for call in calls))
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["address"], "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(summaries[1]["address"], "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    def test_fetch_address_labels_spaces_requests_evenly_under_rate_limit(self):
        calls = []
        sleeps = []
        clock = {"now": 0.0}

        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append(params["chain_id"])
                address = params["address"]
                return FakeResponse(
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {address: [{"category": "cex", "tags": [str(params["chain_id"])]}]},
                    }
                )

        def fake_time():
            return clock["now"]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["now"] += seconds

        fetch_address_labels(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "test-key",
            networks=list(address_labels_module.SUPPORTED_CHAINS),
            session=FakeSession(),
            time_func=fake_time,
            sleep_func=fake_sleep,
        )

        self.assertEqual(len(calls), len(address_labels_module.SUPPORTED_CHAINS))
        self.assertEqual(len(sleeps), len(address_labels_module.SUPPORTED_CHAINS) - 1)
        for seconds in sleeps:
            self.assertAlmostEqual(seconds, 1 / address_labels_module.RATE_LIMIT_PER_SECOND)

    def test_fetch_labels_for_chain_retries_after_429(self):
        sleeps = []
        calls = []

        class FakeHTTPResponse:
            status_code = 429
            headers = {"Retry-After": "1"}

        class FakeResponse:
            def __init__(self, payload, should_fail=False):
                self.payload = payload
                self.should_fail = should_fail

            def raise_for_status(self):
                if self.should_fail:
                    raise HTTPError("429 Too Many Requests", response=FakeHTTPResponse())
                return None

            def json(self):
                return self.payload

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append(params["chain_id"])
                if len(calls) == 1:
                    return FakeResponse({}, should_fail=True)
                return FakeResponse(
                    {
                        "code": 0,
                        "message": "ok",
                        "data": {
                            params["address"]: [
                                {"category": "cex", "tags": ["retried"]},
                            ]
                        },
                    }
                )

        payload = address_labels_module._fetch_labels_for_chain(
            FakeSession(),
            "test-key",
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            1,
            sleep_func=sleeps.append,
        )

        self.assertEqual(calls, [1, 1])
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(
            payload["data"]["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"][0]["tags"],
            ["retried"],
        )

    def test_address_labels_tool_requires_api_key(self):
        tool = AddressLabelsTool()
        original = address_labels_module._load_api_key
        address_labels_module._load_api_key = lambda: ""
        try:
            with self.assertRaises(ValueError):
                tool.execute("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", ["Ethereum"])
        finally:
            address_labels_module._load_api_key = original

    def test_address_labels_main_returns_success_and_prints_output(self):
        original_load_api_key = address_labels_module._load_api_key
        original_fetch = address_labels_module.fetch_address_labels
        original_render = address_labels_module.render_text
        try:
            address_labels_module._load_api_key = lambda: "test-key"
            address_labels_module.fetch_address_labels = lambda address, api_key, networks: {
                "address": address,
                "labels": [{"category": "cex", "tags": ["Binance Hot Wallet"]}],
            }
            address_labels_module.render_text = lambda summary: f"rendered:{summary['address']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = address_labels_main("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", ["Ethereum"])
        finally:
            address_labels_module._load_api_key = original_load_api_key
            address_labels_module.fetch_address_labels = original_fetch
            address_labels_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    def test_fetch_token_holders_returns_top_holders_only(self):
        calls = []
        sleeps = []
        clock = {"now": 0.0}

        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self.payload

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "params": params})
                return FakeResponse(
                    {
                        "code": 0,
                        "message": "ok",
                        "data": [
                            {
                                "wallet_address": "0x1111111111111111111111111111111111111111",
                                "original_amount": "1000",
                                "usd_value": "1230",
                            },
                            {
                                "wallet_address": "0x2222222222222222222222222222222222222222",
                                "amount": "500",
                                "usd_value": "615",
                            },
                        ],
                    }
                )

        def fake_time():
            return clock["now"]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["now"] += seconds

        summary = fetch_token_holders(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
            "test-key",
            session=FakeSession(),
            time_func=fake_time,
            sleep_func=fake_sleep,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            summary["top_holders"][0],
            {
                "wallet_address": "0x1111111111111111111111111111111111111111",
                "amount": 1000.0,
                "usd_value": 1230.0,
            },
        )
        self.assertEqual(len(sleeps), 0)

    def test_fetch_token_market_data_uses_names_parameter(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {
                        "id": "usd-coin",
                        "symbol": "usdc",
                        "name": "USD Coin",
                        "current_price": 1.0,
                        "market_cap": 100,
                        "market_cap_rank": 7,
                        "fully_diluted_valuation": 110,
                        "total_volume": 50,
                        "last_updated": "2026-04-13T00:00:00.000Z",
                    }
                ]

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
                return FakeResponse()

        result = fetch_token_market_data(token_names=["USD Coin"], token_symbols=None, api_key="cg-key", session=FakeSession())

        self.assertEqual(result[0]["id"], "usd-coin")
        self.assertEqual(calls[0]["params"]["names"], "USD Coin")
        self.assertEqual(calls[0]["params"]["vs_currency"], "usd")

    def test_fetch_token_market_data_uses_symbols_and_include_tokens_all(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return []

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
                return FakeResponse()

        fetch_token_market_data(token_names=None, token_symbols=["USDC", "USDT"], api_key="cg-key", session=FakeSession())

        self.assertEqual(calls[0]["params"]["symbols"], "USDC,USDT")
        self.assertEqual(calls[0]["params"]["include_tokens"], "all")

    def test_fetch_token_data_uses_search_then_coin_details_with_required_params(self):
        calls = []

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeSession:
            def get(self, url, headers=None, params=None, timeout=None):
                calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
                if url.endswith("/search"):
                    return FakeResponse(
                        {
                            "coins": [
                                {"id": "usd-coin", "symbol": "usdc", "name": "USD Coin"},
                            ]
                        }
                    )
                return FakeResponse(
                    {
                        "id": "usd-coin",
                        "symbol": "usdc",
                        "name": "USD Coin",
                        "categories": ["Stablecoins"],
                        "links": {},
                        "market_cap_rank": 7,
                        "market_cap_rank_with_rehypothecated": 8,
                        "developer_data": {"stars": 10},
                        "tickers": [],
                    }
                )

        result = fetch_token_data(token_name="USD Coin", token_symbol=None, api_key="cg-key", session=FakeSession())

        self.assertEqual(result["id"], "usd-coin")
        self.assertEqual(calls[0]["params"], {"query": "USD Coin"})
        self.assertEqual(
            calls[1]["params"],
            {
                "localization": "false",
                "tickers": "true",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "true",
                "sparkline": "false",
                "include_categories_details": "false",
                "dex_pair_format": "contract_address",
            },
        )

    def test_render_token_data_text_includes_links_market_summary_and_usdt_details(self):
        text = render_token_data_text(
            {
                "id": "usd-coin",
                "symbol": "usdc",
                "name": "USD Coin",
                "categories": ["Stablecoins", "Ethereum Ecosystem"],
                "links": {
                    "homepage": ["https://www.circle.com/usdc"],
                    "blockchain_site": ["https://etherscan.io/token/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"],
                    "official_forum_url": [],
                    "chat_url": ["https://discord.gg/circle"],
                    "announcement_url": [],
                    "twitter_screen_name": "circle",
                    "facebook_username": "",
                    "telegram_channel_identifier": "circlepay",
                    "subreddit_url": "https://reddit.com/r/USDCoin",
                    "repos_url": {"github": ["https://github.com/circlefin"]},
                },
                "market_cap_rank": 7,
                "market_cap_rank_with_rehypothecated": 8,
                "developer_data": {"stars": 10, "forks": 5},
                "tickers": [
                    {
                        "market": {"name": "Binance"},
                        "target": "USDT",
                        "base": "USDC",
                        "last": 0.9999,
                        "volume": 1000,
                        "bid_ask_spread_percentage": 0.1,
                        "coin_mcap_usd": 50000000,
                        "converted_last": {"usd": 1.0},
                        "converted_volume": {"usd": 1000000},
                    },
                    {
                        "market": {"name": "Bybit"},
                        "target": "USDT",
                        "base": "USDC",
                        "last": 1.0001,
                        "volume": 2000,
                        "bid_ask_spread_percentage": 0.2,
                        "coin_mcap_usd": 51000000,
                        "converted_last": {"usd": 1.01},
                        "converted_volume": {"usd": 3000000},
                    },
                    {
                        "market": {"name": "Binance"},
                        "target": "BTC",
                        "base": "USDC",
                        "last": 0.00001,
                        "volume": 100,
                        "bid_ask_spread_percentage": 0.3,
                        "coin_mcap_usd": 52000000,
                        "converted_last": {"usd": 0.95},
                        "converted_volume": {"usd": 10000},
                    },
                ],
            }
        )

        self.assertIn("categories: Stablecoins, Ethereum Ecosystem", text)
        self.assertIn("homepage: https://www.circle.com/usdc", text)
        self.assertIn("twitter_screen_name: https://twitter.com/circle", text)
        self.assertIn("telegram_channel_identifier: https://t.me/circlepay", text)
        self.assertIn("repos_url.github: https://github.com/circlefin", text)
        self.assertIn("listing_markets: Binance, Bybit", text)
        self.assertIn("converted_last.usd_sum: 2.01", text)
        self.assertIn("converted_volume.usd_sum: 4000000.0", text)
        self.assertIn("bid_ask_spread_percentage_weighted_avg: 0.175", text)
        self.assertIn("coin_mcap_usd_sum: 101000000.0", text)
        self.assertIn("1. Binance USDC/USDT", text)
        self.assertIn("2. Bybit USDC/USDT", text)

    def test_token_data_tool_is_registered(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key="cg-key"))
            tool = tools_module.get_tool("token_data", tools=tools_module.create_tool_instances())
        finally:
            tools_module.Config.from_file = original_from_file

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "token_data")

    def test_create_tool_instances_skips_token_data_without_coingecko_api_key(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key=""))
            tools = tools_module.create_tool_instances()
        finally:
            tools_module.Config.from_file = original_from_file

        tool_names = [tool.name for tool in tools]
        self.assertNotIn("token_data", tool_names)

    def test_create_tool_instances_includes_token_data_with_coingecko_api_key(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key="cg-key"))
            tools = tools_module.create_tool_instances()
        finally:
            tools_module.Config.from_file = original_from_file

        tool_names = [tool.name for tool in tools]
        self.assertIn("token_data", tool_names)

    def test_fetch_token_search_reads_local_cache_and_matches_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token_list.json"
            cache_path.write_text(
                """
[
  {
    "id": "seedify-fund",
    "symbol": "SFUND",
    "name": "Seedify.fund",
    "platforms": {
      "ethereum": "0xabc",
      "binance-smart-chain": "0xdef"
    }
  },
  {
    "id": "seedify-fund-bridged",
    "symbol": "SFUND",
    "name": "Seedify.fund",
    "platforms": {
      "base": "0x123"
    }
  },
  {
    "id": "other",
    "symbol": "OTHER",
    "name": "Other",
    "platforms": {}
  }
]
""".strip()
            )
            original_path = token_search_module.TOKEN_LIST_PATH
            original_load_key = token_search_module._load_coingecko_api_key
            try:
                token_search_module.TOKEN_LIST_PATH = cache_path
                token_search_module._load_coingecko_api_key = lambda: ""

                summary = fetch_token_search(token_symbol="sfund", token_name=None)
            finally:
                token_search_module.TOKEN_LIST_PATH = original_path
                token_search_module._load_coingecko_api_key = original_load_key

        self.assertEqual([item["id"] for item in summary], ["seedify-fund", "seedify-fund-bridged"])
        self.assertEqual(summary[0]["platforms"], {"ethereum": "0xabc", "binance-smart-chain": "0xdef"})

    def test_fetch_token_search_refreshes_stale_cache_when_coingecko_key_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token_list.json"
            cache_path.write_text("[]")
            stale_time = 1_700_000_000 - (2 * 24 * 60 * 60)
            os.utime(cache_path, (stale_time, stale_time))
            original_path = token_search_module.TOKEN_LIST_PATH
            original_load_key = token_search_module._load_coingecko_api_key
            original_refresh = token_search_module._refresh_token_list_cache
            try:
                token_search_module.TOKEN_LIST_PATH = cache_path
                token_search_module._load_coingecko_api_key = lambda: "cg-key"
                token_search_module._refresh_token_list_cache = lambda api_key, session=None, timeout=20: [
                    {
                        "id": "seedify-fund",
                        "symbol": "SFUND",
                        "name": "Seedify.fund",
                        "platforms": {"ethereum": "0xabc"},
                    }
                ]

                summary = fetch_token_search(token_symbol="SFUND", token_name=None, now=1_700_000_000)
            finally:
                token_search_module.TOKEN_LIST_PATH = original_path
                token_search_module._load_coingecko_api_key = original_load_key
                token_search_module._refresh_token_list_cache = original_refresh

            self.assertEqual([item["id"] for item in summary], ["seedify-fund"])
            self.assertIn("seedify-fund", cache_path.read_text())

    def test_fetch_token_search_falls_back_to_dexscreener_when_cache_too_old_without_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token_list.json"
            cache_path.write_text("[]")
            stale_time = 1_700_000_000 - (8 * 24 * 60 * 60)
            os.utime(cache_path, (stale_time, stale_time))
            original_path = token_search_module.TOKEN_LIST_PATH
            original_load_key = token_search_module._load_coingecko_api_key
            original_dex = token_search_module._search_dexscreener
            try:
                token_search_module.TOKEN_LIST_PATH = cache_path
                token_search_module._load_coingecko_api_key = lambda: ""
                token_search_module._search_dexscreener = lambda token_symbol, token_name, session=None, timeout=20: [
                    {
                        "id": "fallback",
                        "symbol": "SFUND",
                        "name": "Seedify.fund",
                        "platforms": {"bsc": "0xdef"},
                    }
                ]

                summary = fetch_token_search(token_symbol="SFUND", token_name=None, now=1_700_000_000)
            finally:
                token_search_module.TOKEN_LIST_PATH = original_path
                token_search_module._load_coingecko_api_key = original_load_key
                token_search_module._search_dexscreener = original_dex

        self.assertEqual(summary, [{"id": "fallback", "symbol": "SFUND", "name": "Seedify.fund", "platforms": {"bsc": "0xdef"}}])

    def test_refresh_token_list_cache_uses_demo_endpoint_and_header(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [{"id": "seedify-fund", "symbol": "SFUND", "name": "Seedify.fund", "platforms": {}}]

        class FakeSession:
            def get(self, url, params=None, timeout=None, headers=None):
                calls.append({"url": url, "params": params, "timeout": timeout, "headers": headers})
                return FakeResponse()

        result = token_search_module._refresh_token_list_cache("cg-key", session=FakeSession())

        self.assertEqual(result[0]["id"], "seedify-fund")
        self.assertEqual(calls[0]["url"], "https://api.coingecko.com/api/v3/coins/list")
        self.assertEqual(calls[0]["params"], {"include_platform": "true"})
        self.assertEqual(calls[0]["headers"]["x-cg-demo-api-key"], "cg-key")

    def test_token_search_tool_requires_symbol_or_name(self):
        result = TokenSearchTool().execute(token_symbol="", token_name="")

        self.assertEqual(result, "Error: token_symbol or token_name is required")

    def test_token_search_tool_supports_name_only_search(self):
        original_fetch = token_search_module.fetch_token_search
        try:
            token_search_module.fetch_token_search = lambda token_symbol, token_name, session=None, timeout=20: [
                {
                    "id": "seedify-fund",
                    "name": "Seedify.fund",
                    "symbol": "SFUND",
                    "platforms": {"ethereum": "0xabc"},
                }
            ]

            result = TokenSearchTool().execute(token_symbol="", token_name="Seedify.fund")
        finally:
            token_search_module.fetch_token_search = original_fetch

        self.assertIn("Token search results", result)
        self.assertIn("seedify-fund", result)
        self.assertIn("Seedify.fund", result)
        self.assertIn("ethereum: 0xabc", result)

    def test_token_search_main_returns_success_and_prints_output(self):
        original_fetch = token_search_module.fetch_token_search
        original_render = token_search_module.render_text
        try:
            token_search_module.fetch_token_search = lambda token_symbol, token_name, session=None, timeout=20: [
                {
                    "id": "seedify-fund",
                    "name": "Seedify.fund",
                    "symbol": "SFUND",
                    "platforms": {"ethereum": "0xabc"},
                }
            ]
            token_search_module.render_text = lambda summary: f"rendered:{summary[0]['id']}:{summary[0]['symbol']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_search_main("SFUND", "")
        finally:
            token_search_module.fetch_token_search = original_fetch
            token_search_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:seedify-fund:SFUND")

    def test_token_holders_tool_description_mentions_chain_ids(self):
        description = TokenHoldersTool.parameters["properties"]["chain_id"]["description"]
        self.assertIn("Ethereum=1", description)
        self.assertIn("Merlin=4200", description)

    def test_tool_descriptions_include_investigation_guidance(self):
        self.assertIn("oklink.com", web_browser_module.WebBrowserTool.description.lower())
        self.assertIn("web_browser", address_mallicious_module.AddressMalliciousTool.description)
        self.assertIn("address_labels", address_mallicious_module.AddressMalliciousTool.description)
        self.assertIn("address_balance", address_mallicious_module.AddressMalliciousTool.description)
        self.assertIn("address_transfers", address_mallicious_module.AddressMalliciousTool.description)

        self.assertIn("3-5", address_transfers_module.AddressTransfersTool.description)
        self.assertIn("address_malicious", address_transfers_module.AddressTransfersTool.description)
        self.assertIn("address_pattern", address_transfers_module.AddressTransfersTool.description)

        self.assertIn("address_pattern", address_balance_module.AddressBalanceTool.description)
        self.assertIn("candidate chain names", address_balance_module.AddressBalanceTool.description)

        self.assertIn("address_pattern", address_labels_module.AddressLabelsTool.description)
        self.assertIn("candidate chain names", address_labels_module.AddressLabelsTool.description)

        self.assertIn("比较慢", address_identity_module.AddressIdentityTool.description)
        self.assertIn("CEX", address_identity_module.AddressIdentityTool.description)
        self.assertIn("ask_user", address_identity_module.AddressIdentityTool.description)
        self.assertIn("address_malicious", address_identity_module.AddressIdentityTool.description)

        self.assertIn("top holders", token_holders_module.TokenHoldersTool.description)
        self.assertIn("address_malicious", token_holders_module.TokenHoldersTool.description)

        self.assertIn("progress updates", brief_module.BriefTool.description)

        self.assertIn("fresh external sources", web_search_module.WebSearchTool.description)

    def test_token_holders_main_returns_success_and_prints_output(self):
        original_load_api_key = token_holders_module._load_api_key
        original_fetch = token_holders_module.fetch_token_holders
        original_render = token_holders_module.render_text
        try:
            token_holders_module._load_api_key = lambda: "test-key"
            token_holders_module.fetch_token_holders = lambda token_address, chain_id, api_key: {
                "token_address": token_address,
                "chain_id": chain_id,
                "top_holders": [],
            }
            token_holders_module.render_text = lambda summary: f"rendered:{summary['token_address']}:{summary['chain_id']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_holders_main(
                    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                    1,
                )
        finally:
            token_holders_module._load_api_key = original_load_api_key
            token_holders_module.fetch_token_holders = original_fetch
            token_holders_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48:1")

    def test_token_market_data_tool_is_registered(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key="cg-key"))
            tool = tools_module.get_tool("token_market_data", tools=tools_module.create_tool_instances())
        finally:
            tools_module.Config.from_file = original_from_file

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "token_market_data")

    def test_create_tool_instances_skips_token_market_data_without_coingecko_api_key(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key=""))
            tools = tools_module.create_tool_instances()
        finally:
            tools_module.Config.from_file = original_from_file

        tool_names = [tool.name for tool in tools]
        self.assertNotIn("token_market_data", tool_names)

    def test_create_tool_instances_includes_token_market_data_with_coingecko_api_key(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key="cg-key"))
            tools = tools_module.create_tool_instances()
        finally:
            tools_module.Config.from_file = original_from_file

        tool_names = [tool.name for tool in tools]
        self.assertIn("token_market_data", tool_names)

    def test_create_tool_instances_never_loads_edit_or_write_tools(self):
        import kittychain.tools as tools_module

        original_from_file = tools_module.Config.from_file
        try:
            tools_module.Config.from_file = lambda *args, **kwargs: SimpleNamespace(apis=SimpleNamespace(coingecko_api_key="cg-key"))
            tools = tools_module.create_tool_instances()
        finally:
            tools_module.Config.from_file = original_from_file

        tool_names = [tool.name for tool in tools]
        self.assertNotIn("edit", tool_names)
        self.assertNotIn("write", tool_names)

    def test_token_holders_tool_is_registered(self):
        from kittychain.tools import get_tool

        tool = get_tool("token_holders")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "token_holders")

    def test_token_market_data_tool_requires_names_or_symbols(self):
        result = TokenMarketDataTool().execute(token_names=None, token_symbols=None)

        self.assertEqual(result, "Error: token_names or token_symbols is required")

    def test_token_data_tool_requires_name_or_symbol(self):
        result = TokenDataTool().execute(token_name="", token_symbol="")

        self.assertEqual(result, "Error: token_name or token_symbol is required")

    def test_token_data_main_returns_success_and_prints_output(self):
        original_load_api_key = token_data_module._load_coingecko_api_key
        original_fetch = token_data_module.fetch_token_data
        original_render = token_data_module.render_text
        try:
            token_data_module._load_coingecko_api_key = lambda: "cg-key"
            token_data_module.fetch_token_data = lambda token_name, token_symbol, api_key, session=None, timeout=20: {
                "id": "usd-coin",
                "symbol": "usdc",
            }
            token_data_module.render_text = lambda payload: f"rendered:{payload['id']}:{payload['symbol']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_data_main(token_name="USD Coin", token_symbol="")
        finally:
            token_data_module._load_coingecko_api_key = original_load_api_key
            token_data_module.fetch_token_data = original_fetch
            token_data_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:usd-coin:usdc")

    def test_token_market_data_main_returns_success_and_prints_output(self):
        original_load_api_key = token_market_data_module._load_coingecko_api_key
        original_fetch = token_market_data_module.fetch_token_market_data
        original_render = token_market_data_module.render_text
        try:
            token_market_data_module._load_coingecko_api_key = lambda: "cg-key"
            token_market_data_module.fetch_token_market_data = lambda token_names, token_symbols, api_key, session=None, timeout=20: [
                {"id": "usd-coin", "symbol": "usdc", "name": "USD Coin"}
            ]
            token_market_data_module.render_text = lambda rows: f"rendered:{rows[0]['id']}:{rows[0]['symbol']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_market_data_main(token_names=["USD Coin"], token_symbols=None)
        finally:
            token_market_data_module._load_coingecko_api_key = original_load_api_key
            token_market_data_module.fetch_token_market_data = original_fetch
            token_market_data_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:usd-coin:usdc")

    def test_summarize_token_security_result_extracts_flags_and_sections(self):
        raw = {
            "result": {
                "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
                    "token_name": "USD Coin",
                    "token_symbol": "USDC",
                    "is_honeypot": "0",
                    "is_blacklisted": "1",
                    "is_open_source": "1",
                    "buy_tax": "0.01",
                    "sell_tax": "0.02",
                    "holders": [
                        {"address": "0x111", "balance": "100", "percent": "0.1", "tag": "whale"}
                    ],
                    "lp_holders": [
                        {"address": "0x222", "balance": "50", "percent": "0.05", "tag": "lp"}
                    ],
                    "dex": [
                        {"name": "Uniswap", "pair": "0x333", "liquidity": "1000000"}
                    ],
                }
            }
        }

        summary = summarize_token_security_result(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
            raw,
        )

        self.assertEqual(summary["token_address"], "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
        self.assertEqual(summary["chain_id"], 1)
        self.assertTrue(summary["security"]["is_malicious"])
        self.assertIn("is_blacklisted", summary["security"]["positive_flags"])
        self.assertEqual(summary["holders"][0]["address"], "0x111")
        self.assertEqual(summary["lp_holders"][0]["address"], "0x222")
        self.assertEqual(summary["dex"][0]["name"], "Uniswap")

    def test_summarize_token_security_result_falls_back_to_single_result_entry(self):
        raw = {
            "result": {
                "USDC": {
                    "token_name": "USD Coin",
                    "is_blacklisted": "1",
                    "holders": [{"address": "0x111", "balance": "100", "percent": "0.1", "tag": "whale"}],
                    "lp_holders": [],
                    "dex": [{"name": "Uniswap", "pair": "0x333", "liquidity": "1000000"}],
                }
            }
        }

        summary = summarize_token_security_result(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
            raw,
        )

        self.assertTrue(summary["security"]["is_malicious"])
        self.assertIn("is_blacklisted", summary["security"]["positive_flags"])
        self.assertEqual(summary["holders"][0]["address"], "0x111")
        self.assertEqual(summary["dex"][0]["name"], "Uniswap")

    def test_token_security_tool_description_mentions_chain_ids(self):
        description = TokenSecurityTool.parameters["properties"]["chain_id"]["description"]
        self.assertIn("1=Ethereum", description)
        self.assertIn("tron=Tron", description)
        self.assertIn("4200=Merlin", description)

    def test_token_security_main_returns_success_and_prints_output(self):
        original_load_credentials = token_security_module._load_credentials
        original_run_lookup = token_security_module.run_token_security_lookup
        original_render = token_security_module.render_text
        try:
            token_security_module._load_credentials = lambda: ("key", "secret")
            token_security_module.run_token_security_lookup = lambda token_address, chain_id, key, secret: {
                "token_address": token_address,
                "chain_id": chain_id,
                "security": {"is_malicious": False, "positive_flags": [], "positive_flag_details": [], "details": {}},
                "holders": [],
                "lp_holders": [],
                "dex": [],
            }
            token_security_module.render_text = lambda summary: f"rendered:{summary['token_address']}:{summary['chain_id']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_security_main("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "1")
        finally:
            token_security_module._load_credentials = original_load_credentials
            token_security_module.run_token_security_lookup = original_run_lookup
            token_security_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48:1")

    def test_render_token_security_text_uses_human_descriptions(self):
        summary = {
            "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "chain_id": "1",
            "security": {
                "is_malicious": True,
                "positive_flags": ["is_in_dex", "is_proxy"],
                "positive_flag_details": [
                    {"key": "is_in_dex", "label": "Token has active DEX trading pairs."},
                    {"key": "is_proxy", "label": "Contract is a proxy."},
                ],
                "details": {
                    "anti_whale_modifiable": None,
                    "is_in_dex": "1",
                    "is_proxy": "1",
                    "buy_tax": "0",
                    "sell_tax": "0.000000",
                    "token_name": "USD Coin",
                },
            },
            "holders": [],
            "lp_holders": [],
            "dex": [
                {"name": "UniswapV3", "pair": "0x111", "liquidity": "100.5"},
                {"name": "UniswapV3", "pair": "0x222", "liquidity": "200.25"},
                {"name": "SushiSwap", "pair": "0x333", "liquidity": "10"},
            ],
        }

        output = token_security_module.render_text(summary)

        self.assertIn("- Token has active DEX trading pairs.", output)
        self.assertIn("- Contract is a proxy.", output)
        self.assertIn("- Token has active DEX trading pairs: 1", output)
        self.assertIn("- Token name: USD Coin", output)
        self.assertIn("- name=UniswapV3 | liquidity=300.75000000", output)
        self.assertIn("- name=SushiSwap | liquidity=10.00000000", output)
        self.assertNotIn("- Buy tax: 0", output)
        self.assertNotIn("- Sell tax: 0.000000", output)
        self.assertNotIn("- Anti-whale settings can be modified: None", output)
        self.assertNotIn("- is_in_dex:", output)
        self.assertNotIn("- is_proxy:", output)
        self.assertNotIn("pair=0x111", output)
        self.assertNotIn("pair=0x222", output)

    def test_agent_main_reports_missing_runtime(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = agent_module.main("Do a sub task")
        self.assertEqual(exit_code, 1)
        self.assertIn("requires a KittyChain parent runtime", buffer.getvalue())

    def test_ask_user_main_reports_missing_runtime(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = ask_user_module.main("Need an answer?")
        self.assertEqual(exit_code, 1)
        self.assertIn("interactive KittyChain runtime", buffer.getvalue())

    def test_brief_main_prints_message(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = brief_module.main("Working on it")
        self.assertEqual(exit_code, 0)
        self.assertIn("Working on it", buffer.getvalue())

    def test_skill_main_loads_repository_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_root = Path(tmpdir) / "skills"
            skill_dir = skill_root / "using-superpowers"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("name: using-superpowers\ndescription: test skill\n")

            original_roots = skill_module.SKILL_ROOTS
            skill_module.SKILL_ROOTS = [skill_root]
            try:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    exit_code = skill_module.main("using-superpowers")
            finally:
                skill_module.SKILL_ROOTS = original_roots
        self.assertEqual(exit_code, 0)
        self.assertIn('Skill "using-superpowers" selected.', buffer.getvalue())

    def test_read_main_prints_file_contents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("alpha\nbeta\n")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = read_module.main(str(path))
        self.assertEqual(exit_code, 0)
        self.assertIn("1\talpha", buffer.getvalue())
        self.assertIn("2\tbeta", buffer.getvalue())

    def test_write_main_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = write_module.main(str(path), "hello world")
            content = path.read_text()
        self.assertEqual(exit_code, 0)
        self.assertEqual(content, "hello world")
        self.assertIn("Wrote", buffer.getvalue())

    def test_edit_main_replaces_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("alpha old omega")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = edit_module.main(str(path), "old", "new")
            content = path.read_text()
        self.assertEqual(exit_code, 0)
        self.assertEqual(content, "alpha new omega")
        self.assertIn("Edited", buffer.getvalue())

    def test_bash_main_prints_command_output(self):
        class FakeCompleted:
            returncode = 0
            stdout = "ok\n"
            stderr = ""

        original_run = bash_module.subprocess.run
        try:
            bash_module.subprocess.run = lambda *args, **kwargs: FakeCompleted()
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = bash_module.main("pwd")
        finally:
            bash_module.subprocess.run = original_run
        self.assertEqual(exit_code, 0)
        self.assertIn("Exit code: 0", buffer.getvalue())
        self.assertIn("ok", buffer.getvalue())

    def test_grep_main_finds_matching_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("alpha\nbeta tool\n")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = grep_module.main("tool", tmpdir)
        self.assertEqual(exit_code, 0)
        self.assertIn("sample.txt:2: beta tool", buffer.getvalue())

    def test_glob_main_lists_matching_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("x")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = glob_module.main("*.txt", tmpdir)
        self.assertEqual(exit_code, 0)
        self.assertIn("sample.txt", buffer.getvalue())

    def test_todo_write_main_prints_todo_list(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = todo_write_module.main()
        self.assertEqual(exit_code, 0)
        self.assertIn("Updated todo list:", buffer.getvalue())

    def test_web_browser_main_prints_fetched_content(self):
        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""
                self.returncode = 0

        class FakeLLM:
            def complete(self, messages, **kwargs):
                self.messages = messages
                self.kwargs = kwargs
                return SimpleNamespace(content="Summarized browser content")

        class FakeAgent:
            def __init__(self):
                self.llm = FakeLLM()

        calls = []
        outputs = iter(
            [
                FakeCompleted(""),
                FakeCompleted(""),
                FakeCompleted("https://example.com"),
                FakeCompleted("Hello from browser"),
                FakeCompleted('[{"status": 200}]'),
                FakeCompleted(""),
            ]
        )

        original_run = web_browser_module.subprocess.run
        try:
            def fake_run(args, **kwargs):
                calls.append(args)
                return next(outputs)

            web_browser_module.subprocess.run = fake_run
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = web_browser_module.main("https://example.com", agent=FakeAgent())
        finally:
            web_browser_module.subprocess.run = original_run
        self.assertEqual(exit_code, 0)
        self.assertIn("Summarized browser content", buffer.getvalue())
        self.assertEqual(calls[0][-2:], ["open", "https://example.com"])

    def test_web_browser_execute_summarizes_page_text_with_agent_llm(self):
        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""
                self.returncode = 0

        class FakeLLM:
            def __init__(self):
                self.complete_calls = []

            def clone(self):
                return self

            def complete(self, messages, **kwargs):
                self.complete_calls.append((messages, kwargs))
                return SimpleNamespace(content="Entity summary")

        class FakeAgent:
            def __init__(self):
                self.llm = FakeLLM()

        outputs = iter(
            [
                FakeCompleted(""),
                FakeCompleted(""),
                FakeCompleted("https://example.com/risk"),
                FakeCompleted("Page body text"),
                FakeCompleted('[{"status": 200}]'),
                FakeCompleted(""),
            ]
        )

        original_run = web_browser_module.subprocess.run
        tool = web_browser_module.WebBrowserTool()
        tool.bind_agent(FakeAgent())
        try:
            web_browser_module.subprocess.run = lambda *args, **kwargs: next(outputs)
            result = tool.execute("https://example.com", "extract counterparties", 20)
        finally:
            web_browser_module.subprocess.run = original_run

        self.assertEqual(result, "Entity summary")
        llm = tool._parent_agent.llm
        self.assertEqual(len(llm.complete_calls), 1)
        messages, kwargs = llm.complete_calls[0]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("extract counterparties", messages[0]["content"])
        self.assertIn("Page body text", messages[0]["content"])
        self.assertIn("brief summary", kwargs["system"].lower())
        self.assertIn("next-step suggestion", kwargs["system"].lower())

    def test_web_browser_execute_filters_think_blocks_from_summary(self):
        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""
                self.returncode = 0

        class FakeLLM:
            def clone(self):
                return self

            def complete(self, messages, **kwargs):
                return SimpleNamespace(content="visible<think>hidden</think>done")

        class FakeAgent:
            def __init__(self):
                self.llm = FakeLLM()

        outputs = iter(
            [
                FakeCompleted(""),
                FakeCompleted(""),
                FakeCompleted("https://example.com/risk"),
                FakeCompleted("Page body text"),
                FakeCompleted('[{"status": 200}]'),
                FakeCompleted(""),
            ]
        )

        original_run = web_browser_module.subprocess.run
        tool = web_browser_module.WebBrowserTool()
        tool.bind_agent(FakeAgent())
        try:
            web_browser_module.subprocess.run = lambda *args, **kwargs: next(outputs)
            result = tool.execute("https://example.com", "summarize", 20)
        finally:
            web_browser_module.subprocess.run = original_run

        self.assertEqual(result, "visibledone")

    def test_web_browser_execute_returns_retry_message_on_timeout(self):
        class FakeAgent:
            llm = None

        original_run = web_browser_module.subprocess.run
        tool = web_browser_module.WebBrowserTool()
        tool.bind_agent(FakeAgent())
        try:
            def fake_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(cmd=args[0], timeout=20)

            web_browser_module.subprocess.run = fake_run
            result = tool.execute("https://example.com", "summarize", 20)
        finally:
            web_browser_module.subprocess.run = original_run

        self.assertEqual(result, "Timed out, please try again.")

    def test_write_report_rejects_missing_token_fields(self):
        tool = write_report_module.WriteReportTool()

        result = tool.execute(
            type="token",
            path="/tmp/token-report.html",
            content="Token analysis",
            sources=["https://example.com"],
        )

        self.assertIn("token_name is required for type=token", result)
        self.assertIn("token_contract_address is required for type=token", result)
        self.assertIn("top_holders is required for type=token", result)
        self.assertIn("top_lp_holders is required for type=token", result)

    def test_write_report_rejects_deep_mode_without_graph_requirements(self):
        tool = write_report_module.WriteReportTool()

        result = tool.execute(
            type="address",
            path="/tmp/address-report.html",
            origin_address="0xabc",
            mode="deep",
            relevant_addresses=[{"address": "0x1"}],
            graph_data={"node": [{"id": "n1", "label": "Node 1"}], "edge": [{"source": "n1", "target": "n2"}]},
            sources=["https://example.com"],
            content="Wallet report",
        )

        self.assertIn("graph_data must include at least 5 nodes", result)
        self.assertIn("graph_data must include at least 5 edges", result)
        self.assertIn("find more hop1/hop2 counterparties of 0xabc", result)

    def test_write_report_rejects_normal_mode_when_agent_is_deep(self):
        class FakeAgent:
            mode = "deep"
            deep_mode = True

        tool = write_report_module.WriteReportTool()
        tool.bind_agent(FakeAgent())

        result = tool.execute(
            type="address",
            path="/tmp/address-report.html",
            origin_address="0xabc",
            mode="normal",
            relevant_addresses=[
                {"address": "0x1", "relation": "hop1-counterparty"},
                {"address": "0x2", "relation": "hop2-counterparty"},
            ],
            graph_data={
                "node": [
                    {"address": f"0x{i:040x}", "chain_name": "Ethereum"}
                    for i in range(1, 6)
                ],
                "edge": [
                    {
                        "source_address": f"0x{i:040x}",
                        "target_address": f"0x{i+1:040x}",
                        "direction": "from",
                    }
                    for i in range(1, 6)
                ],
            },
            sources=["https://example.com"],
            content="Wallet report",
        )

        self.assertIn("mode must be deep when agent.mode=deep", result)

    def test_write_report_relevant_address_relation_description_and_validation_for_address_reports(self):
        description = write_report_module.WriteReportTool.parameters["properties"]["relevant_addresses"]["description"]

        self.assertIn("hop1-counterparty", description)
        self.assertIn("hop2-counterparty", description)
        self.assertIn("hop3-counterparty", description)

        errors = write_report_module.validate_payload(
            {
                "type": "address",
                "mode": "normal",
                "path": "/tmp/address-report.html",
                "origin_address": "0xabc",
                "relevant_addresses": [{"address": "0x1", "relation": "owner"}],
                "graph_data": {},
                "sources": ["https://example.com"],
                "content": "Wallet report",
                "top_holders": [],
                "top_lp_holders": [],
                "token_name": "",
                "token_contract_address": "",
            }
        )

        self.assertIn(
            "relevant_addresses[0].relation must be one of: hop1-counterparty, hop2-counterparty, hop3-counterparty",
            errors,
        )
        self.assertFalse(hasattr(write_report_module, "validate_graph_data_for_origin"))

    def test_write_report_deep_mode_can_use_user_permission_to_confirm_normal_fallback(self):
        prompts = []

        class FakeLLM:
            def complete(self, messages, **kwargs):
                return SimpleNamespace(
                    content=(
                        "<h1>Summary</h1><p>Wallet summary</p>"
                        "<h2>Risk Overview</h2><p>Low</p>"
                        "<h2>Asset Overview</h2><p>Healthy</p>"
                        "<h2>Transaction Overview</h2><p>Active</p>"
                        "<h2>Association Graph</h2><div class='graph'>GRAPH</div>"
                        "<h2>Sources</h2><ul><li>src</li></ul>"
                    )
                )

        class FakeAgent:
            mode = "deep"
            deep_mode = True

            def __init__(self):
                self.llm = FakeLLM()
                self.permission_handler = self.answer

            def answer(self, payload):
                prompts.append(payload)
                return "accept"

        tool = write_report_module.WriteReportTool()
        tool.bind_agent(FakeAgent())

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "address-report.html"
            original_renderer = write_report_module.render_graph_html
            write_report_module.render_graph_html = lambda graph_data: '<div class="graph">GRAPH</div>'
            try:
                result = tool.execute(
                    type="address",
                    path=str(output_path),
                    origin_address="0xabc",
                    mode="normal",
                    relevant_addresses=[{"address": "0x1", "relation": "owner"}],
                    graph_data={
                        "node": [{"address": "0x1", "chain_name": "Ethereum"}],
                        "edge": [{"source_address": "0x1", "target_address": "0x2", "direction": "from"}],
                    },
                    sources=["https://example.com"],
                    content="Wallet report",
                )
            finally:
                write_report_module.render_graph_html = original_renderer

        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["title"], "Report Mode")
        self.assertEqual(
            prompts[0]["options"],
            [
                {"label": "Accept", "value": "accept"},
                {"label": "Deny", "value": "deny"},
            ],
        )
        self.assertIn("same payload", prompts[0]["description"].lower())
        self.assertIn("mode must be deep when agent.mode=deep", prompts[0]["description"])
        self.assertIn(
            "relevant_addresses[0].relation must be one of: hop1-counterparty, hop2-counterparty, hop3-counterparty",
            prompts[0]["description"],
        )
        self.assertIn("已经在", result)

    def test_write_report_returns_validation_errors_when_user_denies_fallback(self):
        prompts = []

        class FakeAgent:
            mode = "deep"
            deep_mode = True

            def __init__(self):
                self.permission_handler = self.answer

            def answer(self, payload):
                prompts.append(payload)
                return "deny"

        tool = write_report_module.WriteReportTool()
        tool.bind_agent(FakeAgent())

        result = tool.execute(
            type="address",
            path="/tmp/address-report.html",
            origin_address="0xabc",
            mode="normal",
            relevant_addresses=[{"address": "0x1", "relation": "owner"}],
            graph_data={
                "node": [{"address": "0x1", "chain_name": "Ethereum"}],
                "edge": [{"source_address": "0x1", "target_address": "0x2", "direction": "from"}],
            },
            sources=["https://example.com"],
            content="Wallet report",
        )

        self.assertEqual(len(prompts), 1)
        self.assertIn("Error:", result)
        self.assertIn("mode must be deep when agent.mode=deep", result)
        self.assertIn("Error:", result)
        self.assertIn("relevant_addresses[0].relation must be one of: hop1-counterparty, hop2-counterparty, hop3-counterparty", result)

    def test_write_report_build_prompts_include_graph_html_and_english_association_graph_section(self):
        payload = {
            "type": "address",
            "mode": "deep",
            "origin_address": "0xabc",
            "token_name": "",
            "token_contract_address": "",
            "top_holders": [],
            "top_lp_holders": [],
            "relevant_addresses": [{"address": "0x1", "relation": "hop1-counterparty"}],
            "sources": ["https://example.com"],
            "content": "Wallet report",
        }

        user_prompt = write_report_module.build_user_prompt(payload)
        system_prompt = write_report_module.build_system_prompt(payload)

        self.assertNotIn("graph_html", user_prompt)
        self.assertNotIn("Association Graph", system_prompt)
        self.assertNotIn("use the graph_html", system_prompt)
        self.assertNotIn("风险概况", system_prompt)
        self.assertNotIn("参考信息源", system_prompt)

    def test_write_report_requires_output_path(self):
        tool = write_report_module.WriteReportTool()

        result = tool.execute(
            type="address",
            origin_address="0xabc",
            sources=["https://example.com"],
            content="Wallet report",
        )

        self.assertEqual(result, "Error: path is required")

    def test_write_report_graph_description_mentions_expected_node_and_edge_fields(self):
        description = write_report_module.WriteReportTool.parameters["properties"]["graph_data"]["description"]

        self.assertIn("Required for `deep` mode", description)
        self.assertIn('"node"', description)
        self.assertIn('"edge"', description)
        self.assertIn("address", description)
        self.assertIn("chain_name", description)
        self.assertIn("source_address", description)
        self.assertIn("target_address", description)
        self.assertIn("direction", description)
        self.assertIn("at least 2", description)
        self.assertIn("address_identity", description)
        self.assertIn("address_labels", description)
        self.assertIn("address_balance", description)
        self.assertIn("address_malicious", description)

    def test_write_report_deep_mode_requires_relevant_address_identity_metadata(self):
        description = write_report_module.WriteReportTool.parameters["properties"]["relevant_addresses"]["description"]

        self.assertIn("at least 1", description)
        self.assertIn("balance", description)
        self.assertIn("labels", description)
        self.assertIn("identity", description)

        errors = write_report_module.validate_payload(
            {
                "type": "address",
                "mode": "deep",
                "path": "/tmp/address-report.html",
                "origin_address": "0xabc",
                "relevant_addresses": [
                    {"address": "0x1", "relation": "hop1-counterparty"},
                ],
                "graph_data": {
                    "node": [
                        {
                            "address": f"0x{i:040x}",
                            "chain_name": "Ethereum",
                            "address_identity": {"entity": f"Node {i}"},
                            "address_labels": [f"label-{i}"],
                        }
                        for i in range(1, 6)
                    ],
                    "edge": [
                        {
                            "source_address": f"0x{i:040x}",
                            "target_address": f"0x{i + 1:040x}",
                            "direction": "from",
                        }
                        for i in range(1, 6)
                    ],
                },
                "sources": ["https://example.com"],
                "content": "Wallet report",
                "top_holders": [],
                "top_lp_holders": [],
                "token_name": "",
                "token_contract_address": "",
            }
        )

        self.assertIn(
            "relevant_addresses[0] must include at least one of: balance, labels, identity",
            errors,
        )

    def test_write_report_deep_mode_requires_graph_node_metadata(self):
        errors = write_report_module.validate_payload(
            {
                "type": "address",
                "mode": "deep",
                "path": "/tmp/address-report.html",
                "origin_address": "0xabc",
                "relevant_addresses": [
                    {
                        "address": "0x1",
                        "balance": "10",
                        "relation": "hop1-counterparty",
                    }
                ],
                "graph_data": {
                    "node": [
                        {
                            "address": f"0x{i:040x}",
                            "chain_name": "Ethereum",
                            "address_identity": {"entity": f"Node {i}"} if i == 1 else {"entity": f"Node {i}"},
                            "address_labels": [] if i == 1 else [f"label-{i}"],
                            "address_balance": {} if i == 1 else {"usd_value": i * 100},
                            "address_malicious": {} if i == 1 else {"risk_level": "low"},
                        }
                        for i in range(1, 6)
                    ],
                    "edge": [
                        {
                            "source_address": f"0x{i:040x}",
                            "target_address": f"0x{i + 1:040x}",
                            "direction": "from",
                        }
                        for i in range(1, 6)
                    ],
                },
                "sources": ["https://example.com"],
                "content": "Wallet report",
                "top_holders": [],
                "top_lp_holders": [],
                "token_name": "",
                "token_contract_address": "",
            }
        )

        self.assertIn(
            "graph_data.node[0] must include at least two of: address_identity, address_labels, address_balance, address_malicious",
            errors,
        )

    def test_write_report_render_graph_html_uses_demo_style_node_and_edge_fields(self):
        recorded = {"nodes": [], "edges": [], "options": []}

        class FakeNetwork:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def set_options(self, options):
                recorded["options"].append(options)

            def add_node(self, node_id, **kwargs):
                recorded["nodes"].append((node_id, kwargs))

            def add_edge(self, source, target, **kwargs):
                recorded["edges"].append((source, target, kwargs))

            def generate_html(self, notebook=False):
                return (
                    "<html><body><div>graph</div><script>"
                    "nodes = new vis.DataSet([]);"
                    "edges = new vis.DataSet([]);"
                    "network = new vis.Network(container, data, options);"
                    "</script></body></html>"
                )

        fake_network_module = SimpleNamespace(Network=FakeNetwork)
        fake_pyvis_module = SimpleNamespace(network=fake_network_module)

        with patch.dict(
            sys.modules,
            {
                "pyvis": fake_pyvis_module,
                "pyvis.network": fake_network_module,
            },
        ):
            html = write_report_module.render_graph_html(
                {
                    "node": [
                        {
                            "address": "0x1111111111111111111111111111111111111111",
                            "chain_name": "Ethereum",
                            "address_identity": {"entity": "Origin wallet"},
                            "address_labels": ["market maker"],
                            "address_balance": {"usd_value": 1200000},
                            "address_malicious": {"risk_level": "low"},
                        }
                    ],
                    "edge": [
                        {
                            "source_address": "0x1111111111111111111111111111111111111111",
                            "target_address": "0x2222222222222222222222222222222222222222",
                            "direction": "from",
                            "usd_value": 420000,
                            "start_time": "2026-04-11T00:00:00Z",
                            "end_time": "2026-04-12T00:00:00Z",
                        }
                    ]
                    + [
                        {
                            "source_address": "0x3333333333333333333333333333333333333333",
                            "target_address": "0x4444444444444444444444444444444444444444",
                            "direction": "to",
                            "usd_value": 1200,
                        }
                    ],
                }
            )

        self.assertIn('class="relationship-graph"', html)
        self.assertIn("function htmlTitle(html)", html)
        self.assertEqual(len(recorded["options"]), 1)
        self.assertIn('"navigationButtons": true', recorded["options"][0])
        self.assertEqual(recorded["nodes"][0][0], "0x1111111111111111111111111111111111111111")
        self.assertIn("0x1111", recorded["nodes"][0][1]["label"])
        self.assertIn("Origin wallet", recorded["nodes"][0][1]["title"])
        self.assertEqual(recorded["nodes"][0][1]["group"], "Ethereum")
        self.assertEqual(recorded["edges"][0][0], "0x1111111111111111111111111111111111111111")
        self.assertEqual(recorded["edges"][0][1], "0x2222222222222222222222222222222222222222")
        self.assertEqual(recorded["edges"][0][2]["arrows"], "to")
        self.assertEqual(recorded["edges"][1][2]["arrows"], "to")
        self.assertIn("Counterparty relation", recorded["edges"][0][2]["title"])
        self.assertGreaterEqual(recorded["edges"][0][2]["width"], 2)

    def test_wrap_html_document_includes_vis_network_assets_when_graph_section_exists(self):
        document = write_report_module.wrap_html_document(
            "# Demo Report",
            '<section class="relationship-graph"><div id="mynetwork"></div><script>new vis.Network()</script></section>',
            "Demo Report",
        )

        self.assertIn("vis-network.min.css", document)
        self.assertIn("vis-network.min.js", document)
        self.assertIn("#mynetwork", document)
        self.assertIn("height: 860px", document)
        self.assertIn("Appendix: Association Graph", document)
        self.assertIn("<h1>Demo Report</h1>", document)

    def test_wrap_html_document_renders_markdown_without_graph_appendix_when_graph_is_empty(self):
        document = write_report_module.wrap_html_document(
            "# Summary\n\n- Item 1\n- Item 2",
            "",
            "Demo Report",
        )

        self.assertIn("<h1>Summary</h1>", document)
        self.assertIn("<li>Item 1</li>", document)
        self.assertNotIn("Appendix: Association Graph", document)
        self.assertNotIn("vis-network.min.js", document)

    def test_wrap_html_document_renders_markdown_bold_text(self):
        document = write_report_module.wrap_html_document(
            "# Summary\n\n**High Risk** wallet activity",
            "",
            "Demo Report",
        )

        self.assertIn("<strong>High Risk</strong> wallet activity", document)

    def test_write_report_generates_address_report_and_embeds_graph(self):
        class FakeLLM:
            def __init__(self):
                self.calls = []

            def clone(self):
                return self

            def complete(self, messages, **kwargs):
                self.calls.append((messages, kwargs))
                return SimpleNamespace(
                    content=(
                        "# Summary\n\nWallet summary\n\n"
                        "## Risk Overview\n\nLow\n\n"
                        "## Asset Overview\n\nHealthy\n\n"
                        "## Transaction Overview\n\nActive\n\n"
                        "## Relevant Addresses\n\n"
                        "| Address |\n| --- |\n| 0x1 |\n\n"
                        "## Sources\n\n- src"
                    )
                )

        class FakeAgent:
            def __init__(self):
                self.llm = FakeLLM()

        tool = write_report_module.WriteReportTool()
        tool.bind_agent(FakeAgent())

        with tempfile.TemporaryDirectory() as tmpdir:
            original_renderer = write_report_module.render_graph_html
            output_path = Path(tmpdir) / "address-report.html"
            write_report_module.render_graph_html = lambda graph_data: '<div class="graph">GRAPH</div>'
            try:
                result = tool.execute(
                    type="address",
                    path=str(output_path),
                    origin_address="0xabc",
                    mode="deep",
                    relevant_addresses=[
                        {
                            "address": "0x1",
                            "balance": "10",
                            "labels": "label",
                            "identity": "entity",
                            "relation": "hop1-counterparty",
                            "notes": "note",
                        }
                    ],
                    graph_data={
                        "node": [
                            {
                                "address": f"0x{i:040x}",
                                "chain_name": "Ethereum",
                                "address_identity": {"entity": f"Node {i}"},
                                "address_labels": [f"label-{i}"],
                            }
                            for i in range(1, 6)
                        ],
                        "edge": [
                            {
                                "source_address": "0x0000000000000000000000000000000000000001",
                                "target_address": f"0x{i:040x}",
                                "direction": "from",
                            }
                            for i in range(2, 7)
                        ],
                    },
                    sources=["https://example.com/a", "https://example.com/b"],
                    content="Main wallet content",
                )
            finally:
                write_report_module.render_graph_html = original_renderer

            self.assertIn("已经在", result)
            self.assertIn(str(output_path), result)
            report_html = output_path.read_text()
            self.assertIn("GRAPH", report_html)
            self.assertIn("Wallet summary", report_html)
            self.assertIn("Appendix: Association Graph", report_html)
            self.assertNotIn("<h2>Association Graph</h2><div class='graph'>GRAPH</div>", report_html)

        llm = tool._parent_agent.llm
        self.assertEqual(len(llm.calls), 1)
        messages, kwargs = llm.calls[0]
        self.assertIn("origin_address", messages[0]["content"])
        self.assertNotIn("graph_html", messages[0]["content"])
        self.assertIn("Relevant Addresses", kwargs["system"])
        self.assertNotIn("Association Graph", kwargs["system"])
        self.assertIn("must call write_report", kwargs["system"])
        self.assertIn("If the report mode is `deep`, make it thorough", kwargs["system"])

    def test_write_report_generates_token_report_without_graph_when_not_needed(self):
        class FakeLLM:
            def clone(self):
                return self

            def complete(self, messages, **kwargs):
                self.messages = messages
                self.kwargs = kwargs
                return SimpleNamespace(
                    content=(
                        "# Summary\n\nToken summary\n\n"
                        "## 风险概况\n\nMedium\n\n"
                        "## Top Holders概况\n\nHolder notes\n\n"
                        "## Top LP Holders概况\n\nLP notes\n\n"
                        "## 参考信息源\n\n- src"
                    )
                )

        class FakeAgent:
            def __init__(self):
                self.llm = FakeLLM()

        tool = write_report_module.WriteReportTool()
        tool.bind_agent(FakeAgent())

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "token-report.html"
            try:
                result = tool.execute(
                    type="token",
                    path=str(output_path),
                    token_name="KITTY",
                    token_contract_address="0xtoken",
                    top_holders=[
                        {
                            "address": "0xholder",
                            "balance": "100",
                            "labels": "holder",
                            "identity": "entity",
                            "notes": "top holder",
                        }
                    ],
                    top_lp_holders=[
                        {
                            "address": "0xlp",
                            "balance": "50",
                            "labels": "lp",
                            "identity": "entity",
                            "notes": "top lp",
                        }
                    ],
                    sources=["https://example.com/token"],
                    content="Token report body",
                )
            finally:
                pass

            self.assertIn("已经在", result)
            self.assertIn(str(output_path), result)
            report_html = output_path.read_text()
            self.assertIn("Token summary", report_html)
            self.assertNotIn('class="graph"', report_html)

        llm = tool._parent_agent.llm
        self.assertIn("top_holders", llm.messages[0]["content"])
        self.assertIn("Top LP Holders", llm.kwargs["system"])

    def test_web_search_main_prints_results(self):
        class FakeResponse:
            status_code = 200
            text = """
            <div class="result">
              <a class="result__a" href="https://example.com/page">Example</a>
              <a class="result__snippet">Example snippet</a>
            </div>
            """

            def raise_for_status(self):
                return None

        original_get = web_search_module.requests.get
        try:
            web_search_module.requests.get = lambda *args, **kwargs: FakeResponse()
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = web_search_module.main("example query")
        finally:
            web_search_module.requests.get = original_get
        self.assertEqual(exit_code, 0)
        self.assertIn('Web search results for "example query":', buffer.getvalue())
        self.assertIn("https://example.com/page", buffer.getvalue())

    def test_new_tool_scripts_support_standalone_execution(self):
        script_paths = [
            "kittychain/tools/agent.py",
            "kittychain/tools/address_pattern.py",
            "kittychain/tools/ask_user.py",
            "kittychain/tools/brief.py",
            "kittychain/tools/skill.py",
            "kittychain/tools/read.py",
            "kittychain/tools/write.py",
            "kittychain/tools/edit.py",
            "kittychain/tools/bash.py",
            "kittychain/tools/grep.py",
            "kittychain/tools/glob.py",
            "kittychain/tools/todo_write.py",
        ]

        for relative_path in script_paths:
            with self.subTest(script=relative_path):
                completed = subprocess.run(
                    [sys.executable, relative_path],
                    cwd=Path(__file__).resolve().parent.parent,
                    capture_output=True,
                    text=True,
                )
                self.assertNotIn("ImportError", completed.stderr)
                self.assertNotIn("attempted relative import", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_glob_and_grep_scripts_work_from_tools_directory(self):
        tool_dir = Path(__file__).resolve().parent.parent / "kittychain" / "tools"

        for script_name in ("glob.py", "grep.py"):
            with self.subTest(script=script_name):
                completed = subprocess.run(
                    [sys.executable, script_name],
                    cwd=tool_dir,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
                self.assertNotIn("Error: tools not found", completed.stdout)

    def test_run_token_security_lookup_uses_goplus_token_client_response(self):
        class FakeAccessTokenResult:
            access_token = "Bearer test-token"

        class FakeAuthResponse:
            result = FakeAccessTokenResult()

        auth_calls = []
        token_calls = []

        class FakeAuth:
            def __init__(self, key, secret):
                auth_calls.append((key, secret))

            def get_access_token(self):
                return FakeAuthResponse()

        class FakeTokenClient:
            def __init__(self, access_token=None):
                token_calls.append(("init", access_token))

            def token_security(self, chain_id, addresses):
                token_calls.append(("token_security", chain_id, addresses))
                return type(
                    "Response",
                    (),
                    {
                        "result": {
                            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
                                "is_blacklisted": "1",
                                "holders": [{"address": "0x111"}],
                                "lp_holders": [{"address": "0x222"}],
                                "dex": [{"name": "Uniswap"}],
                            }
                        },
                        "__dict__": {
                            "result": {
                                "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
                                    "is_blacklisted": "1",
                                    "holders": [{"address": "0x111"}],
                                    "lp_holders": [{"address": "0x222"}],
                                    "dex": [{"name": "Uniswap"}],
                                }
                            }
                        },
                    },
                )()

        original_auth = token_security_module.Auth
        original_token = token_security_module.Token
        try:
            token_security_module.Auth = FakeAuth
            token_security_module.Token = FakeTokenClient
            summary = token_security_module.run_token_security_lookup(
                "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "1",
                "key",
                "secret",
            )
        finally:
            token_security_module.Auth = original_auth
            token_security_module.Token = original_token

        self.assertEqual(auth_calls, [("key", "secret")])
        self.assertEqual(token_calls[0], ("init", "Bearer test-token"))
        self.assertEqual(
            token_calls[1],
            ("token_security", "1", ["0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"]),
        )
        self.assertTrue(summary["security"]["is_malicious"])
        self.assertEqual(summary["holders"][0]["address"], "0x111")

    def test_render_text_mentions_identity_and_exchange(self):
        summary = {
            "address": "0xabc",
            "identity": {"found": True, "rows": [{"name": "alice.eth", "blockchain": "ethereum", "source": "ens"}]},
            "exchange": {
                "is_exchange": True,
                "address_rows": [{"cex_name": "binance", "blockchain": "ethereum"}],
                "is_deposit_address": False,
                "deposit_rows": [],
            },
        }
        output = render_text(summary)
        self.assertIn("alice.eth", output)
        self.assertIn("binance", output)

    def test_render_text_supports_multiple_summaries(self):
        output = render_text(
            [
                {
                    "address": "0xaaa",
                    "identity": {"found": True, "rows": [{"name": "alice.eth", "blockchain": "ethereum"}]},
                    "exchange": {"is_exchange": False, "address_rows": [], "is_deposit_address": False, "deposit_rows": []},
                },
                {
                    "address": "0xbbb",
                    "identity": {"found": False, "rows": []},
                    "exchange": {
                        "is_exchange": True,
                        "address_rows": [{"cex_name": "binance", "blockchain": "ethereum"}],
                        "is_deposit_address": False,
                        "deposit_rows": [],
                    },
                },
            ]
        )
        self.assertIn("Address: 0xaaa", output)
        self.assertIn("Address: 0xbbb", output)
        self.assertIn("alice.eth", output)
        self.assertIn("binance", output)

    def test_run_sql_with_backoff_retries_retry_error(self):
        calls = []

        class FakeClient:
            def run_sql(self, **kwargs):
                calls.append(kwargs)
                if len(calls) < 3:
                    raise RetryError("too many 429 error responses")
                return {"ok": True}

        sleeps = []
        result = _run_sql_with_backoff(FakeClient(), "select 1", ping_frequency=5, max_attempts=3, sleep_func=sleeps.append)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [2, 4])

    def test_summarize_security_result_extracts_flags(self):
        raw = {
            "_result": {
                "_data_source": "SlowMist",
                "_discriminator": None,
                "_malicious_address": "1",
                "_blackmail_activities": "0",
                "_phishing_activities": "1",
                "_stealing_attack": "1",
            }
        }
        summary = summarize_security_result("0xabc", raw)
        self.assertEqual(summary["address"], "0xabc")
        self.assertTrue(summary["is_malicious"])
        self.assertIn("malicious_address", summary["positive_flags"])
        self.assertIn("phishing_activities", summary["positive_flags"])
        self.assertEqual(summary["details"]["data_source"], "SlowMist")
        self.assertNotIn("discriminator", summary["details"])

    def test_render_security_text_is_human_readable(self):
        summary = {
            "address": "0xabc",
            "is_malicious": True,
            "positive_flags": ["malicious_address", "phishing_activities"],
            "positive_flag_details": [
                {"key": "malicious_address", "label": "The address is flagged as malicious overall."},
                {"key": "phishing_activities", "label": "The address is associated with phishing activity."},
            ],
            "details": {"malicious_address": "1", "phishing_activities": "1", "data_source": "SlowMist"},
        }
        output = render_security_text(summary)
        self.assertIn("0xabc", output)
        self.assertIn("malicious overall", output)
        self.assertIn("SlowMist", output)
        self.assertIn("The address is associated with phishing activity. Value: 1", output)
        self.assertNotIn("- phishing_activities: 1", output)

    def test_summarize_tokens_defaults_decimals_and_adds_network_totals(self):
        payload = {
            "data": {
                "tokens": [
                    {
                        "network": "eth-mainnet",
                        "tokenBalance": hex(2_500_000),
                        "tokenMetadata": {"symbol": "USDC", "decimals": 6},
                        "tokenPrices": [{"currency": "usd", "value": "1.0"}],
                    },
                    {
                        "network": "base-mainnet",
                        "tokenBalance": hex(3_000_000),
                        "tokenMetadata": {"symbol": "USDC", "decimals": 6},
                        "tokenPrices": [{"currency": "usd", "value": "1.0"}],
                    },
                    {
                        "network": "eth-mainnet",
                        "tokenBalance": hex(2_000000000000000000),
                        "tokenMetadata": {"symbol": "ETH", "decimals": 18},
                        "tokenPrices": [{"currency": "usd", "value": "2000"}],
                    },
                    {
                        "network": "eth-mainnet",
                        "tokenBalance": "0x10",
                        "tokenMetadata": {"symbol": None, "decimals": None},
                        "tokenPrices": [{"currency": "usd", "value": "99"}],
                    },
                ]
            }
        }
        summary = summarize_tokens(payload)
        self.assertEqual(len(summary["tokens"]), 3)
        self.assertEqual(summary["tokens"][0]["symbol"], "ETH")
        self.assertAlmostEqual(summary["tokens"][0]["quantity"], 2.0)
        self.assertAlmostEqual(summary["tokens"][0]["value_usd"], 4000.0)
        self.assertEqual(summary["tokens"][1]["symbol"], "USDC")
        self.assertAlmostEqual(summary["tokens"][1]["quantity"], 5.5)
        self.assertAlmostEqual(summary["tokens"][1]["value_usd"], 5.5)
        self.assertEqual(summary["tokens"][2]["symbol"], "UNKNOWN@eth-mainnet")
        self.assertGreater(summary["tokens"][2]["quantity"], 0)
        self.assertGreater(summary["tokens"][2]["value_usd"], 0)
        self.assertIn("network_totals", summary)
        self.assertAlmostEqual(summary["network_totals"]["eth-mainnet"], 4002.5, places=8)
        self.assertAlmostEqual(summary["network_totals"]["base-mainnet"], 3.0)
        self.assertAlmostEqual(summary["total_value_usd"], 4005.5, places=8)

    def test_render_balance_text_is_human_readable(self):
        summary = {
            "tokens": [
                {"symbol": "ETH", "quantity": 2.0, "value_usd": 4000.0},
                {"symbol": "USDC", "quantity": 5.5, "value_usd": 5.5},
            ],
            "network_totals": {"eth-mainnet": 4000.0, "base-mainnet": 5.5},
            "total_value_usd": 4005.5,
        }
        output = render_balance_text(summary)
        self.assertIn("ETH", output)
        self.assertIn("USDC", output)
        self.assertIn("4005.50000000", output)
        self.assertIn("value_usd=4000.00000000", output)
        self.assertIn("eth-mainnet", output)
        self.assertIn("base-mainnet", output)

    def test_summarize_transfers_groups_by_direction_counterparty_asset(self):
        responses = [
            {
                "network": "bnb-mainnet",
                "direction": "from",
                "payload": {
                    "result": {
                        "transfers": [
                            {
                                "from": "0xme",
                                "to": "0xcp1",
                                "asset": "SFUND",
                                "value": 10,
                                "metadata": {"blockTimestamp": "2025-09-23T12:06:31.000Z"},
                            },
                            {
                                "from": "0xme",
                                "to": "0xcp1",
                                "asset": "SFUND",
                                "value": 5,
                                "metadata": {"blockTimestamp": "2025-09-24T12:06:31.000Z"},
                            },
                        ]
                    }
                },
            },
            {
                "network": "bnb-mainnet",
                "direction": "to",
                "payload": {
                    "result": {
                        "transfers": [
                            {
                                "from": "0xcp2",
                                "to": "0xme",
                                "asset": "BNB",
                                "value": 2,
                                "metadata": {"blockTimestamp": "2025-09-20T12:06:31.000Z"},
                            }
                        ]
                    }
                },
            },
        ]
        summary = summarize_transfers("0xme", responses)
        self.assertEqual(len(summary["items"]), 2)
        first = summary["items"][0]
        self.assertEqual(first["direction"], "from")
        self.assertEqual(first["counterparty"], "0xcp1")
        self.assertEqual(first["asset"], "SFUND")
        self.assertEqual(first["total_value"], 15.0)
        self.assertEqual(first["first_timestamp"], "2025-09-23T12:06:31.000Z")
        self.assertEqual(first["last_timestamp"], "2025-09-24T12:06:31.000Z")

    def test_render_transfers_text_is_human_readable(self):
        summary = {
            "address": "0xme",
            "skipped_networks": [],
            "items": [
                {
                    "network": "bnb-mainnet",
                    "direction": "from",
                    "counterparty": "0xcp1",
                    "asset": "SFUND",
                    "total_value": 15.0,
                    "first_timestamp": "2025-09-23T12:06:31.000Z",
                    "last_timestamp": "2025-09-24T12:06:31.000Z",
                }
            ],
        }
        output = render_transfers_text(summary)
        self.assertIn("0xcp1", output)
        self.assertIn("SFUND", output)
        self.assertIn("15.00000000", output)
        self.assertIn("2025-09-23T12:06:31.000Z", output)

    def test_fetch_all_transfers_skips_unsupported_networks(self):
        calls = []

        def fake_get_asset_transfers(api_key, network, from_address=None, to_address=None, **kwargs):
            calls.append((network, from_address, to_address))
            if network == "solana-mainnet":
                raise Exception("unsupported network")
            return {"result": {"transfers": []}}

        original = fetch_all_transfers.__globals__["get_asset_transfers"]
        fetch_all_transfers.__globals__["get_asset_transfers"] = fake_get_asset_transfers
        try:
            responses, skipped = fetch_all_transfers("0xme", "key", ["eth-mainnet", "solana-mainnet"])
        finally:
            fetch_all_transfers.__globals__["get_asset_transfers"] = original

        self.assertEqual(len(responses), 2)
        self.assertEqual(skipped[0]["network"], "solana-mainnet")

if __name__ == "__main__":
    unittest.main()
