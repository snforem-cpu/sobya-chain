import unittest
from eth_keys import keys

from attestor_service import (
    AttestorService, AttestorServiceError, EvmSigningBackend,
    FinalizedReservation, PinnedSourceIdentity,
)
from order_ledger import OrderQuote, SourceDepositEvidence, DestinationPayoutEvidence


class AttestorServiceTests(unittest.TestCase):
    def setUp(self):
        self.private_key = keys.PrivateKey(bytes.fromhex("11" * 32))
        self.address = self.private_key.public_key.to_checksum_address()
        self.quote = OrderQuote(
            order_id="0x" + "01" * 32,
            source_chain="ethereum",
            source_asset="0x" + "22" * 20,
            source_amount=25_000_000,
            user="0x" + "33" * 20,
            solver="0x" + "44" * 20,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55" * 20,
            destination_amount=3 * 10**18,
            quote_expiry=1_900_000_000,
            refund_after=1_900_000_300,
        )
        self.source_evidence = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "66" * 32, event_index=1,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        self.destination_evidence = DestinationPayoutEvidence(
            order_id=self.quote.order_id, transaction_id="0x" + "77" * 32,
            event_index=2, destination_chain_id=self.quote.destination_chain_id,
            source_chain="ethereum", source_asset=self.quote.source_asset,
            source_amount=self.quote.source_amount, recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount, solver=self.quote.solver,
            finalized_reference="sobya:confirmations:200",
        )
        self.reservation = FinalizedReservation(
            solver=self.quote.solver, recipient=self.quote.destination_recipient,
            amount=self.quote.destination_amount, release_after=self.quote.refund_after,
            active=True,
        )
        self.identity = PinnedSourceIdentity(
            source_chain="ethereum", source_chain_id=1,
            source_chain_hash="0x" + "88" * 32,
            source_escrow_id="0x" + "99" * 32,
            source_asset_id="0x" + "aa" * 32,
            source_escrow_address="0x" + "bb" * 20,
        )
        self.backend = EvmSigningBackend(
            self.address,
            lambda digest: self.private_key.sign_msg_hash(digest).to_bytes(),
        )
        self.service = AttestorService(
            attestor=self.backend,
            quote_lookup=lambda order_id: self.quote,
            verify_source_deposit=lambda evidence, proof: proof == {"ok": True},
            verify_destination_payout=lambda evidence, proof: proof == {"ok": True},
            finalized_reservation=lambda order_id: self.reservation,
            attestor_membership=lambda network, contract, address: True,
            settlement_contract="0x" + "cc" * 20,
            destination_chain_id=357812033857,
            source_identities={"ethereum": self.identity},
        )

    def test_source_deposit_attestation_requires_verified_source_and_reservation(self):
        result = self.service.sign_source_deposit(self.source_evidence, {"ok": True})
        self.assertEqual(result["purpose"], "SOBYA_SOURCE_DEPOSIT_RELEASE")
        self.assertEqual(result["attestor"].lower(), self.address.lower())
        self.assertEqual(len(bytes.fromhex(result["signature"][2:])), 65)

    def test_source_deposit_does_not_sign_unverified_evidence(self):
        with self.assertRaises(AttestorServiceError):
            self.service.sign_source_deposit(self.source_evidence, {"ok": False})

    def test_source_deposit_requires_exact_finalized_vault_reservation(self):
        self.service.finalized_reservation = lambda order_id: FinalizedReservation(
            solver=self.quote.solver, recipient=self.quote.destination_recipient,
            amount=self.quote.destination_amount - 1,
            release_after=self.quote.refund_after, active=True,
        )
        with self.assertRaises(AttestorServiceError):
            self.service.sign_source_deposit(self.source_evidence, {"ok": True})

    def test_source_release_requires_onchain_attestor_membership(self):
        self.service.attestor_membership = lambda network, contract, address: False
        with self.assertRaises(AttestorServiceError):
            self.service.sign_source_deposit(self.source_evidence, {"ok": True})

    def test_payout_attestation_requires_verified_finalized_sobya_receipt(self):
        result = self.service.sign_evm_source_payout(self.destination_evidence, {"ok": True})
        self.assertEqual(result["purpose"], "SOURCE_ESCROW_SOLVER_PAYOUT")
        self.assertEqual(result["attestor"].lower(), self.address.lower())
        self.assertEqual(len(bytes.fromhex(result["signature"][2:])), 65)

    def test_payout_attestation_does_not_sign_unverified_receipt(self):
        with self.assertRaises(AttestorServiceError):
            self.service.sign_evm_source_payout(self.destination_evidence, {"ok": False})

    def test_wrong_evidence_order_is_rejected(self):
        changed = DestinationPayoutEvidence(
            **{**self.destination_evidence.__dict__, "destination_amount": 1}
        )
        with self.assertRaises(AttestorServiceError):
            self.service.sign_evm_source_payout(changed, {"ok": True})

    def test_solana_instruction_uses_pinned_solana_attestor_not_evm_key(self):
        from dataclasses import replace
        solana_quote = replace(
            self.quote, source_chain="solana",
            source_asset="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        )
        solana_evidence = replace(
            self.destination_evidence, source_chain="solana",
            source_asset=solana_quote.source_asset,
        )
        solana_attestor = "11111111111111111111111111111111"
        program_id = "11111111111111111111111111111111"
        calls = []
        service = AttestorService(
            attestor=self.backend,
            quote_lookup=lambda order_id: solana_quote,
            verify_source_deposit=lambda *_: True,
            verify_destination_payout=lambda *_: True,
            finalized_reservation=lambda _: self.reservation,
            attestor_membership=lambda network, contract, address: (
                calls.append((network, contract, address)) or True
            ),
            settlement_contract="0x" + "cc" * 20,
            destination_chain_id=357812033857,
            source_identities={"solana": PinnedSourceIdentity(
                source_chain="solana", source_chain_id=0,
                source_chain_hash="0x" + "88" * 32,
                source_escrow_id="0x" + "99" * 32,
                source_asset_id="0x" + "aa" * 32,
                source_program_id=program_id,
                solana_attestor_pubkey=solana_attestor,
            )},
        )
        result = service.build_solana_payout_instruction(solana_evidence, {"ok": True})
        self.assertEqual(result["attestor"], solana_attestor)
        self.assertEqual(calls, [("solana", program_id, solana_attestor)])
        self.assertEqual(len(bytes.fromhex(result["instruction_data"][2:])), 65)

    def test_signature_backend_must_recover_configured_attestor(self):
        wrong = keys.PrivateKey(bytes.fromhex("12" * 32))
        backend = EvmSigningBackend(
            self.address, lambda digest: wrong.sign_msg_hash(digest).to_bytes()
        )
        with self.assertRaises(AttestorServiceError):
            backend.sign(bytes.fromhex("ab" * 32))


if __name__ == "__main__":
    unittest.main(verbosity=2)
