"""Read-only verifier for SOBYA native-SOBY payout receipts.

This module queries an EVM JSON-RPC endpoint and validates a finalized
PayoutExecuted event against a separately obtained signed source-order record.
It does not sign attestations, submit transactions, or trust API order state.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from eth_hash.auto import keccak

EVENT_SIGNATURE = "PayoutExecuted(bytes32,bytes32,bytes32,bytes32,uint256,address,uint256,address,uint256)"
EVENT_TOPIC = "0x" + keccak(EVENT_SIGNATURE.encode()).hex()


class VerificationError(ValueError):
    """Raised when a payout receipt cannot be independently verified."""


@dataclass(frozen=True)
class ExpectedPayout:
    order_id: str
    source_chain: str
    source_escrow: str
    source_asset: str
    source_amount: int
    recipient: str
    soby_amount: int
    destination_solver: str


@dataclass(frozen=True)
class VerifiedPayout:
    order_id: str
    transaction_hash: str
    log_index: int
    block_number: int
    destination_chain_id: int
    source_chain: str
    source_escrow: str
    source_asset: str
    source_amount: int
    recipient: str
    soby_amount: int
    solver: str


def _hex_bytes(value: str, length: int, field: str) -> bytes:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise VerificationError(f"{field}: expected 0x-prefixed hex")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise VerificationError(f"{field}: invalid hex") from exc
    if len(raw) != length:
        raise VerificationError(f"{field}: expected {length} bytes")
    return raw


def _address_word(value: str, field: str) -> str:
    raw = _hex_bytes(value, 32, field)
    if raw[:12] != bytes(12):
        raise VerificationError(f"{field}: non-canonical ABI address")
    return "0x" + raw[12:].hex()


def _data_words(value: str, count: int) -> list[bytes]:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise VerificationError("log data: expected 0x-prefixed hex")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise VerificationError("log data: invalid hex") from exc
    if len(raw) != count * 32:
        raise VerificationError(f"log data: expected {count} ABI words")
    return [raw[i:i + 32] for i in range(0, len(raw), 32)]


class JsonRpc:
    """Minimal JSON-RPC client; transport is injectable for deterministic tests."""

    def __init__(self, url: str, timeout: int = 15,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not url.startswith(("https://", "http://")):
            raise ValueError("RPC URL must use HTTP(S)")
        self.url = url
        self.timeout = timeout
        self.transport = transport or self._http_transport
        self._next_id = 1

    @staticmethod
    def _http_transport(url: str, payload: dict[str, Any], timeout: int) -> Any:
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def call(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": self._next_id,
                   "method": method, "params": params}
        self._next_id += 1
        response = self.transport(self.url, payload, self.timeout)
        if not isinstance(response, dict) or response.get("id") != payload["id"]:
            raise VerificationError("invalid JSON-RPC response envelope")
        if response.get("error"):
            raise VerificationError(f"RPC {method} failed: {response['error']}")
        if "result" not in response:
            raise VerificationError(f"RPC {method} missing result")
        return response["result"]


class SettlementVerifier:
    def __init__(self, rpc: JsonRpc, expected_chain_id: int,
                 settlement_contract: str, confirmations: int):
        if expected_chain_id <= 0 or confirmations < 1:
            raise ValueError("chain ID and confirmation threshold must be positive")
        self.rpc = rpc
        self.expected_chain_id = expected_chain_id
        self.contract = settlement_contract.lower()
        _hex_bytes(settlement_contract, 20, "settlement contract")
        self.confirmations = confirmations

    def verify(self, transaction_hash: str, expected: ExpectedPayout) -> VerifiedPayout:
        _hex_bytes(transaction_hash, 32, "transaction hash")
        if int(self.rpc.call("eth_chainId", []), 16) != self.expected_chain_id:
            raise VerificationError("destination chain ID mismatch")

        receipt = self.rpc.call("eth_getTransactionReceipt", [transaction_hash])
        if receipt is None:
            raise VerificationError("transaction receipt not found")
        if int(receipt.get("status", "0x0"), 16) != 1:
            raise VerificationError("destination transaction failed")
        if receipt.get("transactionHash", "").lower() != transaction_hash.lower():
            raise VerificationError("receipt transaction hash mismatch")

        if receipt.get("to", "").lower() != self.contract:
            raise VerificationError("receipt target is not settlement contract")
        transaction = self.rpc.call("eth_getTransactionByHash", [transaction_hash])
        if transaction is None:
            raise VerificationError("destination transaction not found")
        if transaction.get("to", "").lower() != self.contract:
            raise VerificationError("transaction target is not settlement contract")
        if int(transaction.get("value", "0x0"), 16) <= 0:
            raise VerificationError("transaction did not transfer native SOBY")

        block_number = int(receipt["blockNumber"], 16)
        canonical_block = self.rpc.call("eth_getBlockByNumber", [hex(block_number), False])
        if canonical_block is None or canonical_block.get("hash", "").lower() != receipt.get("blockHash", "").lower():
            raise VerificationError("receipt block is not canonical (possible reorg)")
        # A confirmation count is not finality. Require the chain's finalized
        # checkpoint to cover this receipt, then retain the configured depth as
        # an additional conservative policy check.
        finalized_block = self.rpc.call("eth_getBlockByNumber", ["finalized", False])
        if not isinstance(finalized_block, dict):
            raise VerificationError("destination finalized checkpoint is unavailable")
        try:
            finalized_number = int(finalized_block["number"], 16)
        except (KeyError, TypeError, ValueError) as exc:
            raise VerificationError("destination finalized checkpoint is malformed") from exc
        if finalized_number < block_number:
            raise VerificationError("destination payout is not finalized")

        latest = int(self.rpc.call("eth_blockNumber", []), 16)
        if latest < block_number or latest - block_number + 1 < self.confirmations:
            raise VerificationError("destination payout has insufficient confirmations")

        expected_order = _hex_bytes(expected.order_id, 32, "expected order ID")
        expected_chain = _hex_bytes(expected.source_chain, 32, "expected source chain")
        expected_escrow = _hex_bytes(expected.source_escrow, 32, "expected source escrow")
        expected_asset = _hex_bytes(expected.source_asset, 32, "expected source asset")
        recipient_bytes = _hex_bytes("0x" + "00" * 12 + expected.recipient[2:], 32, "expected recipient")
        expected_recipient = "0x" + recipient_bytes[12:].hex()
        expected_solver = expected.destination_solver.lower()

        matches = []
        for log in receipt.get("logs", []):
            if log.get("address", "").lower() != self.contract:
                continue
            topics = log.get("topics", [])
            if len(topics) != 4 or topics[0].lower() != EVENT_TOPIC.lower():
                continue
            if _hex_bytes(topics[1], 32, "order topic") != expected_order:
                continue
            if _hex_bytes(topics[2], 32, "source chain topic") != expected_chain:
                continue
            if _address_word(topics[3], "recipient topic") != expected_recipient:
                continue

            words = _data_words(log.get("data", ""), 6)
            source_amount = int.from_bytes(words[2], "big")
            soby_amount = int.from_bytes(words[3], "big")
            solver = "0x" + words[4][12:].hex()
            destination_chain_id = int.from_bytes(words[5], "big")
            if (
                words[0] != expected_escrow or words[1] != expected_asset
                or source_amount != expected.source_amount
                or soby_amount != expected.soby_amount
                or solver != expected_solver
                or destination_chain_id != self.expected_chain_id
                or int(transaction.get("value", "0x0"), 16) != expected.soby_amount
                or transaction.get("from", "").lower() != expected_solver
            ):
                raise VerificationError("payout event/transaction does not match signed source order")
            matches.append(log)

        if len(matches) != 1:
            raise VerificationError("expected exactly one matching payout event")
        log = matches[0]
        return VerifiedPayout(
            order_id=expected.order_id.lower(),
            transaction_hash=transaction_hash.lower(),
            log_index=int(log["logIndex"], 16),
            block_number=block_number,
            destination_chain_id=self.expected_chain_id,
            source_chain=expected.source_chain.lower(),
            source_escrow=expected.source_escrow.lower(),
            source_asset=expected.source_asset.lower(),
            source_amount=expected.source_amount,
            recipient=expected_recipient,
            soby_amount=expected.soby_amount,
            solver=expected_solver,
        )


class ObservationStore:
    """SQLite idempotency guard; not the authoritative order database."""

    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS verified_payouts (
                order_id TEXT PRIMARY KEY,
                transaction_hash TEXT NOT NULL,
                log_index INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                destination_chain_id INTEGER NOT NULL,
                UNIQUE(transaction_hash, log_index)
            )
        """)
        self.db.commit()

    def record(self, payout: VerifiedPayout) -> None:
        try:
            self.db.execute(
                "INSERT INTO verified_payouts VALUES (?, ?, ?, ?, ?)",
                (payout.order_id, payout.transaction_hash, payout.log_index,
                 payout.block_number, payout.destination_chain_id),
            )
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise VerificationError("payout/order already recorded") from exc

    def close(self) -> None:
        self.db.close()
