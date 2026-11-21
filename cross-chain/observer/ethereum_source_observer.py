"""Fail-closed Ethereum source escrow deposit observer.

Uses Ethereum's finalized block tag and verifies the escrow's on-chain order
record/status, not merely an RPC-reported Transfer event.
"""
from __future__ import annotations

from dataclasses import dataclass

from eth_hash.auto import keccak
from settlement_observer import JsonRpc, VerificationError, _address_word, _hex_bytes

ORDER_FUNDED_TOPIC = "0x" + keccak(
    b"OrderFunded(bytes32,address,address,uint256)"
).hex()


def _selector(signature: str) -> str:
    return "0x" + keccak(signature.encode())[:4].hex()


def _word_address(raw: bytes, field: str) -> str:
    if len(raw) != 32 or raw[:12] != bytes(12):
        raise VerificationError(f"{field}: invalid ABI address")
    return "0x" + raw[12:].hex()


def _words(data: str, count: int) -> list[bytes]:
    if not isinstance(data, str) or not data.startswith("0x"):
        raise VerificationError("eth_call returned invalid ABI data")
    raw = bytes.fromhex(data[2:])
    if len(raw) != count * 32:
        raise VerificationError("eth_call returned unexpected ABI length")
    return [raw[i:i + 32] for i in range(0, len(raw), 32)]


def _uint(raw: bytes) -> int:
    return int.from_bytes(raw, "big")


@dataclass(frozen=True)
class ExpectedDeposit:
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
class VerifiedDeposit:
    order_id: str
    transaction_hash: str
    log_index: int
    block_number: int
    source_chain_id: int
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


class EthereumDepositVerifier:
    def __init__(self, rpc: JsonRpc, source_chain_id: int, escrow: str):
        if source_chain_id <= 0:
            raise ValueError("source chain ID must be positive")
        _hex_bytes(escrow, 20, "source escrow")
        self.rpc = rpc
        self.chain_id = source_chain_id
        self.escrow = escrow.lower()

    def verify(self, transaction_hash: str, expected: ExpectedDeposit) -> VerifiedDeposit:
        _hex_bytes(transaction_hash, 32, "transaction hash")
        if int(self.rpc.call("eth_chainId", []), 16) != self.chain_id:
            raise VerificationError("source chain ID mismatch")

        receipt = self.rpc.call("eth_getTransactionReceipt", [transaction_hash])
        if receipt is None:
            raise VerificationError("source transaction receipt not found")
        if int(receipt.get("status", "0x0"), 16) != 1:
            raise VerificationError("source deposit transaction failed")
        if receipt.get("transactionHash", "").lower() != transaction_hash.lower():
            raise VerificationError("source receipt transaction hash mismatch")
        if receipt.get("to", "").lower() != self.escrow:
            raise VerificationError("source receipt target is not configured escrow")

        tx = self.rpc.call("eth_getTransactionByHash", [transaction_hash])
        if tx is None or tx.get("to", "").lower() != self.escrow:
            raise VerificationError("source transaction target is not configured escrow")
        if tx.get("from", "").lower() != expected.user.lower():
            raise VerificationError("source transaction sender does not match order")
        if int(tx.get("value", "0x0"), 16) != 0:
            raise VerificationError("ERC-20 escrow funding must not send native value")

        block_number = int(receipt["blockNumber"], 16)
        finalized = self.rpc.call("eth_getBlockByNumber", ["finalized", False])
        if finalized is None or int(finalized.get("number", "0x0"), 16) < block_number:
            raise VerificationError("source deposit block is not finalized")
        canonical = self.rpc.call("eth_getBlockByNumber", [hex(block_number), False])
        if canonical is None or canonical.get("hash", "").lower() != receipt.get("blockHash", "").lower():
            raise VerificationError("source receipt block is not canonical")

        order_id = _hex_bytes(expected.order_id, 32, "expected order ID")
        token_call = _selector("token()")
        token_data = self.rpc.call("eth_call", [{"to": self.escrow, "data": token_call}, "finalized"])
        escrow_token = _word_address(_words(token_data, 1)[0], "escrow token")
        if escrow_token != expected.token.lower():
            raise VerificationError("configured escrow token does not match expected USDT")

        status_call = _selector("status(bytes32)") + expected.order_id[2:]
        status_data = self.rpc.call("eth_call", [{"to": self.escrow, "data": status_call}, "finalized"])
        if _uint(_words(status_data, 1)[0]) != 1:
            raise VerificationError("escrow order is not in FUNDED state")

        orders_call = _selector("orders(bytes32)") + expected.order_id[2:]
        order_data = self.rpc.call("eth_call", [{"to": self.escrow, "data": orders_call}, "finalized"])
        values = _words(order_data, 10)
        decoded = {
            "order_id": "0x" + values[0].hex(),
            "user": _word_address(values[1], "order user"),
            "token": _word_address(values[2], "order token"),
            "source_amount": _uint(values[3]),
            "solver": _word_address(values[4], "order solver"),
            "destination_chain_id": _uint(values[5]),
            "destination_recipient": _word_address(values[6], "destination recipient"),
            "destination_amount": _uint(values[7]),
            "quote_expiry": _uint(values[8]),
            "refund_after": _uint(values[9]),
        }
        for field, actual in decoded.items():
            wanted = getattr(expected, field)
            if isinstance(wanted, str):
                wanted = wanted.lower()
            if actual != wanted:
                raise VerificationError(f"on-chain escrow order mismatch: {field}")

        recipient_topic = "0x" + ("00" * 12) + expected.user[2:].lower()
        solver_topic = "0x" + ("00" * 12) + expected.solver[2:].lower()
        matching = []
        for log in receipt.get("logs", []):
            topics = log.get("topics", [])
            if log.get("address", "").lower() != self.escrow or len(topics) != 4:
                continue
            if topics[0].lower() != ORDER_FUNDED_TOPIC.lower():
                continue
            if (
                topics[1].lower() == expected.order_id.lower()
                and topics[2].lower() == recipient_topic
                and topics[3].lower() == solver_topic
            ):
                data = _words(log.get("data", ""), 1)
                if _uint(data[0]) != expected.source_amount:
                    raise VerificationError("OrderFunded amount does not match order")
                matching.append(log)
        if len(matching) != 1:
            raise VerificationError("expected exactly one matching OrderFunded event")

        return VerifiedDeposit(
            order_id=expected.order_id.lower(),
            transaction_hash=transaction_hash.lower(),
            log_index=int(matching[0]["logIndex"], 16),
            block_number=block_number,
            source_chain_id=self.chain_id,
            escrow=self.escrow,
            user=expected.user.lower(),
            token=expected.token.lower(),
            amount=expected.source_amount,
            solver=expected.solver.lower(),
            destination_chain_id=expected.destination_chain_id,
            destination_recipient=expected.destination_recipient.lower(),
            destination_amount=expected.destination_amount,
            quote_expiry=expected.quote_expiry,
            refund_after=expected.refund_after,
        )
