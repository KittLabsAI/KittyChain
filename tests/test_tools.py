import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from requests import HTTPError
from requests.exceptions import RetryError

import src.config as src_config
import src.tools.agent as agent_module
import src.tools.address_identity as address_identity_module
import src.tools.address_labels as address_labels_module
import src.tools.ask_user as ask_user_module
import src.tools.bash as bash_module
import src.tools.brief as brief_module
import src.tools.edit as edit_module
import src.tools.glob as glob_module
import src.tools.grep as grep_module
import src.tools.read as read_module
import src.tools.skill as skill_module
import src.tools.token_info as token_info_module
import src.tools.token_security as token_security_module
import src.tools.todo_write as todo_write_module
import src.tools.web_fetch as web_fetch_module
import src.tools.web_search as web_search_module
import src.tools.write as write_module
from src.tools.address_balance import render_balance_text, summarize_tokens
from src.tools.address_identity import (
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
from src.tools.address_labels import (
    AddressLabelsTool,
    fetch_address_labels,
    main as address_labels_main,
    summarize_label_results,
)
from src.tools.address_mallicious import render_security_text, summarize_security_result
from src.tools.address_transfers import fetch_all_transfers, render_transfers_text, summarize_transfers
from src.tools.token_info import TokenInfoTool, fetch_token_info, main as token_info_main
from src.tools.token_security import TokenSecurityTool, main as token_security_main, summarize_token_security_result


class ToolsTests(unittest.TestCase):
    def test_config_module_exposes_chainbase_api_key(self):
        self.assertTrue(hasattr(src_config, "CHAINBASE_API_KEY"))

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
            session=FakeSession(),
        )

        self.assertEqual(len(calls), len(address_labels_module.SUPPORTED_CHAIN_IDS) * 2)
        self.assertEqual(
            sorted({call["params"]["chain_id"] for call in calls}),
            sorted(address_labels_module.SUPPORTED_CHAIN_IDS),
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
            session=FakeSession(),
            time_func=fake_time,
            sleep_func=fake_sleep,
        )

        self.assertEqual(len(calls), len(address_labels_module.SUPPORTED_CHAIN_IDS))
        self.assertEqual(len(sleeps), len(address_labels_module.SUPPORTED_CHAIN_IDS) - 1)
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
                tool.execute("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        finally:
            address_labels_module._load_api_key = original

    def test_address_labels_main_returns_success_and_prints_output(self):
        original_load_api_key = address_labels_module._load_api_key
        original_fetch = address_labels_module.fetch_address_labels
        original_render = address_labels_module.render_text
        try:
            address_labels_module._load_api_key = lambda: "test-key"
            address_labels_module.fetch_address_labels = lambda address, api_key: {
                "address": address,
                "labels": [{"category": "cex", "tags": ["Binance Hot Wallet"]}],
            }
            address_labels_module.render_text = lambda summary: f"rendered:{summary['address']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = address_labels_main("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        finally:
            address_labels_module._load_api_key = original_load_api_key
            address_labels_module.fetch_address_labels = original_fetch
            address_labels_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    def test_fetch_token_info_combines_price_history_and_top_holders(self):
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
                if url.endswith("/token/price"):
                    return FakeResponse(
                        {"code": 0, "message": "ok", "data": {"price": "1.23", "symbol": "USDC", "contract_address": params["contract_address"]}}
                    )
                if url.endswith("/token/price/history"):
                    return FakeResponse(
                        {
                            "code": 0,
                            "message": "ok",
                            "data": [
                                {"price": "1.20", "updated_at": "2024-01-01T00:00:00Z"},
                                {"price": "1.21", "updated_at": "2024-01-02T00:00:00Z"},
                            ],
                        }
                    )
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

        summary = fetch_token_info(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            1,
            1704067200,
            1704153600,
            "test-key",
            session=FakeSession(),
            time_func=fake_time,
            sleep_func=fake_sleep,
        )

        self.assertEqual(len(calls), 3)
        self.assertEqual(summary["current_price_usd"], 1.23)
        self.assertEqual(len(summary["price_history"]), 2)
        self.assertEqual(summary["price_history"][0]["price_usd"], 1.2)
        self.assertEqual(
            summary["top_holders"][0],
            {
                "wallet_address": "0x1111111111111111111111111111111111111111",
                "amount": 1000.0,
                "usd_value": 1230.0,
            },
        )
        self.assertEqual(len(sleeps), 2)

    def test_token_info_tool_description_mentions_chain_ids_and_timestamps(self):
        description = TokenInfoTool.parameters["properties"]["chain_id"]["description"]
        self.assertIn("Ethereum=1", description)
        self.assertIn("Merlin=4200", description)

        start_description = TokenInfoTool.parameters["properties"]["start_time"]["description"]
        end_description = TokenInfoTool.parameters["properties"]["end_time"]["description"]
        self.assertIn("Unix timestamp integer", start_description)
        self.assertIn("from_timestamp", start_description)
        self.assertIn("end_timestamp", end_description)
        self.assertIn("90 days", end_description)

    def test_token_info_main_returns_success_and_prints_output(self):
        original_load_api_key = token_info_module._load_api_key
        original_fetch = token_info_module.fetch_token_info
        original_render = token_info_module.render_text
        try:
            token_info_module._load_api_key = lambda: "test-key"
            token_info_module.fetch_token_info = lambda token_address, chain_id, start_time, end_time, api_key: {
                "token_address": token_address,
                "chain_id": chain_id,
                "current_price_usd": 1.23,
                "price_history": [],
                "top_holders": [],
            }
            token_info_module.render_text = lambda summary: f"rendered:{summary['token_address']}:{summary['chain_id']}"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = token_info_main(
                    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                    1,
                    1704067200,
                    1704153600,
                )
        finally:
            token_info_module._load_api_key = original_load_api_key
            token_info_module.fetch_token_info = original_fetch
            token_info_module.render_text = original_render

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip(), "rendered:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48:1")

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
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = skill_module.main("using-superpowers")
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

    def test_web_fetch_main_prints_fetched_content(self):
        class FakeResponse:
            status_code = 200
            url = "https://example.com"
            text = "<html><body><h1>Hello</h1></body></html>"
            headers = {"Content-Type": "text/html"}

            def raise_for_status(self):
                return None

        original_get = web_fetch_module.requests.get
        try:
            web_fetch_module.requests.get = lambda *args, **kwargs: FakeResponse()
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = web_fetch_module.main("https://example.com")
        finally:
            web_fetch_module.requests.get = original_get
        self.assertEqual(exit_code, 0)
        self.assertIn("Fetched: https://example.com", buffer.getvalue())
        self.assertIn("Hello", buffer.getvalue())

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
            "src/tools/agent.py",
            "src/tools/ask_user.py",
            "src/tools/brief.py",
            "src/tools/skill.py",
            "src/tools/read.py",
            "src/tools/write.py",
            "src/tools/edit.py",
            "src/tools/bash.py",
            "src/tools/grep.py",
            "src/tools/glob.py",
            "src/tools/todo_write.py",
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
        tool_dir = Path(__file__).resolve().parent.parent / "src" / "tools"

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
