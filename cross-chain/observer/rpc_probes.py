"""Read-only JSON-RPC/HTTP health probes for SOBYA-operated nodes.

No public RPC fallback, signing, transaction submission, or key handling.
The configured URL must pass the supervisor's self-hosted URL policy.
"""
from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from self_hosted_supervisor import (
    NodeHealth, NodeTarget, NodeHealthError, validate_self_hosted_url,
)

MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_TIMEOUT_SECONDS = 5.0


class ProbeError(NodeHealthError):
    """A bounded, sanitized node-probe failure."""


def _http_json(
    url: str,
    *,
    method: str = "POST",
    payload: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    opener: Callable[..., Any] = urlopen,
) -> Any:
    validate_self_hosted_url(url)
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=data, method=method, headers={
        "Accept": "application/json",
        **({"Content-Type": "application/json"} if data is not None else {}),
    })
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProbeError("node response exceeds size limit")
        return json.loads(raw.decode("utf-8"))
    except ProbeError:
        raise
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProbeError("node HTTP/JSON request failed") from exc


def _rpc(url: str, method: str, params: list[Any] | None = None, *, opener=urlopen) -> Any:
    response = _http_json(url, payload={
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or [],
    }, opener=opener)
    if not isinstance(response, dict) or response.get("id") != 1:
        raise ProbeError("malformed JSON-RPC response")
    if response.get("error") is not None or "result" not in response:
        raise ProbeError("JSON-RPC method failed")
    return response["result"]


def _quantity(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ProbeError(f"invalid {field}")
    try:
        number = int(value, 16)
    except ValueError as exc:
        raise ProbeError(f"invalid {field}") from exc
    if number < 0:
        raise ProbeError(f"invalid {field}")
    return number


def probe_evm(target: NodeTarget, *, opener=urlopen) -> NodeHealth:
    """Probe Ethereum or SOBYA EVM using chain ID, head, finalized tag, syncing."""
    identity = _rpc(target.rpc_url, "eth_chainId", opener=opener)
    head = _quantity(_rpc(target.rpc_url, "eth_blockNumber", opener=opener), "head block")
    finalized_block = _rpc(target.rpc_url, "eth_getBlockByNumber", ["finalized", False], opener=opener)
    if not isinstance(finalized_block, dict):
        raise ProbeError("finalized block tag is unavailable")
    finalized = _quantity(finalized_block.get("number"), "finalized block")
    syncing = _rpc(target.rpc_url, "eth_syncing", opener=opener)
    if not isinstance(identity, str) or not identity.startswith("0x"):
        raise ProbeError("invalid EVM chain identity")
    try:
        identity = str(int(identity, 16))
    except ValueError as exc:
        raise ProbeError("invalid EVM chain identity") from exc
    if syncing is not False and not isinstance(syncing, dict):
        raise ProbeError("invalid EVM syncing response")
    return NodeHealth(identity, head, finalized, head, syncing is not False)


def probe_tron(target: NodeTarget, *, opener=urlopen) -> NodeHealth:
    """Probe a local TRON full-node HTTP API; finality uses Solidity-node height."""
    base = target.rpc_url.rstrip("/")
    genesis = _http_json(base + "/wallet/getblockbynum", payload={"num": 0}, opener=opener)
    head_block = _http_json(base + "/wallet/getnowblock", payload={}, opener=opener)
    solid_block = _http_json(base + "/walletsolidity/getnowblock", payload={}, opener=opener)
    try:
        identity = genesis["blockID"]
        head = int(head_block["block_header"]["raw_data"]["number"])
        finalized = int(solid_block["block_header"]["raw_data"]["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProbeError("malformed TRON node response") from exc
    if not isinstance(identity, str) or not identity:
        raise ProbeError("invalid TRON genesis identity")
    return NodeHealth(identity, head, finalized, head, False)


def probe_solana(target: NodeTarget, *, opener=urlopen) -> NodeHealth:
    """Probe local Solana JSON-RPC using genesis hash, health and slot commitments."""
    identity = _rpc(target.rpc_url, "getGenesisHash", opener=opener)
    health = _rpc(target.rpc_url, "getHealth", opener=opener)
    head = _rpc(target.rpc_url, "getSlot", [{"commitment": "processed"}], opener=opener)
    finalized = _rpc(target.rpc_url, "getSlot", [{"commitment": "finalized"}], opener=opener)
    if not isinstance(identity, str) or not identity:
        raise ProbeError("invalid Solana genesis identity")
    if not isinstance(head, int) or not isinstance(finalized, int):
        raise ProbeError("invalid Solana slot response")
    return NodeHealth(identity, head, finalized, head, health != "ok")


def probe_for_network(network: str, *, opener=urlopen) -> Callable[[NodeTarget], NodeHealth]:
    """Return the chain-specific read-only probe for a configured network."""
    normalized = network.lower()
    if normalized in ("ethereum", "sobya"):
        return lambda target: probe_evm(target, opener=opener)
    if normalized == "tron":
        return lambda target: probe_tron(target, opener=opener)
    if normalized == "solana":
        return lambda target: probe_solana(target, opener=opener)
    raise ProbeError("unsupported network probe")
