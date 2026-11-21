"""Pure-Python EIP-712 solver quote signature verification.

Implements secp256k1 public-key recovery with low-s enforcement matching the
escrow contract. No private keys or signing functionality are present.
"""
from __future__ import annotations

from dataclasses import dataclass

from eth_hash.auto import keccak

from order_ledger import OrderQuote


P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)
HALF_N = N // 2
DOMAIN_TYPEHASH = keccak(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
ORDER_TYPEHASH = keccak(
    b"Order(bytes32 orderId,address user,address token,uint256 sourceAmount,address solver,"
    b"uint256 destinationChainId,address destinationRecipient,uint256 destinationAmount,"
    b"uint256 quoteExpiry,uint256 refundAfter)"
)
NAME_HASH = keccak(b"SOBYA Cross-Chain Escrow")
VERSION_HASH = keccak(b"1")


class SignatureVerificationError(ValueError):
    pass


def _address(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise SignatureVerificationError(f"{field} must be a hex address")
    raw = value.removeprefix("0x")
    if len(raw) == 42 and raw[:2].lower() == "41":
        raw = raw[2:]
    try:
        result = bytes.fromhex(raw)
    except ValueError as exc:
        raise SignatureVerificationError(f"{field} is invalid hex") from exc
    if len(result) != 20:
        raise SignatureVerificationError(f"{field} must be a 20-byte address")
    return result


def _bytes32(value: str, field: str) -> bytes:
    if not isinstance(value, str):
        raise SignatureVerificationError(f"{field} must be hex")
    try:
        raw = bytes.fromhex(value.removeprefix("0x"))
    except ValueError as exc:
        raise SignatureVerificationError(f"{field} is invalid hex") from exc
    if len(raw) != 32:
        raise SignatureVerificationError(f"{field} must be 32 bytes")
    return raw


def _uint(value: int, field: str) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= 2**256:
        raise SignatureVerificationError(f"{field} must be uint256")
    return value.to_bytes(32, "big")


def _add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if a == b:
        slope = (3 * x1 * x1) * pow(2 * y1, P - 2, P) % P
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P, P - 2, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def _mul(k: int, point=G):
    result = None
    addend = point
    while k:
        if k & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        k >>= 1
    return result


def _recover_address(digest: bytes, signature: bytes) -> str:
    if len(signature) != 65:
        raise SignatureVerificationError("signature must be 65 bytes")
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:64], "big")
    v = signature[64]
    if v in (0, 1):
        v += 27
    if v not in (27, 28) or not (1 <= r < N) or not (1 <= s <= HALF_N):
        raise SignatureVerificationError("signature has invalid v/r/s or non-canonical high-s")
    x = r
    if x >= P:
        raise SignatureVerificationError("signature recovery point is invalid")
    alpha = (pow(x, 3, P) + 7) % P
    beta = pow(alpha, (P + 1) // 4, P)
    y = beta if beta & 1 == (v - 27) else P - beta
    point = (x, y)
    if _mul(N, point) is not None:
        raise SignatureVerificationError("signature recovery point is not in subgroup")
    z = int.from_bytes(digest, "big") % N
    inverse_r = pow(r, N - 2, N)
    public_key = _mul(inverse_r, _add(_mul(s, point), _mul((-z) % N, G)))
    if public_key is None:
        raise SignatureVerificationError("signature recovered the point at infinity")
    address = keccak(public_key[0].to_bytes(32, "big") + public_key[1].to_bytes(32, "big"))[-20:]
    return "0x" + address.hex()


@dataclass(frozen=True)
class Eip712QuoteDomain:
    chain_id: int
    verifying_contract: str


class Eip712QuoteVerifier:
    """Verify solver quote signatures against the exact escrow EIP-712 domain."""

    def __init__(self, domains: dict[str, Eip712QuoteDomain]):
        if not domains:
            raise ValueError("at least one explicitly pinned source escrow domain is required")
        for name, domain in domains.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("source chain names must be non-empty")
            if not isinstance(domain, Eip712QuoteDomain) or domain.chain_id <= 0:
                raise ValueError("each source chain requires a positive pinned chain ID")
            _address(domain.verifying_contract, "escrow")
        self.domains = {key.lower(): value for key, value in domains.items()}

    def digest(self, quote: OrderQuote) -> bytes:
        domain = self.domains.get(quote.source_chain.lower())
        if domain is None:
            raise SignatureVerificationError("source chain has no pinned escrow domain")
        if quote.destination_chain_id <= 0:
            raise SignatureVerificationError("destination chain ID must be positive")
        verifying_contract = _address(domain.verifying_contract, "escrow")
        domain_hash = keccak(
            DOMAIN_TYPEHASH + NAME_HASH + VERSION_HASH + _uint(domain.chain_id, "source chain ID")
            + bytes(12) + verifying_contract
        )
        struct_hash = keccak(
            ORDER_TYPEHASH + _bytes32(quote.order_id, "order ID")
            + bytes(12) + _address(quote.user, "user")
            + bytes(12) + _address(quote.source_asset, "source asset")
            + _uint(quote.source_amount, "source amount")
            + bytes(12) + _address(quote.solver, "solver")
            + _uint(quote.destination_chain_id, "destination chain ID")
            + bytes(12) + _address(quote.destination_recipient, "destination recipient")
            + _uint(quote.destination_amount, "destination amount")
            + _uint(quote.quote_expiry, "quote expiry")
            + _uint(quote.refund_after, "refund deadline")
        )
        return keccak(b"\x19\x01" + domain_hash + struct_hash)

    def verify(self, quote: OrderQuote, signature: bytes) -> bool:
        digest = self.digest(quote)
        recovered = _recover_address(digest, signature)
        return recovered.lower() == ("0x" + _address(quote.solver, "solver").hex()).lower()
