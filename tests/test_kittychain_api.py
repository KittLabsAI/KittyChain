"""Tests for the shared KittyChain API helper."""

import json
import unittest
from unittest.mock import MagicMock, patch

from kittychain.tools._kittychain_api import (
    KITTYCHAIN_API_BASE,
    KittyChainAPIError,
    post_kittychain,
)


class TestPostKittychain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_returns_data_on_success(self, mock_send, mock_load_key):
        mock_load_key.return_value = "kk_test_key"
        mock_send.return_value = {"ok": True, "data": {"foo": "bar"}}
        result = post_kittychain("/api/test", {"key": "value"})
        self.assertEqual(result, {"foo": "bar"})

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_raises_on_api_error(self, mock_send, mock_load_key):
        mock_load_key.return_value = "kk_test_key"
        mock_send.return_value = {"ok": False, "error": "bad request"}
        with self.assertRaises(KittyChainAPIError):
            post_kittychain("/api/test", {})

    @patch("kittychain.tools._kittychain_api._load_api_key")
    def test_raises_when_api_key_missing(self, mock_load_key):
        mock_load_key.return_value = ""
        with self.assertRaises(KittyChainAPIError):
            post_kittychain("/api/test", {})

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_sends_correct_url_and_headers(self, mock_send, mock_load_key):
        mock_load_key.return_value = "kk_test_key"
        mock_send.return_value = {"ok": True, "data": {}}
        post_kittychain("/api/address/balance", {"address": "0x123"})
        call_args = mock_send.call_args
        url = call_args[0][0]
        headers = call_args[0][2]
        self.assertEqual(url, f"{KITTYCHAIN_API_BASE}/api/address/balance")
        self.assertEqual(headers["Authorization"], "Bearer kk_test_key")
        self.assertEqual(headers["Content-Type"], "application/json")

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_passes_payload_as_json_body(self, mock_send, mock_load_key):
        mock_load_key.return_value = "kk_test_key"
        mock_send.return_value = {"ok": True, "data": {}}
        payload = {"address": "0xabc", "chains": ["Ethereum"]}
        post_kittychain("/api/address/balance", payload)
        call_args = mock_send.call_args
        sent_payload = call_args[0][1]
        self.assertEqual(sent_payload, payload)


class TestAddressBalanceKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_summarize_tokens_from_kittychain_response(self, mock_send, mock_load_key):
        from kittychain.tools.address_balance import summarize_tokens_kittychain

        api_response = {
            "tokens": [
                {"network": "eth-mainnet", "symbol": "ETH", "tokenAddress": None, "quantity": "2", "valueUsd": "4000"},
                {"network": "eth-mainnet", "symbol": "USDC", "tokenAddress": "0xa0b8", "quantity": "5.5", "valueUsd": "5.5"},
                {"network": "base-mainnet", "symbol": "USDC", "tokenAddress": "0x8335", "quantity": "3", "valueUsd": "3"},
            ],
            "networkTotals": {"eth-mainnet": "4005.5", "base-mainnet": "3"},
            "totalValueUsd": "4008.5",
        }
        summary = summarize_tokens_kittychain(api_response)
        self.assertEqual(len(summary["tokens"]), 3)
        self.assertEqual(summary["tokens"][0]["symbol"], "ETH")
        self.assertAlmostEqual(summary["tokens"][0]["quantity"], 2.0)
        self.assertAlmostEqual(summary["tokens"][0]["value_usd"], 4000.0)
        self.assertAlmostEqual(summary["total_value_usd"], 4008.5)
        self.assertIn("network_totals", summary)
        self.assertAlmostEqual(summary["network_totals"]["eth-mainnet"], 4005.5)

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_render_balance_text_with_kittychain_data(self, mock_send, mock_load_key):
        from kittychain.tools.address_balance import render_balance_text

        summary = {
            "tokens": [
                {"symbol": "ETH", "token_address": None, "quantity": 2.0, "value_usd": 4000.0},
                {"symbol": "USDC", "token_address": "0xa0b8", "quantity": 5.5, "value_usd": 5.5},
            ],
            "network_totals": {"eth-mainnet": 4000.0, "base-mainnet": 5.5},
            "total_value_usd": 4005.5,
        }
        output = render_balance_text(summary)
        self.assertIn("ETH", output)
        self.assertIn("USDC", output)
        self.assertIn("4005.50000000", output)
        self.assertIn("value_usd=4000.00000000", output)

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_address_balance_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.address_balance import AddressBalanceTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "tokens": [],
                "networkTotals": {},
                "totalValueUsd": "0",
            },
        }
        tool = AddressBalanceTool()
        result = tool.execute(address="0xabc", chains=["Ethereum", "Base"])
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/address/balance", url)
        self.assertEqual(payload["address"], "0xabc")
        self.assertEqual(payload["chains"], ["Ethereum", "Base"])


