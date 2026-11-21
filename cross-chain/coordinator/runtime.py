"""Composition root for the self-hosted SOBYA cross-chain coordinator.

The caller supplies already-constructed private RPC clients, pinned chain
identities, a fresh supervisor Monitor, the local ledger, and a locally loaded
bearer token. This module never reads secrets from the repository, starts the
HTTP server, signs, or broadcasts transactions.
"""
from __future__ import annotations

from typing import Any

from admission import ReadinessAdmissionGuard
from coordinator import LocalCoordinator
from eip712_quote_verifier import Eip712QuoteVerifier, Eip712QuoteDomain
from quote_signature_router import ChainQuoteSignatureVerifier
from solana_quote_verifier import SolanaQuoteVerifier
from http_api import create_server
from order_ledger import CrossChainOrderLedger
from pricing import InventoryAwareQuotePricer
from source_observer_router import (
    SourceObserverRouter, EthereumSourceConfig, TronSourceConfig,
    SolanaSourceConfig, quote_from_ledger,
)
from destination_payout_router import (
    DestinationPayoutRouter, SobyaSettlementConfig, SourceIdentity,
)
from solver_balance_reader import FinalizedNativeBalanceReader


def build_local_server(
    *,
    host: str,
    port: int,
    bearer_token: str,
    monitor: Any,
    ledger: CrossChainOrderLedger,
    quote_domains: dict[str, Eip712QuoteDomain],
    ethereum_sources: dict[str, EthereumSourceConfig],
    tron_sources: dict[str, TronSourceConfig],
    solana_source: SolanaSourceConfig | None,
    sobya_settlement: SobyaSettlementConfig,
    source_identities: dict[str, SourceIdentity],
    quote_pricer: InventoryAwareQuotePricer,
):
    """Build, but do not start, the fully wired loopback coordinator HTTP server."""
    balance_reader = getattr(quote_pricer, "finalized_balance", None)
    if not isinstance(balance_reader, FinalizedNativeBalanceReader):
        raise ValueError("runtime requires a pinned finalized SOBYA native-balance reader")
    if balance_reader.expected_chain_id != sobya_settlement.destination_chain_id:
        raise ValueError("solver balance reader and payout observer chain IDs differ")
    settlement_rpc_url = getattr(sobya_settlement.rpc, "url", None)
    if not isinstance(settlement_rpc_url, str) or balance_reader.rpc.url != settlement_rpc_url:
        raise ValueError("solver balance reader must use the same pinned SOBYA node as payout verification")
    evm_quote_signatures = Eip712QuoteVerifier(quote_domains)
    solana_quote_signatures = None
    if solana_source is not None:
        solana_quote_signatures = SolanaQuoteVerifier(
            program_id=solana_source.program_id,
            config_authority=solana_source.config_authority,
            usdt_mint=solana_source.usdt_mint,
            destination_chain_id=solana_source.sobya_chain_id,
        )
    quote_signatures = ChainQuoteSignatureVerifier(
        evm_quote_signatures, solana_quote_signatures
    )
    lookup = lambda order_id: quote_from_ledger(ledger, order_id)
    source_observer = SourceObserverRouter(
        quote_lookup=lookup,
        ethereum=ethereum_sources,
        tron=tron_sources,
        solana=solana_source,
    )
    destination_observer = DestinationPayoutRouter(
        quote_lookup=lookup,
        settlement=sobya_settlement,
        source_identities=source_identities,
    )
    admission = ReadinessAdmissionGuard(monitor, ledger)
    coordinator = LocalCoordinator(admission)
    return create_server(
        host, port, coordinator,
        bearer_token=bearer_token,
        verify_quote_signature=quote_signatures.verify,
        verify_source_deposit=source_observer,
        verify_destination_payout=destination_observer,
        quote_pricer=quote_pricer,
    )
