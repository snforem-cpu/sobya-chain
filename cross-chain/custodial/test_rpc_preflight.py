import json
import unittest
from unittest.mock import patch

from rpc_preflight import (
    RpcPreflightError, check_network, EXPECTED, USDT_ETH, SOBYA_INVENTORY,
)


class FakeResponse:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self):
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": self.value}).encode()


class RpcPreflightTests(unittest.TestCase):
    def test_ethereum_chain_finality_and_usdt_contract(self):
        def fake_open(request, timeout):
            payload = json.loads(request.data)
            method = payload["method"]
            if method == "eth_chainId":
                value = hex(EXPECTED["ethereum"])
            elif method == "eth_getBlockByNumber":
                value = (
                    {"number": "0x100"} if payload["params"][0] == "latest"
                    else {"number": "0xf0"}
                )
            elif method == "eth_getCode":
                value = "0x60016000"
            else:
                raise AssertionError(method)
            return FakeResponse(value)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            result = check_network("ethereum", "https://rpc.example")
        self.assertEqual(result["chain_id"], 1)
        self.assertEqual(result["finalized_block"], 240)
        self.assertEqual(result["usdt_contract_code"], "present")

    def test_sobya_reads_inventory_balance_at_finalized_block(self):
        calls = []
        def fake_open(request, timeout):
            payload = json.loads(request.data)
            calls.append((payload["method"], payload["params"]))
            method = payload["method"]
            if method == "eth_chainId":
                value = hex(EXPECTED["sobya"])
            elif method == "eth_getBlockByNumber":
                value = {"number": "0x20" if payload["params"][0] == "latest" else "0x1f"}
            elif method == "eth_getBalance":
                value = "0x1234"
            else:
                raise AssertionError(method)
            return FakeResponse(value)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            result = check_network("sobya", "https://rpc.example")
        self.assertEqual(result["inventory_balance_wei"], 0x1234)
        self.assertIn(("eth_getBalance", [SOBYA_INVENTORY, "finalized"]), calls)

    def test_rejects_wrong_chain(self):
        def fake_open(request, timeout):
            return FakeResponse("0x1")
        with patch("urllib.request.urlopen", side_effect=fake_open):
            with self.assertRaisesRegex(RpcPreflightError, "wrong chain ID"):
                check_network("sobya", "https://rpc.example")

    def test_rejects_non_https_endpoint(self):
        with self.assertRaisesRegex(RpcPreflightError, "HTTPS"):
            check_network("ethereum", "http://rpc.example")


if __name__ == "__main__":
    unittest.main(verbosity=2)
