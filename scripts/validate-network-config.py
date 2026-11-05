#!/usr/bin/env python3
"""Validate an operator's SOBYA CometBFT and Cosmos EVM network configuration."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(Exception):
    pass


def fail(message: str) -> None:
    raise ConfigError(message)


def parse_host_port(value: str, label: str) -> tuple[str, int]:
    value = value.strip()
    if value.startswith("["):
        match = re.fullmatch(r"\[([^]]+)\]:(\d+)", value)
        if not match:
            fail(f"{label}: invalid host:port {value!r}")
        host, port_text = match.groups()
    else:
        if value.count(":") != 1:
            fail(f"{label}: expected hostname:port (IPv6 must be bracketed), got {value!r}")
        host, port_text = value.rsplit(":", 1)
    if not host or host.lower() in {"localhost", "example.com", "example.org"}:
        fail(f"{label}: host must be a real externally reachable host, got {host!r}")
    try:
        port = int(port_text)
    except ValueError:
        fail(f"{label}: invalid TCP port {port_text!r}")
    if not 1 <= port <= 65535:
        fail(f"{label}: TCP port out of range: {port}")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            fail(f"{label}: address {host!r} is not globally routable")
    except ValueError:
        if "." not in host or any(x in host.lower() for x in ("<", ">", "your-", "replace-me", "placeholder")):
            fail(f"{label}: use a real public DNS name or global IP, got {host!r}")
    return host, port


def parse_peer_list(raw: str, label: str) -> list[tuple[str, str, int]]:
    peers = []
    if not raw.strip():
        return peers
    for entry in raw.split(","):
        entry = entry.strip()
        if "@" not in entry:
            fail(f"{label}: peer must use node-id@host:port, got {entry!r}")
        node_id, address = entry.split("@", 1)
        if not re.fullmatch(r"[0-9a-fA-F]{40}", node_id):
            fail(f"{label}: CometBFT node ID must be 40 hex characters, got {node_id!r}")
        host, port = parse_host_port(address, label)
        peers.append((node_id.lower(), host, port))
    if len({p[0] for p in peers}) != len(peers):
        fail(f"{label}: duplicate peer node IDs")
    return peers


def is_loopback_listener(value: str, label: str) -> None:
    if "://" not in value:
        value = "tcp://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in {"tcp", "http"} or not parsed.hostname or not parsed.port:
        fail(f"{label}: expected host:port, tcp://host:port, or http://host:port, got {value!r}")
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname.lower() == "localhost"
    if not loopback:
        fail(f"{label}: must bind to loopback behind a hardened TLS reverse proxy, got {value!r}")


def validate(config_path: Path, app_path: Path, genesis_path: Path, chain_id: str, evm_chain_id: int, role: str) -> list[str]:
    with config_path.open("rb") as stream:
        comet = tomllib.load(stream)
    with app_path.open("rb") as stream:
        app = tomllib.load(stream)
    with genesis_path.open(encoding="utf-8") as stream:
        genesis = json.load(stream)

    if not chain_id or genesis.get("chain_id") != chain_id:
        fail(f"genesis chain_id {genesis.get('chain_id')!r} does not match expected {chain_id!r}")
    if not isinstance(genesis.get("app_state"), dict) or "evm" not in genesis["app_state"]:
        fail("genesis app_state is missing the evm module")

    p2p = comet.get("p2p", {})
    laddr = p2p.get("laddr", "")
    parsed_laddr = urlsplit(laddr)
    if parsed_laddr.scheme != "tcp" or parsed_laddr.hostname not in {"0.0.0.0", "::"} or not parsed_laddr.port:
        fail(f"[p2p].laddr must listen on tcp://0.0.0.0:<port> (or [::]), got {laddr!r}")
    if not p2p.get("external_address"):
        fail("[p2p].external_address is empty; publish the node's real public P2P address")
    ext_host, ext_port = parse_host_port(p2p["external_address"], "[p2p].external_address")
    # A provider may map a public TCP port to a different local listener port.
    # The operator must verify that mapping from an independent network.
    peers = parse_peer_list(p2p.get("persistent_peers", ""), "[p2p].persistent_peers")
    seeds = parse_peer_list(p2p.get("seeds", ""), "[p2p].seeds")
    if not peers and not seeds and role != "seed":
        fail("configure at least one real persistent peer or seed; only the initial seed node may bootstrap without upstream peers")

    rpc = comet.get("rpc", {})
    is_loopback_listener(rpc.get("laddr", ""), "[rpc].laddr")
    if rpc.get("unsafe", True):
        fail("[rpc].unsafe must be false")

    evm = app.get("evm", {})
    actual_evm_id = evm.get("evm-chain-id")
    if actual_evm_id != evm_chain_id or evm_chain_id <= 0:
        fail(f"[evm].evm-chain-id {actual_evm_id!r} does not match expected {evm_chain_id}")
    if evm_chain_id in {777777, 777778}:
        fail(f"{evm_chain_id} is reserved for SOBYA development/CI and cannot be used for a public network")

    if role not in {"validator", "seed", "rpc"}:
        fail(f"unknown node role {role!r}")
    json_rpc = app.get("json-rpc", {})
    rpc_enabled = bool(json_rpc.get("enable", False))
    if role == "rpc" and not rpc_enabled:
        fail("[json-rpc].enable must be true on the designated RPC node")
    if role in {"validator", "seed"} and rpc_enabled:
        fail(f"[json-rpc].enable must remain false on a {role} node")
    is_loopback_listener("tcp://" + json_rpc.get("address", ""), "[json-rpc].address")
    is_loopback_listener("tcp://" + json_rpc.get("ws-address", ""), "[json-rpc].ws-address")
    if json_rpc.get("allow-insecure-unlock", True):
        fail("[json-rpc].allow-insecure-unlock must be false")
    if json_rpc.get("enable-profiling", True):
        fail("[json-rpc].enable-profiling must be false")
    if json_rpc.get("max-open-connections", 0) <= 0:
        fail("[json-rpc].max-open-connections must be a finite positive limit")
    namespaces = set(json_rpc.get("api", []))
    if rpc_enabled:
        if not {"eth", "net", "web3"}.issubset(namespaces):
            fail("[json-rpc].api must include eth, net, and web3")
        if namespaces.intersection({"personal", "debug", "miner"}):
            fail("public JSON-RPC must not expose personal, debug, or miner namespaces")
    origins = json_rpc.get("ws-origins", [])
    if not origins or "*" in origins:
        fail("[json-rpc].ws-origins must be explicitly restricted; wildcard origins are forbidden")

    api = app.get("api", {})
    if api.get("enable", False):
        is_loopback_listener(api.get("address", ""), "[api].address")
    grpc = app.get("grpc", {})
    if grpc.get("enable", False):
        is_loopback_listener(grpc.get("address", ""), "[grpc].address")

    return [
        f"PASS chain ID: {chain_id}",
        f"PASS EVM chain ID: {evm_chain_id}",
        f"PASS public P2P listener: {laddr}",
        f"PASS advertised P2P endpoint: {ext_host}:{ext_port}",
        f"PASS configured peers/seeds: {len(peers)} persistent, {len(seeds)} seeds",
        "PASS CometBFT RPC is loopback-only and unsafe RPC is disabled",
        f"PASS node role: {role}",
        "PASS EVM JSON-RPC exposure matches node role and has no insecure unlock",
        "NOTE This validates local configuration only; it does not prove Internet reachability or consensus.",
    ]


def self_test() -> None:
    import tempfile

    config = """[p2p]
