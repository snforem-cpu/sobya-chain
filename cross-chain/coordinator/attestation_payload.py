"""Deterministic attestation payload builders; deliberately contains no signer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_hash.auto import keccak

DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
PAYOUT_TYPE = (
    "Payout(bytes32 orderId,bytes32 destinationTxHash,uint256 destinationChainId,"
    "address destinationRecipient,uint256 destinationAmount,address escrow,uint256 sourceChainId)"
)
NAME = "SOBYA Cross-Chain Escrow"
VERSION = "1"


class AttestationPayloadError(ValueError):
    pass


def _bytes32(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise AttestationPayloadError(f"{field} must be hex")
    raw = value.removeprefix("0x")
    try:
        result = bytes.fromhex(raw)
    except ValueError as exc:
        raise AttestationPayloadError(f"{field} is invalid hex") from exc
    if len(result) != 32:
        raise AttestationPayloadError(f"{field} must be 32 bytes")
    return result


def _address(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise AttestationPayloadError(f"{field} must be an address")
    raw = value.removeprefix("0x")
    if len(raw) == 42 and raw[:2].lower() == "41":
        raw = raw[2:]
    try:
        result = bytes.fromhex(raw)
    except ValueError as exc:
        raise AttestationPayloadError(f"{field} is invalid hex") from exc
    if len(result) != 20:
        raise AttestationPayloadError(f"{field} must be a 20-byte EVM/TVM address")
    return result


def _uint(value: int, field: str) -> bytes:
    if not isinstance(value, int) or value <= 0 or value >= 2**256:
        raise AttestationPayloadError(f"{field} must be a positive uint256")
    return value.to_bytes(32, "big")


@dataclass(frozen=True)
class EvmPayoutAttestation:
    order_id: str
    destination_tx_hash: str
    destination_chain_id: int
    destination_recipient: str
    destination_amount: int
    source_escrow: str
    source_chain_id: int


def build_eip712_payout(attestation: EvmPayoutAttestation) -> dict[str, Any]:
    _bytes32(attestation.order_id, "order ID")
    _bytes32(attestation.destination_tx_hash, "destination transaction hash")
    _uint(attestation.destination_chain_id, "destination chain ID")
    _address(attestation.destination_recipient, "destination recipient")
    _uint(attestation.destination_amount, "destination amount")
    _address(attestation.source_escrow, "source escrow")
    _uint(attestation.source_chain_id, "source chain ID")
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Payout": [
                {"name": "orderId", "type": "bytes32"},
                {"name": "destinationTxHash", "type": "bytes32"},
                {"name": "destinationChainId", "type": "uint256"},
                {"name": "destinationRecipient", "type": "address"},
                {"name": "destinationAmount", "type": "uint256"},
                {"name": "escrow", "type": "address"},
                {"name": "sourceChainId", "type": "uint256"},
            ],
        },
        "primaryType": "Payout",
        "domain": {
            "name": NAME, "version": VERSION,
            "chainId": attestation.source_chain_id,
            "verifyingContract": "0x" + _address(attestation.source_escrow, "source escrow").hex(),
        },
        "message": {
            "orderId": "0x" + _bytes32(attestation.order_id, "order ID").hex(),
            "destinationTxHash": "0x" + _bytes32(attestation.destination_tx_hash, "destination transaction hash").hex(),
            "destinationChainId": attestation.destination_chain_id,
            "destinationRecipient": "0x" + _address(attestation.destination_recipient, "destination recipient").hex(),
            "destinationAmount": attestation.destination_amount,
            "escrow": "0x" + _address(attestation.source_escrow, "source escrow").hex(),
            "sourceChainId": attestation.source_chain_id,
        },
    }


def eip712_payout_digest(attestation: EvmPayoutAttestation) -> str:
    domain = keccak(
        keccak(DOMAIN_TYPE.encode())
        + keccak(NAME.encode())
        + keccak(VERSION.encode())
        + _uint(attestation.source_chain_id, "source chain ID")
        + bytes(12) + _address(attestation.source_escrow, "source escrow")
    )
    struct_hash = keccak(
        keccak(PAYOUT_TYPE.encode())
        + _bytes32(attestation.order_id, "order ID")
        + _bytes32(attestation.destination_tx_hash, "destination transaction hash")
        + _uint(attestation.destination_chain_id, "destination chain ID")
        + bytes(12) + _address(attestation.destination_recipient, "destination recipient")
        + _uint(attestation.destination_amount, "destination amount")
        + bytes(12) + _address(attestation.source_escrow, "source escrow")
        + _uint(attestation.source_chain_id, "source chain ID")
    )
    return "0x" + keccak(b"\x19\x01" + domain + struct_hash).hex()


def build_solana_attest_payout_instruction(order_id: str, destination_tx_hash: str) -> bytes:
    """Return Borsh enum variant 2 + order ID + SOBYA transaction hash."""
    return b"\x02" + _bytes32(order_id, "order ID") + _bytes32(
        destination_tx_hash, "destination transaction hash"
    )
