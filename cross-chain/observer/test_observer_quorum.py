import unittest
from dataclasses import dataclass

from observer_quorum import (
    IndependentObserverQuorum, ObserverSource, QuorumVerificationError,
)


@dataclass(frozen=True)
class Evidence:
    order_id: str
    amount: int
    block_hash: bytes


class ObserverQuorumTests(unittest.TestCase):
    def test_strict_majority_accepts_matching_evidence(self):
        evidence = Evidence("order-1", 42, b"\x01" * 32)
        quorum = IndependentObserverQuorum([
            ObserverSource("rpc-a", lambda: evidence),
            ObserverSource("rpc-b", lambda: evidence),
            ObserverSource("rpc-c", lambda: Evidence("order-1", 99, b"\x02" * 32)),
        ], 2)
        result = quorum.verify()
        self.assertEqual(result.value, evidence)
        self.assertEqual(result.agreeing_sources, ("rpc-a", "rpc-b"))
        self.assertEqual(result.rejected_sources, ("rpc-c",))

    def test_provider_failure_does_not_count_as_vote(self):
        evidence = {"order": "x", "amount": 10}
        def fail():
            raise RuntimeError("sensitive provider detail")
        quorum = IndependentObserverQuorum([
            ObserverSource("a", lambda: evidence),
            ObserverSource("b", fail),
            ObserverSource("c", lambda: evidence),
        ], 2)
        result = quorum.verify()
        self.assertEqual(result.agreeing_sources, ("a", "c"))
        self.assertIn("b", result.rejected_sources)

    def test_disagreement_without_majority_fails_closed(self):
        quorum = IndependentObserverQuorum([
            ObserverSource("a", lambda: {"amount": 1}),
            ObserverSource("b", lambda: {"amount": 2}),
            ObserverSource("c", lambda: {"amount": 3}),
        ], 2)
        with self.assertRaises(QuorumVerificationError):
            quorum.verify()

    def test_single_matching_response_is_not_enough(self):
        quorum = IndependentObserverQuorum([
            ObserverSource("a", lambda: 7),
            ObserverSource("b", lambda: 7),
            ObserverSource("c", lambda: 8),
        ], 3)
        with self.assertRaises(QuorumVerificationError):
            quorum.verify()

    def test_duplicate_source_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            IndependentObserverQuorum([
                ObserverSource("same", lambda: 1),
                ObserverSource("same", lambda: 1),
            ], 2)

    def test_quorum_must_be_strict_majority(self):
        with self.assertRaisesRegex(ValueError, "strict majority"):
            IndependentObserverQuorum([
                ObserverSource("a", lambda: 1),
                ObserverSource("b", lambda: 1),
                ObserverSource("c", lambda: 1),
                ObserverSource("d", lambda: 1),
            ], 2)

    def test_mapping_key_order_does_not_change_evidence(self):
        quorum = IndependentObserverQuorum([
            ObserverSource("a", lambda: {"a": 1, "b": 2}),
            ObserverSource("b", lambda: {"b": 2, "a": 1}),
            ObserverSource("c", lambda: {"a": 9}),
        ], 2)
        self.assertEqual(quorum.verify().agreeing_sources, ("a", "b"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
