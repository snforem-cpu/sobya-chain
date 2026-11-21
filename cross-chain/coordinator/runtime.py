"""Composition root for the self-hosted SOBYA cross-chain coordinator.

The caller supplies already-constructed private RPC clients, pinned chain
identities, a fresh supervisor Monitor, the local ledger, and a locally loaded
bearer token. This module never reads secrets from the repository, starts the
HTTP server, signs, or broadcasts transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
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
from observer_quorum import IndependentObserverQuorum, ObserverSource
from self_hosted_supervisor import validate_self_hosted_url, SupervisorConfigError


@dataclass(frozen=True)
class SourceObserverReplica:
    observer_id: str
    ethereum_sources: dict[str, EthereumSourceConfig]
    tron_sources: dict[str, TronSourceConfig]
    solana_source: SolanaSourceConfig | None


@dataclass(frozen=True)
class DestinationObserverReplica:
    observer_id: str
    settlement: SobyaSettlementConfig


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
    additional_source_observers: tuple[SourceObserverReplica, ...] = (),
    additional_destination_observers: tuple[DestinationObserverReplica, ...] = (),
    required_observer_quorum: int = 2,
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
    source_configs = [(
        "primary", ethereum_sources, tron_sources, solana_source,
    )] + [
        (replica.observer_id, replica.ethereum_sources, replica.tron_sources, replica.solana_source)
        for replica in additional_source_observers
    ]
    destination_configs = [("primary", sobya_settlement)] + [
        (replica.observer_id, replica.settlement)
        for replica in additional_destination_observers
    ]
    source_ids = [item[0] for item in source_configs]
    destination_ids = [item[0] for item in destination_configs]
    if (len(source_ids) < 3 or len(destination_ids) < 3
            or len(set(source_ids)) != len(source_ids)
            or len(set(destination_ids)) != len(destination_ids)):
        raise ValueError("at least three uniquely named source and destination observer nodes are required")
    enabled_source_networks = set(ethereum_sources) | set(tron_sources)
    if solana_source is not None:
        enabled_source_networks.add("solana")
    source_routers = []
    for observer_id, eth_nodes, tron_nodes, sol_node in source_configs:
        configured = set(eth_nodes) | set(tron_nodes)
        if sol_node is not None:
            configured.add("solana")
        if configured != enabled_source_networks:
            raise ValueError("every source observer replica must cover the same enabled source networks")
        source_routers.append(ObserverSource(
            observer_id,
            SourceObserverRouter(
                quote_lookup=lookup, ethereum=eth_nodes, tron=tron_nodes, solana=sol_node,
            ),
        ))
    for network in enabled_source_networks:
        urls = []
        for _, eth_nodes, tron_nodes, sol_node in source_configs:
            config = (eth_nodes.get(network) or tron_nodes.get(network))
            if network == "solana":
                config = sol_node
            if config is None:
                raise ValueError("source observer replica is missing an enabled network")
            rpc_url = getattr(config.rpc, "url", None)
            if not isinstance(rpc_url, str):
                raise ValueError("source observer RPC must expose its URL")
            try:
                validate_self_hosted_url(rpc_url)
            except SupervisorConfigError as exc:
                raise ValueError("source observer RPCs must be private self-hosted nodes") from exc
            urls.append(rpc_url)
        if len(set(urls)) != len(urls):
            raise ValueError(f"source observer RPC URLs must be distinct for {network}")
    source_quorum = IndependentObserverQuorum(source_routers, required_observer_quorum)

    destination_routers = []
    destination_urls = []
    for observer_id, settlement in destination_configs:
        if (
            settlement.destination_chain_id != sobya_settlement.destination_chain_id
            or settlement.settlement_contract.lower() != sobya_settlement.settlement_contract.lower()
            or settlement.confirmations != sobya_settlement.confirmations
        ):
            raise ValueError("destination observer replicas must use identical pinned settlement identity and policy")
        rpc_url = getattr(settlement.rpc, "url", None)
        if not isinstance(rpc_url, str):
            raise ValueError("destination observer RPC must expose its URL")
        try:
            validate_self_hosted_url(rpc_url)
        except SupervisorConfigError as exc:
            raise ValueError("destination observer RPCs must be private self-hosted nodes") from exc
        destination_urls.append(rpc_url)
        destination_routers.append(ObserverSource(
            observer_id,
            DestinationPayoutRouter(
                quote_lookup=lookup, settlement=settlement, source_identities=source_identities,
            ),
        ))
    if len(set(destination_urls)) != len(destination_urls):
        raise ValueError("destination observer RPC URLs must be distinct")
    destination_quorum = IndependentObserverQuorum(
        destination_routers, required_observer_quorum
    )

    def verify_source_deposit(evidence, proof):
        return source_quorum.verify(evidence, proof).value is True

    def verify_destination_payout(evidence, proof):
        return destination_quorum.verify(evidence, proof).value is True

    admission = ReadinessAdmissionGuard(monitor, ledger)
    coordinator = LocalCoordinator(admission)
    return create_server(
        host, port, coordinator,
        bearer_token=bearer_token,
        verify_quote_signature=quote_signatures.verify,
        verify_source_deposit=verify_source_deposit,
        verify_destination_payout=verify_destination_payout,
        quote_pricer=quote_pricer,
    )
