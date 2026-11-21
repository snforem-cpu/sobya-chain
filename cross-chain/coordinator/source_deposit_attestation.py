"""EIP-712 payloads for SOBYA destination-side source-deposit attestations.

This module builds the exact digest consumed by SobyaCrossChainSettlement.
It deliberately contains no private-key loading or signing code.
"""
from __future__ import annotations

from dataclasses import dataclass

from eth_hash.auto import keccak


DOMAIN_TYPE = b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
ATTESTATION_TYPE = (
    b"SourceDepositAttestation(bytes32 orderId,bytes32 sourceChain,bytes32 sourceEscrow,"
    b"bytes32 sourceAsset,uint256 sourceAmount,address recipient,uint256 sobyAmount,"
    b"address solver,uint256 destinationChainId,uint64 releaseAfter)"
)
DOMAIN_NAME = b"SOBYA Cross-Chain Settlement"
DOMAIN_VERSION = b"1"


class SourceDepositAttestationError(ValueError):
    pass


def _bytes32(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise SourceDepositAttestationError(f"{field} must be hex")
    try:
        result = bytes.fromhex(value.removeprefix("0x"))
    except ValueError as exc:
        raise SourceDepositAttestationError(f"{field} is invalid hex") from exc
    if len(result) != 32:
        raise SourceDepositAttestationError(f"{field} must be exactly 32 bytes")
    return result


def _address(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise SourceDepositAttestationError(f"{field} must be an EVM address")
    raw = value.removeprefix("0x")
    try:
        result = bytes.fromhex(raw)
    except ValueError as exc:
        raise SourceDepositAttestationError(f"{field} is invalid hex") from exc
    if len(result) != 20:
        raise SourceDepositAttestationError(f"{field} must be exactly 20 bytes")
    return result


def _uint(value: int, field: str, bits: int = 256) -> bytes:
    if (
        not isinstance(value, int) or isinstance(value, bool)
        or value <= 0 or value >= 1 << bits
    ):
        raise SourceDepositAttestationError(f"{field} must be a positive uint{bits}")
    return value.to_bytes(32, "big")


@dataclass(frozen=True)
class SourceDepositAttestation:
    order_id: str
    source_chain: str
    source_escrow: str
    source_asset: str
    source_amount: int
    recipient: str
    soby_amount: int
    solver: str
    destination_chain_id: int
    release_after: int


def build_eip712_source_deposit_attestation(
    attestation: SourceDepositAttestation,
    *,
    settlement_contract: str,
) -> dict:
    """Return wallet-compatible EIP-712 typed data for local attestor signing."""
    _bytes32(attestation.order_id, "order ID")
    _bytes32(attestation.source_chain, "source chain")
    _bytes32(attestation.source_escrow, "source escrow")
    _bytes32(attestation.source_asset, "source asset")
    _uint(attestation.source_amount, "source amount")
    _address(attestation.recipient, "recipient")
    _uint(attestation.soby_amount, "SOBY amount")
    _address(attestation.solver, "solver")
    _uint(attestation.destination_chain_id, "destination chain ID")
    _uint(attestation.release_after, "release deadline", 64)
    _address(settlement_contract, "settlement contract")
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "SourceDepositAttestation": [
                {"name": "orderId", "type": "bytes32"},
                {"name": "sourceChain", "type": "bytes32"},
                {"name": "sourceEscrow", "type": "bytes32"},
                {"name": "sourceAsset", "type": "bytes32"},
                {"name": "sourceAmount", "type": "uint256"},
                {"name": "recipient", "type": "address"},
                {"name": "sobyAmount", "type": "uint256"},
                {"name": "solver", "type": "address"},
                {"name": "destinationChainId", "type": "uint256"},
                {"name": "releaseAfter", "type": "uint64"},
            ],
        },
        "primaryType": "SourceDepositAttestation",
        "domain": {
            "name": DOMAIN_NAME.decode("ascii"),
            "version": DOMAIN_VERSION.decode("ascii"),
            "chainId": attestation.destination_chain_id,
            "verifyingContract": "0x" + _address(settlement_contract, "settlement contract").hex(),
        },
        "message": {
            "orderId": "0x" + _bytes32(attestation.order_id, "order ID").hex(),
            "sourceChain": "0x" + _bytes32(attestation.source_chain, "source chain").hex(),
            "sourceEscrow": "0x" + _bytes32(attestation.source_escrow, "source escrow").hex(),
            "sourceAsset": "0x" + _bytes32(attestation.source_asset, "source asset").hex(),
            "sourceAmount": attestation.source_amount,
            "recipient": "0x" + _address(attestation.recipient, "recipient").hex(),
            "sobyAmount": attestation.soby_amount,
            "solver": "0x" + _address(attestation.solver, "solver").hex(),
            "destinationChainId": attestation.destination_chain_id,
            "releaseAfter": attestation.release_after,
        },
    }


def eip712_source_deposit_digest(
    attestation: SourceDepositAttestation,
    *,
    settlement_contract: str,
) -> bytes:
    """Compute the exact EIP-712 digest required by SobyaCrossChainSettlement."""
    domain = keccak(
        keccak(DOMAIN_TYPE)
        + keccak(DOMAIN_NAME)
        + keccak(DOMAIN_VERSION)
        + _uint(attestation.destination_chain_id, "destination chain ID")
        + bytes(12)
        + _address(settlement_contract, "settlement contract")
    )
    struct_hash = keccak(
        keccak(ATTESTATION_TYPE)
        + _bytes32(attestation.order_id, "order ID")
        + _bytes32(attestation.source_chain, "source chain")
        + _bytes32(attestation.source_escrow, "source escrow")
        + _bytes32(attestation.source_asset, "source asset")
        + _uint(attestation.source_amount, "source amount")
        + bytes(12)
        + _address(attestation.recipient, "recipient")
        + _uint(attestation.soby_amount, "SOBY amount")
        + bytes(12)
        + _address(attestation.solver, "solver")
        + _uint(attestation.destination_chain_id, "destination chain ID")
        + _uint(attestation.release_after, "release deadline", 64)
    )
    return keccak(b"\x19\x01" + domain + struct_hash)