_TEST_ADDR = "0x28c71c57F806Fb674d9FA9D1fd47056b8D3Da8bB"


class TestAddressIdentityKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.address_identity import AddressIdentityTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "items": [{
                    "address": _TEST_ADDR,
                    "identity": {"found": False, "rows": []},
                    "exchange": {"isExchange": False, "addressRows": [], "isDepositAddress": False, "depositRows": []},
                }]
            },
        }
        tool = AddressIdentityTool()
        result = tool.execute(addresses=[_TEST_ADDR])
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/address/identity", url)
        self.assertEqual(payload["addresses"], [_TEST_ADDR.lower()])
        self.assertIn(_TEST_ADDR, result)

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_renders_identity_and_exchange(self, mock_send, mock_load_key):
        from kittychain.tools.address_identity import AddressIdentityTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "items": [{
                    "address": _TEST_ADDR,
                    "identity": {"found": True, "rows": [{"blockchain": "ethereum", "name": "wallet.eth", "category": "ens", "source": "ens", "labelType": "identifier"}]},
                    "exchange": {"isExchange": True, "addressRows": [{"blockchain": "ethereum", "cexName": "Binance", "distinctName": "Hot Wallet", "addedBy": None, "addedDate": None}], "isDepositAddress": False, "depositRows": []},
                }]
            },
        }
        tool = AddressIdentityTool()
        result = tool.execute(addresses=[_TEST_ADDR])
        self.assertIn("wallet.eth", result)
        self.assertIn("Binance", result)
        self.assertIn("Hot Wallet", result)


class TestAddressLabelsKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.address_labels import AddressLabelsTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {"items": [{"address": _TEST_ADDR, "labels": [{"category": "Exchange", "tags": ["Hot Wallet"]}]}]},
        }
        tool = AddressLabelsTool()
        result = tool.execute(address=_TEST_ADDR, chains=["Ethereum"])
        call_args = mock_send.call_args
        url = call_args[0][0]
        self.assertIn("/api/address/labels", url)
        self.assertIn("Exchange", result)
        self.assertIn("Hot Wallet", result)


class TestAddressMaliciousKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.address_mallicious import AddressMaliciousTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "address": "0xabc",
                "isMalicious": False,
                "positiveFlags": [],
                "positiveFlagDetails": [],
                "details": {},
            },
        }
        tool = AddressMaliciousTool()
        result = tool.execute(address="0xabc")
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/address/malicious", url)
        self.assertEqual(payload["address"], "0xabc")
        self.assertIn("no positive malicious flags", result)

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_renders_malicious_flags(self, mock_send, mock_load_key):
        from kittychain.tools.address_mallicious import AddressMaliciousTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "address": "0xabc",
                "isMalicious": True,
                "positiveFlags": ["phishing_activities"],
                "positiveFlagDetails": [{"key": "phishing_activities", "label": "Phishing activity detected."}],
                "details": {"phishing_activities": "1"},
            },
        }
        tool = AddressMaliciousTool()
        result = tool.execute(address="0xabc")
        self.assertIn("malicious or risky signals", result)
        self.assertIn("phishing_activities", result)


class TestAddressTransfersKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.address_transfers import AddressTransfersTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {"address": "0xabc", "items": [], "skippedNetworks": []},
        }
        tool = AddressTransfersTool()
        result = tool.execute(address="0xabc", chains=["Ethereum"])
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/address/transfers", url)
        self.assertEqual(payload["chains"], ["Ethereum"])

    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_renders_transfer_items(self, mock_send, mock_load_key):
        from kittychain.tools.address_transfers import AddressTransfersTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "address": "0xabc",
                "items": [{
                    "network": "eth-mainnet",
                    "direction": "from",
                    "counterparty": "0xdef",
                    "asset": "USDC",
                    "totalValue": "100.5",
                    "firstTimestamp": "2026-04-01T00:00:00Z",
                    "lastTimestamp": "2026-04-02T00:00:00Z",
                }],
                "skippedNetworks": [],
            },
        }
        tool = AddressTransfersTool()
        result = tool.execute(address="0xabc", chains=["Ethereum"])
        self.assertIn("0xdef", result)
        self.assertIn("USDC", result)
        self.assertIn("100.50000000", result)


class TestTokenSearchKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_search import TokenSearchTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {"items": [{"id": "pepe", "symbol": "PEPE", "name": "Pepe", "platforms": {"ethereum": "0x6982"}}]},
        }
        tool = TokenSearchTool()
        result = tool.execute(token_symbol="PEPE")
        call_args = mock_send.call_args
        url = call_args[0][0]
        self.assertIn("/api/token/search", url)
        self.assertIn("PEPE", result)
        self.assertIn("Pepe", result)


class TestTokenDetailKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_data import TokenDetailTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "categories": ["Cryptocurrency"],
                "links": [{"label": "homepage", "url": "https://bitcoin.org"}],
                "marketCapRank": 1,
                "developerData": {},
                "listingMarkets": ["Binance"],
                "usdtTickersSummary": {},
            },
        }
        tool = TokenDetailTool()
        result = tool.execute(token_symbol="btc")
        call_args = mock_send.call_args
        url = call_args[0][0]
        self.assertIn("/api/token/detail", url)
        self.assertIn("Bitcoin", result)


class TestTokenHoldersKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_holders import TokenHoldersTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {"holders": [{"walletAddress": "0xabc", "amount": "1000000", "usdValue": "5.23"}]},
        }
        tool = TokenHoldersTool()
        result = tool.execute(token_address="0xa0b8", chain_id=1)
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/token/holders", url)
        self.assertEqual(payload["chain"], "Ethereum")
        self.assertEqual(payload["tokenAddress"], "0xa0b8")
        self.assertIn("wallet_address=0xabc", result)
        self.assertIn("usd_value=5.23000000", result)
        self.assertIn("Chain ID: 1", result)


class TestTokenPriceKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_market_data import TokenPriceTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {"items": [{"priceUsd": "0.99", "marketCapUsd": "54000000000", "volume24hUsd": "1000000000", "priceChange24hPct": "0.02", "lastUpdated": "1777565617597"}]},
        }
        tool = TokenPriceTool()
        result = tool.execute(chain="ethereum", token_address="0xa0b8")
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/token/price", url)
        self.assertEqual(payload["chain"], "ethereum")
        self.assertEqual(payload["tokenAddress"], "0xa0b8")
        self.assertIn("0.99", result)


class TestTokenSecurityKittyChain(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_security import TokenSecurityTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "isMalicious": False,
                "positiveFlags": [],
                "positiveFlagDetails": [],
                "details": {"is_open_source": "1", "token_name": "USDC"},
                "holders": [],
                "lpHolders": [],
                "dex": [],
            },
        }
        tool = TokenSecurityTool()
        result = tool.execute(token_address="0xa0b8", chain="ethereum")
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/token/security", url)
        self.assertEqual(payload["chain"], "ethereum")
        self.assertIn("no positive malicious flags", result)


class TestTransactionDetail(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.transaction_detail import TransactionDetailTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "chainId": "1",
                "blockHeight": "24993273",
                "txTime": "1777556315000",
                "txHash": "0xabc",
                "status": "success",
                "gasLimit": "248576",
                "gasUsed": "137707",
                "gasPrice": "9678081858",
                "txFee": "0.00133",
                "nonce": "4174",
                "amount": "0",
                "symbol": "ETH",
                "methodId": "0x791ac947",
                "from": [{"address": "0xfrom", "isContract": False}],
                "to": [{"address": "0xto", "isContract": True}],
                "internalTransactions": [],
                "tokenTransfers": [],
            },
        }
        tool = TransactionDetailTool()
        result = tool.execute(chain="ethereum", tx_hash="0xabc")
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/transaction/detail", url)
        self.assertEqual(payload["chain"], "ethereum")
        self.assertEqual(payload["txHash"], "0xabc")
        self.assertIn("success", result)
        self.assertIn("0xabc", result)


class TestTokenAdvanced(unittest.TestCase):
    @patch("kittychain.tools._kittychain_api._load_api_key")
    @patch("kittychain.tools._kittychain_api._send_request")
    def test_tool_calls_correct_endpoint(self, mock_send, mock_load_key):
        from kittychain.tools.token_advanced import TokenAdvancedTool

        mock_load_key.return_value = "kk_test"
        mock_send.return_value = {
            "ok": True,
            "data": {
                "totalFee": "300",
                "lpBurnedPercent": "0",
                "isInternal": False,
                "protocolId": "1",
                "progress": "100",
                "tokenTags": ["defi"],
                "createTime": "1690000000",
                "creatorAddress": "0xcreator",
                "riskControlLevel": "1",
                "top10HoldPercent": "45.67",
            },
        }
        tool = TokenAdvancedTool()
        result = tool.execute(chain="ethereum", token_address="0xabc")
        call_args = mock_send.call_args
        url = call_args[0][0]
        payload = call_args[0][1]
        self.assertIn("/api/token/advanced", url)
        self.assertEqual(payload["chain"], "ethereum")
        self.assertEqual(payload["tokenAddress"], "0xabc")
        self.assertIn("45.67", result)
        self.assertIn("defi", result)


if __name__ == "__main__":
    unittest.main()
