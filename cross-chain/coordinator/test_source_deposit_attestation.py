import unittest

from source_deposit_attestation import (
    SourceDepositAttestation,
    SourceDepositAttestationError,
    build_eip712_source_deposit_attestation,
    eip712_source_deposit_digest,
)


class SourceDepositAttestationTests(unittest.TestCase):
    def setUp(self):
        self.attestation = SourceDepositAttestation(
            order_id="0x" + "01" * 32,
            source_chain="0x" + "02" * 32,
            source_escrow="0x" + "03" * 32,
            source_asset="0x" + "04" * 32,
            source_amount=25_000_000,
            recipient="0x" + "11" * 20,
            soby_amount=3 * 10**18,
            solver="0x" + "22" * 20,
            destination_chain_id=357812033857,
            release_after=1_900_000_000,
        )
        self.settlement = "0x" + "33" * 20

    def test_digest_is_deterministic_and_typed_data_matches_contract_fields(self):
        digest = eip712_source_deposit_digest(
            self.attestation, settlement_contract=self.settlement
        )
        self.assertEqual(len(digest), 32)
        self.assertEqual(
            digest,
            eip712_source_deposit_digest(
                self.attestation, settlement_contract=self.settlement
            ),
        )
        typed = build_eip712_source_deposit_attestation(
            self.attestation, settlement_contract=self.settlement
        )
        self.assertEqual(typed["primaryType"], "SourceDepositAttestation")
        self.assertEqual(typed["domain"]["chainId"], 357812033857)
        self.assertEqual(typed["message"]["releaseAfter"], 1_900_000_000)

    def test_digest_is_bound_to_settlement_address_and_chain(self):
        original = eip712_source_deposit_digest(
            self.attestation, settlement_contract=self.settlement
        )
        other_contract = eip712_source_deposit_digest(
            self.attestation, settlement_contract="0x" + "44" * 20
        )
        changed_chain = SourceDepositAttestation(
            **{**self.attestation.__dict__, "destination_chain_id": 357812033858}
        )
        self.assertNotEqual(original, other_contract)
        self.assertNotEqual(
            original,
            eip712_source_deposit_digest(
                changed_chain, settlement_contract=self.settlement
            ),
        )

    def test_digest_is_bound_to_exact_order_and_source_deposit(self):
        original = eip712_source_deposit_digest(
            self.attestation, settlement_contract=self.settlement
        )
        changed = SourceDepositAttestation(
            **{**self.attestation.__dict__, "source_amount": 25_000_001}
        )
        self.assertNotEqual(
            original,
            eip712_source_deposit_digest(changed, settlement_contract=self.settlement),
        )

    def test_rejects_bool_amount_and_invalid_uint64_deadline(self):
        with self.assertRaises(SourceDepositAttestationError):
            invalid = SourceDepositAttestation(
                **{**self.attestation.__dict__, "source_amount": True}
            )
            eip712_source_deposit_digest(invalid, settlement_contract=self.settlement)
        with self.assertRaises(SourceDepositAttestationError):
            invalid = SourceDepositAttestation(
                **{**self.attestation.__dict__, "release_after": 1 << 64}
            )
            build_eip712_source_deposit_attestation(
                invalid, settlement_contract=self.settlement
            )


if __name__ == "__main__":
    unittest.main()