laddr = "tcp://0.0.0.0:26656"
external_address = "seed1.sobya.network:26656"
persistent_peers = "0123456789abcdef0123456789abcdef01234567@seed1.sobya.network:26656"
seeds = ""

[rpc]
laddr = "tcp://127.0.0.1:26657"
unsafe = false
"""
    app = """[evm]
evm-chain-id = 42424242

[json-rpc]
enable = true
api = ["eth", "net", "web3"]
address = "127.0.0.1:8545"
ws-address = "127.0.0.1:8546"
allow-insecure-unlock = false
enable-profiling = false
max-open-connections = 100
ws-origins = ["127.0.0.1", "localhost"]

[api]
enable = false

[grpc]
enable = false
"""
    genesis = {"chain_id": "sobya-testnet-stage2", "app_state": {"evm": {}}}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config.toml").write_text(config, encoding="utf-8")
        (root / "app.toml").write_text(app, encoding="utf-8")
        (root / "genesis.json").write_text(json.dumps(genesis), encoding="utf-8")
        validate(root / "config.toml", root / "app.toml", root / "genesis.json", "sobya-testnet-stage2", 42424242, "rpc")
        validator_app = app.replace("enable = true", "enable = false", 1)
        (root / "app.toml").write_text(validator_app, encoding="utf-8")
        validate(root / "config.toml", root / "app.toml", root / "genesis.json", "sobya-testnet-stage2", 777778, "validator")
        bad_app = app.replace("allow-insecure-unlock = false", "allow-insecure-unlock = true")
        (root / "app.toml").write_text(bad_app, encoding="utf-8")
        try:
            validate(root / "config.toml", root / "app.toml", root / "genesis.json", "sobya-testnet-stage2", 777778, "rpc")
        except ConfigError:
            pass
        else:
            fail("self-test did not reject insecure account unlocking")
    print("PASS network config validator self-test (valid config accepted; insecure unlock rejected)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="CometBFT config.toml")
    parser.add_argument("--app-config", type=Path, help="Cosmos SDK/Cosmos EVM app.toml")
    parser.add_argument("--genesis", type=Path, help="the exact genesis.json used by this node")
    parser.add_argument("--chain-id", help="expected CometBFT chain ID from the signed launch bundle")
    parser.add_argument("--evm-chain-id", type=int, help="expected EVM chain ID from the signed launch bundle")
    parser.add_argument("--role", choices=("validator", "seed", "rpc"), default="validator", help="node role; validator/seed nodes keep EVM JSON-RPC disabled")
    parser.add_argument("--self-test", action="store_true", help="run built-in positive and negative tests")
    args = parser.parse_args()

    try:
        if args.self_test:
            self_test()
            return 0
        required = [args.config, args.app_config, args.genesis, args.chain_id, args.evm_chain_id]
        if any(value is None for value in required):
            parser.error("provide --config, --app-config, --genesis, --chain-id, and --evm-chain-id (or use --self-test)")
        for line in validate(args.config, args.app_config, args.genesis, args.chain_id, args.evm_chain_id, args.role):
            print(line)
        return 0
    except (ConfigError, OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
