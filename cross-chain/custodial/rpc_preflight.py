"""Read-only RPC preflight for the disabled Enzonic custodial deployment.

No wallet is unlocked, no key is read, and no transaction is signed or sent.
Failures are diagnostic only while all live feature gates remain disabled.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

DEFAULTS = {
    "ethereum": "https://ethereum-rpc.publicnode.com",
    "sobya": "https://sobya-evm-rpc.nodesafe-app.xyz",
}
SOBYA_FALLBACKS = ("https://sobya-rpc.bonynode.online",)
EXPECTED = {
    "ethereum": 1,
    "sobya": 357812033857,
}
USDT_ETH = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
SOBYA_INVENTORY = "0xebdb899fFE84a89e1d576964b640491c135651AD"


class RpcPreflightError(RuntimeError):
    pass


def _rpc(url: str, method: str, params: list[Any]) -> Any:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read())
    except Exception as exc:
        # Keep diagnostics useful without printing the endpoint (which may
        # contain credentials in operator-provided URLs).
        if isinstance(exc, urllib.error.HTTPError):
            detail = f"HTTP {exc.code}"
        elif isinstance(exc, urllib.error.URLError):
            reason = getattr(exc, "reason", "connection error")
            detail = f"{type(reason).__name__}: {reason}"
        else:
            detail = f"{type(exc).__name__}: {exc}"
        detail = " ".join(str(detail).split())[:180]
        raise RpcPreflightError(f"{method}: network request failed ({detail})") from exc
    if not isinstance(body, dict) or body.get("id") != 1 or body.get("error") or "result" not in body:
        raise RpcPreflightError(f"{method}: invalid JSON-RPC response")
    return body["result"]


def _hex_int(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise RpcPreflightError(f"{label}: malformed hex quantity")
    try:
        return int(value, 16)
    except ValueError as exc:
        raise RpcPreflightError(f"{label}: malformed hex quantity") from exc


def check_network(name: str, url: str | None = None) -> dict[str, Any]:
    if name not in EXPECTED:
        raise ValueError("only Ethereum and SOBYA are supported")
    endpoint = url or os.environ.get(
        "SOBYA_ETHEREUM_RPC_URL" if name == "ethereum" else "SOBYA_SOBYA_RPC_URL",
        DEFAULTS[name],
    )
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise RpcPreflightError("RPC endpoint must use HTTPS")

    chain_id = _hex_int(_rpc(endpoint, "eth_chainId", []), "chain ID")
    if chain_id != EXPECTED[name]:
        raise RpcPreflightError(f"wrong chain ID: expected {EXPECTED[name]}, received {chain_id}")

    latest = _rpc(endpoint, "eth_getBlockByNumber", ["latest", False])
    finalized = _rpc(endpoint, "eth_getBlockByNumber", ["finalized", False])
    if not isinstance(latest, dict) or not isinstance(finalized, dict):
        raise RpcPreflightError("RPC did not return latest and finalized blocks")
    latest_height = _hex_int(latest.get("number"), "latest block")
    finalized_height = _hex_int(finalized.get("number"), "finalized block")
    if finalized_height > latest_height:
        raise RpcPreflightError("finalized block is ahead of latest block")

    result: dict[str, Any] = {
        "network": name, "chain_id": chain_id,
        "latest_block": latest_height, "finalized_block": finalized_height,
    }
    if name == "ethereum":
        code = _rpc(endpoint, "eth_getCode", [USDT_ETH, "finalized"])
        if not isinstance(code, str) or code in ("0x", "0x0"):
            raise RpcPreflightError("pinned Ethereum USDT contract has no code at finalized block")
        result["usdt_contract_code"] = "present"
    else:
        balance = _hex_int(
            _rpc(endpoint, "eth_getBalance", [SOBYA_INVENTORY, "finalized"]),
            "SOBYA inventory balance",
        )
        result["inventory_wallet"] = SOBYA_INVENTORY
        result["inventory_balance_wei"] = balance
    return result


def run_preflight() -> list[dict[str, Any]]:
    results = []
    for name in ("ethereum", "sobya"):
        primary_env = "SOBYA_ETHEREUM_RPC_URL" if name == "ethereum" else "SOBYA_SOBYA_RPC_URL"
        candidates = [os.environ.get(primary_env, DEFAULTS[name])]
        if name == "sobya":
            fallback = os.environ.get("SOBYA_SOBYA_RPC_FALLBACK_URL")
            candidates.extend([fallback] if fallback else list(SOBYA_FALLBACKS))
        last_error = None
        for index, endpoint in enumerate(candidates):
            try:
                result = check_network(name, endpoint)
                if index:
                    print(f"RPC PREFLIGHT INFO: {name} using fallback endpoint #{index + 1}.")
                print(
                    f"RPC PREFLIGHT OK: {name} chain_id={result['chain_id']} "
                    f"latest={result['latest_block']} finalized={result['finalized_block']}"
                )
                if name == "ethereum":
                    print("RPC PREFLIGHT OK: Ethereum USDT contract code is present.")
                else:
                    print(f"RPC PREFLIGHT OK: SOBYA inventory balance={result['inventory_balance_wei']} wei.")
                results.append({"network": name, "ok": True, **result})
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(
                    f"RPC PREFLIGHT ATTEMPT FAILED: {name} endpoint #{index + 1}: "
                    f"{type(exc).__name__}: {exc}"
                )
        if last_error is not None:
            print(f"RPC PREFLIGHT FAILED: {name}: all configured endpoints failed.")
            results.append({"network": name, "ok": False, "error": str(last_error)})
    return results

if __name__ == "__main__":
    run_preflight()
