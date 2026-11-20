"""Fail-closed TRON source escrow observer using Solidity Node APIs.

TRON's Solidity Node is used for solidified transaction information and
constant calls. Addresses are normalized from either 20-byte EVM form or
21-byte TRON hex form (41 prefix). This is a read-only verifier.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from eth_hash.auto import keccak
from settlement_observer import VerificationError, _hex_bytes

ORDER_FUNDED_TOPIC = "0x" + keccak(b"OrderFunded(bytes32,address,address,uint256)").hex()


def _selector(signature: str) -> str:
    return "0x" + keccak(signature.encode())[:4].hex()


def _address(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise VerificationError(f"{field}: invalid TRON address")
    raw = value[2:] if value.startswith("0x") else value
    try:
        decoded = bytes.fromhex(raw)
    except ValueError as exc:
        raise VerificationError(f"{field}: invalid hex address") from exc
    if len(decoded) == 21 and decoded[0] == 0x41:
        decoded = decoded[1:]
    if len(decoded) != 20:
        raise VerificationError(f"{field}: expected 20-byte address or 41-prefixed TRON address")
    return "0x" + decoded.hex()


def _word_address(raw: bytes, field: str) -> str:
    if len(raw) != 32 or raw[:12] != bytes(12):
        raise VerificationError(f"{field}: invalid ABI address")
    return "0x" + raw[12:].hex()


def _words(value: str, count: int) -> list[bytes]:
    if not isinstance(value, str):
        raise VerificationError("TRON constant-call result is missing")
    value = value[2:] if value.startswith("0x") else value
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise VerificationError("TRON constant-call result is not hex") from exc
    if len(raw) != count * 32:
        raise VerificationError("TRON constant-call result has unexpected ABI length")
    return [raw[i:i + 32] for i in range(0, len(raw), 32)]


@dataclass(frozen=True)
class ExpectedTronDeposit:
    order_id: str
    user: str
    token: str
    source_amount: int
    solver: str
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    quote_expiry: int
    refund_after: int


@dataclass(frozen=True)
class VerifiedTronDeposit:
    order_id: str
    transaction_id: str
    log_index: int
    block_number: int
    escrow: str
    user: str
    token: str
    amount: int
    solver: str
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    quote_expiry: int
    refund_after: int


class TronSolidityRpc:
    """Small injectable HTTP client for TRON Solidity Node endpoints."""

    def __init__(self, base_url: str, timeout: int = 15,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not base_url.startswith("https://"):
            raise ValueError("TRON production RPC must use HTTPS")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport or self._http_transport

    @staticmethod
    def _http_transport(url: str, payload: dict[str, Any], timeout: int) -> Any:
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def call(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.transport(self.base_url + endpoint, payload, self.timeout)
        if not isinstance(result, dict):
            raise VerificationError(f"TRON {endpoint} returned an invalid response")
        if result.get("Error") or result.get("result", {}).get("result") is False:
            raise VerificationError(f"TRON {endpoint} RPC error")
        return result


class TronDepositVerifier:
    """Verifies a TRC-20 escrow deposit using solidified transaction data."""

    def __init__(self, rpc: TronSolidityRpc, escrow: str):
        self.rpc = rpc
        self.escrow = _address(escrow, "escrow")

    def _constant_call(self, selector: str, order_id: str | None = None) -> str:
        data = selector + (order_id[2:] if order_id else "")
        response = self.rpc.call("/walletsolidity/triggerconstantcontract", {
            "owner_address": self.escrow[2:],
            "contract_address": self.escrow[2:],
            "function_selector": "",
            "parameter": "",
            "data": data,
            "visible": False,
        })
        values = response.get("constant_result", [])
        if len(values) != 1:
            raise VerificationError("TRON constant call did not return exactly one result")
        return values[0]

    def verify(self, transaction_id: str, expected: ExpectedTronDeposit) -> VerifiedTronDeposit:
        _hex_bytes("0x" + transaction_id.removeprefix("0x"), 32, "TRON transaction ID")
        txid = transaction_id.removeprefix("0x").lower()

        # Solidity Node only exposes solidified transaction information.
        info = self.rpc.call("/walletsolidity/gettransactioninfobyid", {"value": txid})
        if info.get("id", "").lower() != txid or not info.get("blockNumber"):
            raise VerificationError("TRON transaction is not present in Solidity Node")
        receipt = info.get("receipt", {})
        if receipt.get("result") != "SUCCESS":
            raise VerificationError("TRON source transaction failed")

        tx_response = self.rpc.call("/walletsolidity/gettransactionbyid", {"value": txid})
        raw_contracts = tx_response.get("raw_data", {}).get("contract", [])
        if len(raw_contracts) != 1:
            raise VerificationError("expected one TRON escrow call")
        contract = raw_contracts[0]
        if contract.get("type") != "TriggerSmartContract":
            raise VerificationError("TRON transaction is not a smart-contract call")
        parameter = contract.get("parameter", {}).get("value", {})
        if _address(parameter.get("contract_address", ""), "transaction target") != self.escrow:
            raise VerificationError("TRON transaction target is not configured escrow")
        if _address(parameter.get("owner_address", ""), "transaction sender") != _address(expected.user, "expected user"):
            raise VerificationError("TRON transaction sender does not match order")
        if int(parameter.get("call_value", 0)) != 0:
            raise VerificationError("TRC-20 escrow funding must not send native TRX")

        block_number = int(info["blockNumber"])
        block = self.rpc.call("/walletsolidity/getblockbynum", {"num": block_number})
        block_id = block.get("blockID", "").lower()
        info_block_id = info.get("blockHash", block_id).lower()
        if not block_id or (info_block_id and block_id != info_block_id):
            raise VerificationError("TRON solidified block hash mismatch")

        order_id = "0x" + _hex_bytes(expected.order_id, 32, "expected order ID").hex()
        token_data = self._constant_call(_selector("token()"))
        token = _word_address(_words(token_data, 1)[0], "escrow token")
        if token != _address(expected.token, "expected token"):
            raise VerificationError("configured TRC-20 token does not match expected USDT")

        status_data = self._constant_call(_selector("status(bytes32)"), order_id)
        if int.from_bytes(_words(status_data, 1)[0], "big") != 1:
            raise VerificationError("TRON escrow order is not in FUNDED state")

        order_data = self._constant_call(_selector("orders(bytes32)"), order_id)
        values = _words(order_data, 10)
        decoded = {
            "order_id": "0x" + values[0].hex(),
            "user": _word_address(values[1], "order user"),
            "token": _word_address(values[2], "order token"),
            "source_amount": int.from_bytes(values[3], "big"),
            "solver": _word_address(values[4], "order solver"),
            "destination_chain_id": int.from_bytes(values[5], "big"),
            "destination_recipient": _word_address(values[6], "destination recipient"),
            "destination_amount": int.from_bytes(values[7], "big"),
            "quote_expiry": int.from_bytes(values[8], "big"),
            "refund_after": int.from_bytes(values[9], "big"),
        }
        for field, actual in decoded.items():
            wanted = getattr(expected, field)
            if isinstance(wanted, str):
                wanted = wanted.lower()
            if actual != wanted:
                raise VerificationError(f"TRON on-chain escrow order mismatch: {field}")

        matches = []
        for log in info.get("log", []):
            if _address(log.get("address", ""), "event address") != self.escrow:
                continue
            topics = log.get("topics", [])
            if len(topics) != 4 or topics[0].lower() != ORDER_FUNDED_TOPIC.lower():
                continue
            if (
                topics[1].lower() != order_id
                or _word_address(bytes.fromhex(topics[2]), "event user") != _address(expected.user, "expected user")
                or _word_address(bytes.fromhex(topics[3]), "event solver") != _address(expected.solver, "expected solver")
            ):
                continue
            data = _words(log.get("data", ""), 1)
            if int.from_bytes(data[0], "big") != expected.source_amount:
                raise VerificationError("TRON OrderFunded amount does not match order")
            matches.append(log)
        if len(matches) != 1:
            raise VerificationError("expected exactly one matching TRON OrderFunded event")

        return VerifiedTronDeposit(
            order_id=order_id, transaction_id=txid,
            log_index=int(matches[0].get("logIndex", 0)), block_number=block_number,
            escrow=self.escrow, user=_address(expected.user, "expected user"),
            token=token, amount=expected.source_amount,
            solver=_address(expected.solver, "expected solver"),
            destination_chain_id=expected.destination_chain_id,
            destination_recipient=_address(expected.destination_recipient, "destination recipient"),
            destination_amount=expected.destination_amount,
            quote_expiry=expected.quote_expiry, refund_after=expected.refund_after,
        )
