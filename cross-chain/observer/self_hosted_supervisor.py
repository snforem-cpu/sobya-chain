"""Fail-closed health gate for SOBYA-operated cross-chain nodes.

This module deliberately performs no network requests and has no signing path.
A deployment supplies a probe adapter for its locally operated node processes.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Callable, Iterable
from urllib.parse import urlsplit


class SupervisorConfigError(ValueError):
    pass


class NodeHealthError(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeTarget:
    network: str
    node_id: str
    rpc_url: str
    expected_identity: str
    max_head_lag: int = 3
    max_finality_lag: int = 64


@dataclass(frozen=True)
class NodeHealth:
    identity: str
    head_height: int
    finalized_height: int
    syncing: bool
    healthy: bool = True


@dataclass(frozen=True)
class NetworkReadiness:
    network: str
    ready: bool
    checked_nodes: tuple[str, ...]
    failures: tuple[str, ...]


def validate_self_hosted_url(url: str) -> None:
    """Accept only loopback/private-network or explicitly internal node URLs."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise SupervisorConfigError("node RPC URL must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SupervisorConfigError("credentials, query strings and fragments are forbidden in node URLs")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise SupervisorConfigError("node hostname must be private, loopback, or an internal DNS name") from exc
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise SupervisorConfigError("public node RPC addresses are forbidden; use SOBYA-operated private nodes")


def validate_targets(targets: Iterable[NodeTarget]) -> tuple[NodeTarget, ...]:
    values = tuple(targets)
    if not values:
        raise SupervisorConfigError("at least one self-hosted node target is required")
    seen: set[tuple[str, str]] = set()
    for target in values:
        if not target.network.strip() or not target.node_id.strip() or not target.expected_identity.strip():
            raise SupervisorConfigError("network, node ID and expected identity are required")
        key = (target.network.lower(), target.node_id)
        if key in seen:
            raise SupervisorConfigError("node IDs must be unique within each network")
        seen.add(key)
        if target.max_head_lag < 0 or target.max_finality_lag < 0:
            raise SupervisorConfigError("lag limits cannot be negative")
        validate_self_hosted_url(target.rpc_url)
    return values


def validate_health(target: NodeTarget, health: NodeHealth) -> None:
    if not health.healthy:
        raise NodeHealthError("node health endpoint reports unhealthy")
    if health.syncing:
        raise NodeHealthError("node is still syncing")
    if health.identity != target.expected_identity:
        raise NodeHealthError("node chain identity does not match configured identity")
    if health.head_height < 0 or health.finalized_height < 0:
        raise NodeHealthError("node returned a negative block height")
    if health.finalized_height > health.head_height:
        raise NodeHealthError("finalized height exceeds head height")
    if health.head_height - health.finalized_height > target.max_finality_lag:
        raise NodeHealthError("finality data is too far behind the node head")


class SelfHostedNodeSupervisor:
    """Require every configured node for a network to pass its health probe.

    Probe exceptions and malformed results fail closed. This is an operational
    availability/integrity gate, not a cryptographic light client or an
    independent-operator quorum.
    """

    def __init__(self, targets: Iterable[NodeTarget], probe: Callable[[NodeTarget], NodeHealth]):
        self.targets = validate_targets(targets)
        self.probe = probe

    def check_network(self, network: str) -> NetworkReadiness:
        selected = tuple(t for t in self.targets if t.network.lower() == network.lower())
        if not selected:
            return NetworkReadiness(network, False, (), ("no self-hosted node is configured",))
        checked: list[str] = []
        failures: list[str] = []
        for target in selected:
            checked.append(target.node_id)
            try:
                result = self.probe(target)
                if not isinstance(result, NodeHealth):
                    raise NodeHealthError("probe returned an invalid health result")
                validate_health(target, result)
            except Exception as exc:
                # Never return raw exception details that may contain local credentials.
                failures.append(f"{target.node_id}: {type(exc).__name__}")
        return NetworkReadiness(network, not failures, tuple(checked), tuple(failures))

    def all_ready(self) -> tuple[NetworkReadiness, ...]:
        networks = sorted({target.network for target in self.targets})
        return tuple(self.check_network(network) for network in networks)

    def may_accept_orders(self, network: str) -> bool:
        return self.check_network(network).ready
