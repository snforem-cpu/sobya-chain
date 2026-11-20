import json
import unittest
from unittest.mock import Mock

from rpc_probes import (
    ProbeError, probe_evm, probe_solana, probe_tron, probe_for_network,
)
from self_hosted_supervisor import NodeTarget


def target(network="ethereum", url="http://127.0.0.1:8545", identity="1"):
    return NodeTarget(network, "local-node", url, identity, 10, 100)


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, limit=-1):
        return self.raw[:limit]


def rpc_opener(results):
    calls = []
    def opener(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        method = body["method"]
        value = results[method]
        return FakeResponse({"jsonrpc": "2.0", "id": body["id"], "result": value})
    return opener, calls


class ReadOnlyProbeTests(unittest.TestCase):
    def test_evm_probe_checks_finality_and_chain_id(self):
        opener, calls = rpc_opener({
            "eth_chainId": "0x1", "eth_blockNumber": "0x64",
            "eth_getBlockByNumber": {"number": "0x60"}, "eth_syncing": False,
        })
        health = probe_evm(target(), opener=opener)
        self.assertEqual((health.identity, health.head_height, health.finalized_height), ("1", 100, 96))
        self.assertFalse(health.syncing)
        self.assertEqual(len(calls), 4)

    def test_evm_fails_closed_when_finalized_tag_missing(self):
        opener, _ = rpc_opener({
            "eth_chainId": "0x1", "eth_blockNumber": "0x64",
            "eth_getBlockByNumber": None, "eth_syncing": False,
        })
        with self.assertRaises(ProbeError):
            probe_evm(target(), opener=opener)

    def test_tron_uses_genesis_and_solidity_height(self):
        def opener(request, timeout):
            body = json.loads(request.data)
            if request.full_url.endswith("/wallet/getblockbynum"):
                result = {"blockID": "genesis-hash"}
            elif request.full_url.endswith("/wallet/getnowblock"):
                result = {"block_header": {"raw_data": {"number": 105}}}
            else:
                result = {"block_header": {"raw_data": {"number": 104}}}
            return FakeResponse(result)
        health = probe_tron(target("tron", "http://127.0.0.1:8090", "genesis-hash"), opener=opener)
        self.assertEqual((health.identity, health.head_height, health.finalized_height), ("genesis-hash", 105, 104))

    def test_solana_checks_genesis_health_and_commitment_slots(self):
        opener, _ = rpc_opener({
            "getGenesisHash": "solana-genesis", "getHealth": "ok",
            "getSlot": 200,
        })
        # Distinguish processed and finalized commitment requests.
        calls = []
        def sol_opener(request, timeout):
            body = json.loads(request.data)
            calls.append(body)
            if body["method"] == "getSlot":
                result = 200 if body["params"][0]["commitment"] == "processed" else 198
            else:
                result = {"getGenesisHash": "solana-genesis", "getHealth": "ok"}[body["method"]]
            return FakeResponse({"jsonrpc": "2.0", "id": 1, "result": result})
        health = probe_solana(target("solana", "http://127.0.0.1:8899", "solana-genesis"), opener=sol_opener)
        self.assertEqual((health.head_height, health.finalized_height), (200, 198))
        self.assertFalse(health.syncing)

    def test_network_factory_rejects_unknown_network(self):
        with self.assertRaises(ProbeError):
            probe_for_network("unknown")

    def test_public_rpc_rejected_before_request(self):
        bad = target(url="https://api.mainnet-beta.solana.com")
        with self.assertRaises(Exception):
            probe_evm(bad, opener=Mock())

if __name__ == "__main__":
    unittest.main(verbosity=2)
