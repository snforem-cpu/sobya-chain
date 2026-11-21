import unittest
from attestation_payload import (
    AttestationPayloadError, EvmPayoutAttestation, build_eip712_payout,
    build_solana_attest_payout_instruction, eip712_payout_digest,
)


class AttestationPayloadTests(unittest.TestCase):
    def setUp(self):
        self.value = EvmPayoutAttestation(
            order_id="0x"+"11"*32, destination_tx_hash="0x"+"22"*32,
            destination_chain_id=357812033857, destination_recipient="0x"+"33"*20,
            destination_amount=10**18, source_escrow="0x"+"44"*20,
            source_chain_id=1,
        )

    def test_eip712_payload_matches_escrow_domain_and_fields(self):
        payload = build_eip712_payout(self.value)
        self.assertEqual(payload["domain"]["name"], "SOBYA Cross-Chain Escrow")
        self.assertEqual(payload["domain"]["version"], "1")
        self.assertEqual(payload["domain"]["chainId"], 1)
        self.assertEqual(payload["primaryType"], "Payout")
        self.assertEqual(payload["message"]["sourceChainId"], 1)
        self.assertEqual(payload["message"]["destinationChainId"], 357812033857)
        self.assertEqual(payload["message"]["escrow"], self.value.source_escrow)

    def test_digest_is_deterministic(self):
        self.assertEqual(eip712_payout_digest(self.value), eip712_payout_digest(self.value))
        self.assertEqual(len(eip712_payout_digest(self.value)), 66)

    def test_digest_binds_destination_tx_hash(self):
        changed = EvmPayoutAttestation(**{**self.value.__dict__, "destination_tx_hash": "0x"+"55"*32})
        self.assertNotEqual(eip712_payout_digest(self.value), eip712_payout_digest(changed))

    def test_digest_binds_source_chain_and_escrow_domain(self):
        changed = EvmPayoutAttestation(**{**self.value.__dict__, "source_chain_id": 728126428})
        self.assertNotEqual(eip712_payout_digest(self.value), eip712_payout_digest(changed))

    def test_tron_prefixed_address_normalizes(self):
        changed = EvmPayoutAttestation(**{**self.value.__dict__, "source_escrow": "41"+"44"*20})
        self.assertEqual(eip712_payout_digest(self.value), eip712_payout_digest(changed))

    def test_invalid_amount_rejected(self):
        changed = EvmPayoutAttestation(**{**self.value.__dict__, "destination_amount": 0})
        with self.assertRaises(AttestationPayloadError):
            build_eip712_payout(changed)

    def test_solana_instruction_matches_borsh_variant(self):
        raw = build_solana_attest_payout_instruction("0x"+"11"*32, "0x"+"22"*32)
        self.assertEqual(raw, b"\x02" + bytes.fromhex("11"*32) + bytes.fromhex("22"*32))
        self.assertEqual(len(raw), 65)

    def test_solana_instruction_rejects_bad_hash(self):
        with self.assertRaises(AttestationPayloadError):
            build_solana_attest_payout_instruction("0x12", "0x"+"22"*32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
