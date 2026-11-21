"""Local SOBYA EVM vault transaction adapter.

Builds and broadcasts a narrowly scoped reserve() transaction through a
caller-supplied local signer, then waits for canonical finalized inclusion and
reads the reservation back from the pinned vault contract. The signer is
injected; this module never loads or stores private keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from eth_hash.auto import keccak
from order_ledger import OrderQuote
class VaultConnectorError(RuntimeError):
    """Raised when the pinned SOBYA vault cannot be safely reserved."""


VerificationError = VaultConnectorError


def _selector(signature: str) -> str:
    return "0x" + keccak(signature.encode())[:4].hex()


def _word_uint(value: int, bits: int, field: str) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= 1 << bits:
        raise ValueError(f"{field} is outside uint{bits}")
    return value.to_bytes(32, "big").hex()


def _word_address(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise ValueError(f"{field} must be a 20-byte 0x address")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise ValueError(f"{field} is not valid hex") from exc
    if len(raw) != 20 or raw == bytes(20):
        raise ValueError(f"{field} is invalid")
    return (bytes(12) + raw).hex()


def _word_bytes32(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 66 or not value.startswith("0x"):
        raise ValueError(f"{field} must be 32-byte 0x hex")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise ValueError(f"{field} is not valid hex") from exc
    if len(raw) != 32 or raw == bytes(32):
        raise ValueError(f"{field} is invalid")
    return raw.hex()


def _decode_words(value: Any, count: int) -> list[int]:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise VerificationError("vault returned malformed ABI data")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise VerificationError("vault returned non-hex ABI data") from exc
    if len(raw) != count * 32:
        raise VerificationError("vault returned unexpected ABI data length")
    return [int.from_bytes(raw[i:i + 32], "big") for i in range(0, len(raw), 32)]


@dataclass(frozen=True)
class VaultReservation:
    solver: str
    recipient: str
    amount: int
    release_after: int
    active: bool


class SobyaVaultReserver:
    """Reserve solver SOBY and return True only after finalized state readback."""

    def __init__(
        self,
        rpc: JsonRpc,
        *,
        expected_chain_id: int,
        vault_address: str,
        signer: Callable[[dict[str, Any]], str],
        confirmations: int = 2,
        gas_limit_multiplier_bps: int = 12000,
    ):
        if expected_chain_id <= 0 or confirmations < 1:
            raise ValueError("chain ID and confirmations must be positive")
        _word_address(vault_address, "vault address")
        if not callable(signer):
            raise ValueError("a local transaction signer callback is required")
        if not 10_000 <= gas_limit_multiplier_bps <= 30_000:
            raise ValueError("gas limit multiplier must be between 10000 and 30000 bps")
        self.rpc = rpc
        self.chain_id = expected_chain_id
        self.vault = vault_address.lower()
        self.signer = signer
        self.confirmations = confirmations
        self.gas_multiplier = gas_limit_multiplier_bps

    def _call_reservation(self, order_id: str) -> VaultReservation:
        data = _selector("reservations(bytes32)") + _word_bytes32(order_id, "order ID")
        raw = self.rpc.call("eth_call", [{"to": self.vault, "data": data}, "finalized"])
        words = _decode_words(raw, 5)
        solver = "0x" + words[0].to_bytes(32, "big")[-20:].hex()
        recipient = "0x" + words[1].to_bytes(32, "big")[-20:].hex()
        if words[0] >> 160 or words[1] >> 160 or words[4] not in (0, 1):
            raise VerificationError("vault reservation contains non-canonical ABI values")
        return VaultReservation(solver, recipient, words[2], words[3], bool(words[4]))

    def reserve(self, quote: OrderQuote) -> bool:
        if not isinstance(quote, OrderQuote):
            raise ValueError("an immutable coordinator OrderQuote is required")
        order_word = _word_bytes32(quote.order_id, "order ID")
        recipient_word = _word_address(quote.destination_recipient, "recipient")
        solver = quote.solver.lower()
        _word_address(solver, "solver")
        amount = _word_uint(quote.destination_amount, 128, "SOBY amount")
        release_after = _word_uint(quote.refund_after, 64, "releaseAfter")
        if quote.destination_chain_id != self.chain_id:
            raise VerificationError("quote destination chain ID does not match pinned SOBYA chain")
        if quote.destination_amount <= 0:
            raise VerificationError("quote SOBY amount must be positive")
        if int(self.rpc.call("eth_chainId", []), 16) != self.chain_id:
            raise VerificationError("connected RPC is not the pinned SOBYA chain")
        code = self.rpc.call("eth_getCode", [self.vault, "finalized"])
        if not isinstance(code, str) or code in ("0x", "0x0"):
            raise VerificationError("configured SOBYA vault has no deployed code")

        existing = self._call_reservation(quote.order_id)
        if existing.active:
            if (existing.solver == solver and existing.recipient == quote.destination_recipient.lower()
                    and existing.amount == quote.destination_amount
                    and existing.release_after == quote.refund_after):
                return True
            raise VerificationError("order already has a conflicting active vault reservation")
        if existing.solver != "0x" + "00" * 20:
            raise VerificationError("order ID was previously used by the vault")

        calldata = (
            _selector("reserve(bytes32,address,uint128,uint64)")
            + order_word + recipient_word + amount + release_after
        )
        nonce = int(self.rpc.call("eth_getTransactionCount", [solver, "pending"]), 16)
        gas_price = int(self.rpc.call("eth_gasPrice", []), 16)
        tx = {
            "from": solver,
            "to": self.vault,
            "value": "0x0",
            "data": calldata,
            "nonce": hex(nonce),
            "chainId": self.chain_id,
            "gasPrice": hex(gas_price),
        }
        estimate = int(self.rpc.call("eth_estimateGas", [tx]), 16)
        tx["gas"] = hex((estimate * self.gas_multiplier + 9_999) // 10_000)
        raw_signed = self.signer(tx)
        if not isinstance(raw_signed, str) or not raw_signed.startswith("0x") or len(raw_signed) <= 2:
            raise VerificationError("local signer did not return a signed raw transaction")
        tx_hash = self.rpc.call("eth_sendRawTransaction", [raw_signed])
        if not isinstance(tx_hash, str) or len(tx_hash) != 66 or not tx_hash.startswith("0x"):
            raise VerificationError("SOBYA RPC returned an invalid transaction hash")
        submitted = self.rpc.call("eth_getTransactionByHash", [tx_hash])
        if (not isinstance(submitted, dict)
                or submitted.get("from", "").lower() != solver
                or submitted.get("to", "").lower() != self.vault
                or submitted.get("input", submitted.get("data", "")).lower() != calldata.lower()
                or int(submitted.get("value", "0x0"), 16) != 0
                or (submitted.get("chainId") is not None
                    and int(submitted["chainId"], 16) != self.chain_id)):
            raise VerificationError("broadcast transaction does not match the signed vault reservation")

        receipt = self.rpc.call("eth_getTransactionReceipt", [tx_hash])
        if receipt is None:
            raise VerificationError("vault reservation receipt is not available yet")
        if receipt.get("transactionHash", "").lower() != tx_hash.lower():
            raise VerificationError("vault reservation receipt hash mismatch")
        if receipt.get("to", "").lower() != self.vault:
            raise VerificationError("vault reservation receipt targets another contract")
        if int(receipt.get("status", "0x0"), 16) != 1:
            raise VerificationError("vault reservation transaction reverted")
        block_number = int(receipt["blockNumber"], 16)
        canonical = self.rpc.call("eth_getBlockByNumber", [hex(block_number), False])
        finalized = self.rpc.call("eth_getBlockByNumber", ["finalized", False])
        latest = int(self.rpc.call("eth_blockNumber", []), 16)
        if (canonical is None or canonical.get("hash", "").lower() != receipt.get("blockHash", "").lower()
                or finalized is None or int(finalized.get("number", "0x0"), 16) < block_number
                or latest - block_number + 1 < self.confirmations):
            raise VerificationError("vault reservation is not canonical and finalized")

        event_topic = "0x" + keccak(
            b"InventoryReserved(bytes32,address,address,uint256,uint64)"
        ).hex()
        found = False
        for log in receipt.get("logs", []):
            topics = log.get("topics", [])
            if (log.get("address", "").lower() == self.vault
                    and len(topics) == 4 and topics[0].lower() == event_topic
                    and topics[1].lower() == "0x" + order_word
                    and topics[2].lower() == "0x" + _word_address(solver, "solver")
                    and topics[3].lower() == "0x" + recipient_word):
                data = _decode_words(log.get("data"), 2)
                if data == [quote.destination_amount, quote.refund_after]:
                    found = True
                    break
        if not found:
            raise VerificationError("finalized receipt lacks the exact InventoryReserved event")

        observed = self._call_reservation(quote.order_id)
        if (not observed.active or observed.solver != solver
                or observed.recipient != quote.destination_recipient.lower()
                or observed.amount != quote.destination_amount
                or observed.release_after != quote.refund_after):
            raise VerificationError("finalized vault reservation readback does not match the quote")
        return True
