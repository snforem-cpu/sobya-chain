import unittest

from self_hosted_supervisor import (
    NodeHealth, NodeHealthError, NodeTarget, SelfHostedNodeSupervisor,
    SupervisorConfigError, validate_health, validate_self_hosted_url,
    validate_targets,
)


def target(**overrides):
    values = dict(
        network="ethereum", node_id="eth-node-a",
        rpc_url="http://10.10.0.11:8545", expected_identity="1",
        max_head_lag=3, max_finality_lag=64,
    )
    values.update(overrides)
    return NodeTarget(**values)


class SelfHostedSupervisorTests(unittest.TestCase):
    def test_accepts_private_and_internal_node_addresses(self):
        for url in ("http://127.0.0.1:8545", "http://10.0.0.2:8545",
                    "https://eth-node.internal:8545", "http://node.local:8545"):
            validate_self_hosted_url(url)

    def test_rejects_public_rpc_addresses(self):
        for url in ("https://1.1.1.1", "https://eth-mainnet.example.com/rpc",
                    "https://api.mainnet-beta.solana.com"):
            with self.subTest(url=url), self.assertRaises(SupervisorConfigError):
                validate_self_hosted_url(url)

    def test_rejects_url_credentials_and_query(self):
        for url in ("http://user:pass@10.0.0.1:8545", "http://10.0.0.1/rpc?key=secret"):
            with self.subTest(url=url), self.assertRaises(SupervisorConfigError):
                validate_self_hosted_url(url)

    def test_rejects_duplicate_node_ids(self):
        with self.assertRaisesRegex(SupervisorConfigError, "unique"):
            validate_targets([target(), target()])

    def test_healthy_synced_correct_chain_is_ready(self):
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        health = NodeHealth("1", 1000, 995, 1000, False)
        supervisor = SelfHostedNodeSupervisor([target(), second], lambda _: health)
        self.assertTrue(supervisor.may_accept_orders("ethereum"))

    def test_single_node_is_not_sufficient_for_readiness(self):
        health = NodeHealth("1", 1000, 995, 1000, False)
        result = SelfHostedNodeSupervisor([target()], lambda _: health).check_network("ethereum")
        self.assertFalse(result.ready)
        self.assertIn("at least two", result.failures[0])

    def test_peer_head_is_derived_from_other_configured_nodes(self):
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        def probe(item):
            # Both probes lie by setting their own head as the reference. The
            # supervisor must ignore that field and compare the observed heads.
            if item.node_id == "eth-node-a":
                return NodeHealth("1", 1000, 995, 1000, False)
            return NodeHealth("1", 1005, 1000, 1005, False)
        result = SelfHostedNodeSupervisor([target(), second], probe).check_network("ethereum")
        self.assertFalse(result.ready)
        self.assertIn("eth-node-a: NodeHealthError", result.failures)

    def test_wrong_chain_identity_fails_closed(self):
        health = NodeHealth("5", 1000, 995, 1000, False)
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        supervisor = SelfHostedNodeSupervisor([target(), second], lambda _: health)
        self.assertFalse(supervisor.may_accept_orders("ethereum"))

    def test_syncing_node_fails_closed(self):
        health = NodeHealth("1", 1000, 995, 1000, True)
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        supervisor = SelfHostedNodeSupervisor([target(), second], lambda _: health)
        self.assertFalse(supervisor.may_accept_orders("ethereum"))

    def test_stale_finality_fails_closed(self):
        with self.assertRaisesRegex(NodeHealthError, "too far behind"):
            validate_health(target(), NodeHealth("1", 1000, 900, 1000, False))

    def test_peer_head_lag_fails_closed(self):
        with self.assertRaisesRegex(NodeHealthError, "too far behind"):
            validate_health(target(), NodeHealth("1", 1000, 995, 1005, False))

    def test_finalized_height_cannot_exceed_head(self):
        with self.assertRaisesRegex(NodeHealthError, "exceeds head"):
            validate_health(target(), NodeHealth("1", 100, 101, 100, False))

    def test_probe_exception_fails_closed_without_leaking_details(self):
        def fail(_):
            raise RuntimeError("rpc password=do-not-leak")
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        def probe(item):
            return NodeHealth("1", 1000, 995, 1000, False) if item.node_id == "eth-node-b" else fail(item)
        result = SelfHostedNodeSupervisor([target(), second], probe).check_network("ethereum")
        self.assertFalse(result.ready)
        self.assertEqual(result.failures, ("eth-node-a: RuntimeError",))
        self.assertNotIn("do-not-leak", str(result))

    def test_missing_network_fails_closed(self):
        supervisor = SelfHostedNodeSupervisor([target()], lambda _: NodeHealth("1", 1, 1, 1, False))
        self.assertFalse(supervisor.may_accept_orders("tron"))

    def test_all_configured_nodes_must_be_healthy(self):
        second = target(node_id="eth-node-b", rpc_url="http://10.10.0.12:8545")
        def probe(item):
            if item.node_id == "eth-node-b":
                raise RuntimeError("offline")
            return NodeHealth("1", 1000, 995, 1000, False)
        result = SelfHostedNodeSupervisor([target(), second], probe).check_network("ethereum")
        self.assertFalse(result.ready)
        self.assertEqual(result.checked_nodes, ("eth-node-a", "eth-node-b"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
