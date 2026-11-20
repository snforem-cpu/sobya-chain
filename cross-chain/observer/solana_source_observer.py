"""Fail-closed read-only observer for native Solana SPL-USDT escrow deposits.

The observer checks finalized transaction status, the invoked escrow program,
the exact Fund account set, Borsh order PDA account contents, and the legacy
SPL Token escrow account state. It does not sign or submit transactions.
"""
from __future__ import annotations

import base64
import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from settlement_observer import VerificationError


ORDER_DATA_LEN = 256
FUNDED_STATUS = 0
LEGACY_SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@dataclass(frozen=True)
class ExpectedSolanaDeposit:
    signature: str
    program_id: str
    order_pda: str
    config_pda: str
    user: str
    solver: str
    escrow_token_account: str
    usdt_mint: str
    source_amount: int
    order_id: bytes
    destination_recipient: bytes
    destination_amount: int
    quote_expiry: int
    refund_after: int


@dataclass(frozen=True)
class VerifiedSolanaDeposit:
    signature: str
    slot: int
    order_pda: str
    config_pda: str
    user: str
    solver: str
    escrow_token_account: str
    usdt_mint: str
    source_amount: int
    order_id: bytes
    destination_recipient: bytes
    destination_amount: int
    quote_expiry: int
    refund_after: int


