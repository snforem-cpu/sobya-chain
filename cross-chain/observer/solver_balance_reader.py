"""Read finalized spendable SOBY inventory from the pinned SOBYA vault.

The contract's available(solver) view already subtracts on-chain reservations.
The coordinator takes the minimum of this value and its own ledger availability;
it must not subtract the same reservations twice.
"""
from __future__ import annotations

import re
from typing import Any

from eth_hash.auto import keccak
from self_hosted_supervisor import (
    SupervisorConfigError, validate_self_hosted_url,
)


class BalanceVerificationError(ValueError):
    """Raised when finalized vault inventory cannot be established."""


class FinalizedVaultInventoryReader:
    def __init__(self, rpc: Any, expected_chain_id: int, vault_address: str):
        if not isinstance(expected_chain_id, int) or isinstance(expected_chain_id, bool) or expected_chain_id <= 0:
            raise ValueError("expected SOBYA EVM chain ID must be positive")
        if not isinstance(vault_address, str) or re.fullmatch(r"0x[0-9a-fA-F]{40}", vault_address) is None:
            raise ValueError("vault address must be a canonical 20-byte EVM address")
        if int(vault_address[2:], 16) == 0:
            raise ValueError("vault address cannot be zero")
        url = getattr(rpc, "url", None)
        if not isinstance(url, str):
            raise ValueError("SOBYA vault RPC must expose its configured URL")
        try:
            validate_self_hosted_url(url)
        except SupervisorConfigError as exc:
            raise ValueError("SOBYA vault RPC must be a private self-hosted node") from exc
        if not callable(getattr(rpc, "call", None)):
            raise ValueError("SOBYA vault RPC client is invalid")
        self.rpc = rpc
        self.expected_chain_id = expected_chain_id
        self.vault = vault_address.lower()
        self._available_selector = "0x" + keccak(b"available(address)")[:4].hex()

    def __call__(self, solver: str) -> int:
        if not isinstance(solver, str) or re.fullmatch(r"0x[0-9a-fA-F]{40}", solver) is None:
            raise BalanceVerificationError("solver must be a canonical 20-byte EVM address")
        try:
            chain_id_raw = self.rpc.call("eth_chainId", [])
            chain_id = int(chain_id_raw, 16) if isinstance(chain_id_raw, str) else -1
        except Exception as exc:
            raise BalanceVerificationError("SOBYA chain identity query failed") from exc
        if chain_id != self.expected_chain_id:
            raise BalanceVerificationError("SOBYA vault chain ID mismatch")
        try:
            code = self.rpc.call("eth_getCode", [self.vault, "finalized"])
            if not isinstance(code, str) or code in ("0x", "0x0"):
                raise ValueError("vault has no deployed code")
            address_word = (bytes(12) + bytes.fromhex(solver[2:])).hex()
            data = self._available_selector + address_word
            result = self.rpc.call("eth_call", [{"to": self.vault, "data": data}, "finalized"])
            if not isinstance(result, str) or not result.startswith("0x"):
                raise ValueError("malformed ABI result")
            raw = bytes.fromhex(result[2:])
            if len(raw) != 32:
                raise ValueError("unexpected ABI result length")
            return int.from_bytes(raw, "big")
        except Exception as exc:
            raise BalanceVerificationError("finalized SOBYA vault inventory query failed") from exc
