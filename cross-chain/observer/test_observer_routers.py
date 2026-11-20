import unittest
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coordinator"))

from order_ledger import OrderQuote, SourceDepositEvidence, DestinationPayoutEvidence
from settlement_observer import VerificationError
from source_observer_router import (SourceObserverRouter, EthereumSourceConfig, SolanaSourceConfig, _build_solana_expected_deposit)
from solana_source_observer import _b58encode, _find_program_address, _pubkey_bytes
from destination_payout_router import (
    DestinationPayoutRouter, SobyaSettlementConfig, quote_from_ledger,
)


class ObserverRouterTests(unittest.TestCase):
    def setUp(self):
        self.quote = OrderQuote(
            order_id="0x" + "01"*32, source_chain="ethereum",
            source_asset="0x" + "33"*20, source_amount=20_000_000,
            user="0x" + "22"*20, solver="0x" + "44"*20,
            destination_chain_id=357812033857,
            destination_recipient="0x" + "55"*20,
            destination_amount=10**18, quote_expiry=1_900_000_000,
            refund_after=1_900_003_600,
        )

    def test_source_router_fails_closed_without_pinned_node(self):
        router = SourceObserverRouter(quote_lookup=lambda _id: self.quote)
        evidence = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "aa"*32, event_index=0,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        with self.assertRaises(VerificationError):
            router(evidence, {"transaction_id": evidence.transaction_id})

    def test_source_router_rejects_public_rpc_before_query(self):
        class PublicRpc:
            url = "https://rpc.example.invalid"
        router = SourceObserverRouter(
            quote_lookup=lambda _id: self.quote,
            ethereum={"ethereum": EthereumSourceConfig(1, "0x" + "11"*20, PublicRpc())},
        )
        evidence = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "aa"*32, event_index=0,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        with self.assertRaises(VerificationError):
            router(evidence, {"transaction_id": evidence.transaction_id})

    def test_source_router_rejects_caller_supplied_extra_fields(self):
        router = SourceObserverRouter(quote_lookup=lambda _id: self.quote)
        evidence = SourceDepositEvidence(
            order_id=self.quote.order_id, source_chain="ethereum",
            transaction_id="0x" + "aa"*32, event_index=0,
            source_asset=self.quote.source_asset, source_amount=self.quote.source_amount,
            user=self.quote.user, solver=self.quote.solver,
            destination_chain_id=self.quote.destination_chain_id,
            destination_recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            finalized_reference="ethereum:finalized:100",
        )
        with self.assertRaises(VerificationError):
            router(evidence, {"transaction_id": evidence.transaction_id, "finalized": True})

    def test_destination_router_requires_pinned_source_identity(self):
        class NeverRpc:
            def call(self, *_args):
                raise AssertionError("RPC must not be called without a pinned source identity")
        router = DestinationPayoutRouter(
            quote_lookup=lambda _id: self.quote,
            settlement=SobyaSettlementConfig(
                destination_chain_id=357812033857,
                settlement_contract="0x" + "66"*20,
                confirmations=1, rpc=NeverRpc(),
            ),
            source_identities={},
        )
        evidence = DestinationPayoutEvidence(
            order_id=self.quote.order_id, transaction_id="0x" + "aa"*32,
            event_index=0, destination_chain_id=self.quote.destination_chain_id,
            source_chain="ethereum", source_asset=self.quote.source_asset,
            source_amount=self.quote.source_amount,
            recipient=self.quote.destination_recipient,
            destination_amount=self.quote.destination_amount,
            solver=self.quote.solver, finalized_reference="sobya:confirmations:100",
        )
        with self.assertRaises(VerificationError):
            router(evidence, {"transaction_hash": evidence.transaction_id})

    def test_quote_from_ledger_reconstructs_immutable_quote(self):
        class FakeLedger:
            def get_order(self, order_id):
                return {"quote": self_quote.__dict__}
        self_quote = self.quote
        self.assertEqual(quote_from_ledger(FakeLedger(), self.quote.order_id), self.quote)


    def test_solana_expected_order_uses_pinned_config_authority_not_swap_user(self):
        program_id = _b58encode(bytes([9]) * 32)
        config_authority = _b58encode(bytes([12]) * 32)
        usdt_mint = _b58encode(bytes([7]) * 32)
        user = _b58encode(bytes([1]) * 32)
        quote = replace(
            self.quote, source_chain="solana", source_asset=usdt_mint,
            user=user, solver=_b58encode(bytes([2]) * 32),
        )
        config = SolanaSourceConfig(
            program_id=program_id, config_authority=config_authority,
            usdt_mint=usdt_mint, sobya_chain_id=quote.destination_chain_id,
            expected_genesis_hash="pinned-genesis", rpc=object(),
        )
        expected = _build_solana_expected_deposit(quote, "test-signature", config)
        pinned_pda, _ = _find_program_address(
            [b"config", _pubkey_bytes(config_authority)], program_id
        )
        user_pda, _ = _find_program_address(
            [b"config", _pubkey_bytes(user)], program_id
        )
        self.assertEqual(expected.config_pda, pinned_pda)
        self.assertNotEqual(expected.config_pda, user_pda)
        self.assertEqual(expected.config_authority, config_authority)
        self.assertEqual(expected.sobya_chain_id, quote.destination_chain_id)

    def test_solana_router_rejects_wrong_pinned_mint_or_chain(self):
        program_id = _b58encode(bytes([9]) * 32)
        config = SolanaSourceConfig(
            program_id=program_id,
            config_authority=_b58encode(bytes([12]) * 32),
            usdt_mint=_b58encode(bytes([7]) * 32),
            sobya_chain_id=self.quote.destination_chain_id,
            expected_genesis_hash="pinned-genesis", rpc=object(),
        )
        with self.assertRaisesRegex(VerificationError, "asset"):
            _build_solana_expected_deposit(self.quote, "sig", config)
        quote = replace(
            self.quote, source_chain="solana", source_asset=config.usdt_mint,
            destination_chain_id=self.quote.destination_chain_id + 1,
        )
        with self.assertRaisesRegex(VerificationError, "chain ID"):
            _build_solana_expected_deposit(quote, "sig", config)

if __name__ == "__main__":
    unittest.main()