class SolanaRpc:
    def __init__(self, url: str, timeout: int = 20,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not url.startswith("https://"):
            raise ValueError("Solana production RPC must use HTTPS")
        self.url, self.timeout = url, timeout
        self.transport = transport or self._http_transport
        self._next_id = 1

    @staticmethod
    def _http_transport(url: str, payload: dict[str, Any], timeout: int) -> Any:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def call(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        self._next_id += 1
        response = self.transport(self.url, payload, self.timeout)
        if not isinstance(response, dict) or response.get("id") != payload["id"]:
            raise VerificationError("invalid Solana JSON-RPC response envelope")
        if response.get("error") or "result" not in response:
            raise VerificationError(f"Solana RPC {method} failed")
        return response["result"]


def _decode_order(data_b64: str) -> dict[str, Any]:
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception as exc:
        raise VerificationError("order PDA data is not valid base64") from exc
    if len(raw) != ORDER_DATA_LEN:
        raise VerificationError("order PDA has unexpected Borsh data length")
    p = 0
    def take(n: int) -> bytes:
        nonlocal p
        out = raw[p:p+n]
        p += n
        return out
    return {
        "order_id": take(32),
        "user": take(32),
        "solver": take(32),
        "config": take(32),
        "escrow_token_account": take(32),
        "destination_recipient": take(20),
        "destination_amount": int.from_bytes(take(16), "little"),
        "source_amount": int.from_bytes(take(8), "little"),
        "quote_expiry": int.from_bytes(take(8), "little"),
        "refund_after": int.from_bytes(take(8), "little"),
        "destination_tx_hash": take(32),
        "attested_bitmap": int.from_bytes(take(2), "little"),
        "status": take(1)[0],
        "bump": take(1)[0],
    }


class SolanaDepositVerifier:
    def __init__(self, rpc: SolanaRpc):
        self.rpc = rpc

    def verify(self, expected: ExpectedSolanaDeposit) -> VerifiedSolanaDeposit:
        if len(expected.order_id) != 32 or len(expected.destination_recipient) != 20:
            raise ValueError("order ID and destination recipient must be 32 and 20 bytes")
        tx = self.rpc.call("getTransaction", [expected.signature, {
            "encoding": "json", "commitment": "finalized", "maxSupportedTransactionVersion": 0,
        }])
        if tx is None:
            raise VerificationError("Solana deposit transaction is not finalized or not found")
        meta = tx.get("meta") or {}
        if meta.get("err") is not None:
            raise VerificationError("Solana source deposit transaction failed")
        slot = tx.get("slot")
        if not isinstance(slot, int) or slot <= 0:
            raise VerificationError("Solana transaction has invalid finalized slot")

        message = tx.get("transaction", {}).get("message", {})
        keys = message.get("accountKeys", [])
        pubkeys = [k.get("pubkey") if isinstance(k, dict) else k for k in keys]
        signers = {
            (k.get("pubkey") if isinstance(k, dict) else k)
            for k in keys if isinstance(k, dict) and k.get("signer")
        }
        if tx.get("transaction", {}).get("signatures", [None])[0] != expected.signature:
            raise VerificationError("Solana transaction signature does not match request")
        if not signers:
            # json encoding may return string keys; signer flags are then in header.
            header = message.get("header", {})
            required = header.get("numRequiredSignatures", 0)
            signers = set(pubkeys[:required])
        for signer in (expected.user, expected.solver):
            if signer not in signers:
                raise VerificationError("user and solver must both sign the Solana fund transaction")

        instructions = message.get("instructions", [])
        fund_calls = []
        for ix in instructions:
            program_index = ix.get("programIdIndex")
            if not isinstance(program_index, int) or program_index >= len(pubkeys):
                continue
            if pubkeys[program_index] == expected.program_id:
                accounts = [pubkeys[i] for i in ix.get("accounts", []) if isinstance(i, int) and i < len(pubkeys)]
                if expected.order_pda in accounts:
                    raw_instruction = _b58decode(ix.get("data", ""))
                    if len(raw_instruction) != 1 + 32 + 20 + 16 + 8 + 8 + 8 or raw_instruction[0] != 1:
                        raise VerificationError("Solana instruction is not a canonical Fund instruction")
                    p = 1
                    fields = [raw_instruction[p:p+32]]; p += 32
                    fields.append(raw_instruction[p:p+20]); p += 20
                    fields.append(int.from_bytes(raw_instruction[p:p+16], "little")); p += 16
                    fields.append(int.from_bytes(raw_instruction[p:p+8], "little")); p += 8
                    fields.append(int.from_bytes(raw_instruction[p:p+8], "little")); p += 8
                    fields.append(int.from_bytes(raw_instruction[p:p+8], "little"))
                    wanted_instruction = [expected.order_id, expected.destination_recipient,
                        expected.destination_amount, expected.source_amount,
                        expected.quote_expiry, expected.refund_after]
                    if fields != wanted_instruction:
                        raise VerificationError("Solana Fund instruction data does not match expected quote")
                    fund_calls.append(accounts)
        if len(fund_calls) != 1:
            raise VerificationError("expected exactly one escrow-program instruction for this order PDA")
        accounts = fund_calls[0]
        required_accounts = [expected.user, expected.solver, expected.config_pda,
            expected.order_pda, expected.escrow_token_account]
        if any(key not in accounts for key in required_accounts):
            raise VerificationError("Solana fund instruction account set does not match expected order")

        order_info = self.rpc.call("getAccountInfo", [expected.order_pda, {
            "encoding": "base64", "commitment": "finalized",
        }]).get("value")
        if not order_info or order_info.get("owner") != expected.program_id:
            raise VerificationError("order PDA is missing or not owned by configured escrow program")
        decoded = _decode_order(order_info.get("data", [""])[0])
        wanted = {
            "order_id": expected.order_id,
            "user": _pubkey_bytes(expected.user),
            "solver": _pubkey_bytes(expected.solver),
            "config": _pubkey_bytes(expected.config_pda),
            "escrow_token_account": _pubkey_bytes(expected.escrow_token_account),
            "destination_recipient": expected.destination_recipient,
            "destination_amount": expected.destination_amount,
            "source_amount": expected.source_amount,
            "quote_expiry": expected.quote_expiry,
            "refund_after": expected.refund_after,
            "status": FUNDED_STATUS,
        }
        for field, value in wanted.items():
            if decoded[field] != value:
                raise VerificationError(f"Solana on-chain order mismatch: {field}")

        token_info = self.rpc.call("getAccountInfo", [expected.escrow_token_account, {
            "encoding": "jsonParsed", "commitment": "finalized",
        }]).get("value")
        if not token_info or token_info.get("owner") != LEGACY_SPL_TOKEN_PROGRAM:
            raise VerificationError("escrow account is not owned by the legacy SPL Token program")
        parsed = token_info.get("data", {}).get("parsed", {}).get("info", {})
        token_amount = parsed.get("tokenAmount", {}).get("amount")
        if parsed.get("mint") != expected.usdt_mint or parsed.get("owner") != expected.order_pda:
            raise VerificationError("Solana escrow token account mint or authority mismatch")
        if str(token_amount) != str(expected.source_amount):
            raise VerificationError("Solana escrow token balance does not equal funded amount")

        return VerifiedSolanaDeposit(
            signature=expected.signature, slot=slot, order_pda=expected.order_pda,
            config_pda=expected.config_pda, user=expected.user, solver=expected.solver,
            escrow_token_account=expected.escrow_token_account, usdt_mint=expected.usdt_mint,
            source_amount=expected.source_amount, order_id=expected.order_id,
            destination_recipient=expected.destination_recipient,
            destination_amount=expected.destination_amount,
            quote_expiry=expected.quote_expiry, refund_after=expected.refund_after,
        )


def _pubkey_bytes(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    try:
        for char in value:
            number = number * 58 + alphabet.index(char)
    except ValueError as exc:
        raise VerificationError("invalid base58 Solana public key") from exc
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading = len(value) - len(value.lstrip("1"))
    raw = bytes(leading) + decoded
    if len(raw) != 32:
        raise VerificationError("Solana public key must decode to 32 bytes")
    return raw

def _b58decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    try:
        for char in value:
            number = number * 58 + alphabet.index(char)
    except ValueError as exc:
        raise VerificationError("invalid base58 instruction data") from exc
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return bytes(len(value) - len(value.lstrip("1"))) + decoded
