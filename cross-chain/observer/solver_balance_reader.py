"""Read finalized native SOBY balances from a pinned self-hosted SOBYA EVM node.

This is an inventory reconciliation input, not proof of ownership of solver
keys or a reservation. The coordinator still reserves obligations atomically
in its ledger and subtracts those reservations from the finalized balance.
"""
from __future__ import annotations

import re
from typing import Any

from self_hosted_supervisor import (
    SupervisorConfigError, validate_self_hosted_url,
)


class BalanceVerificationError(ValueError):
    """Raised when a finalized solver balance cannot be established."""


class FinalizedNativeBalanceReader:
    def __init__(self, rpc: Any, expected_chain_id: int):
        if not isinstance(expected_chain_id, int) or isinstance(expected_chain_id, bool) or expected_chain_id <= 0:
            raise ValueError("expected SOBYA EVM chain ID must be positive")
        url = getattr(rpc, "url", None)
        if not isinstance(url, str):
            raise ValueError("SOBYA balance RPC must expose its configured URL")
        try:
            validate_self_hosted_url(url)
        except SupervisorConfigError as exc:
            raise ValueError("SOBYA balance RPC must be a private self-hosted node") from exc
        if not callable(getattr(rpc, "call", None)):
            raise ValueError("SOBYA balance RPC client is invalid")
        self.rpc = rpc
        self.expected_chain_id = expected_chain_id

    def __call__(self, solver: str) -> int:
        if not isinstance(solver, str) or re.fullmatch(r"0x[0-9a-fA-F]{40}", solver) is None:
            raise BalanceVerificationError("solver must be a canonical 20-byte EVM address")
        try:
            chain_id_raw = self.rpc.call("eth_chainId", [])
            chain_id = int(chain_id_raw, 16) if isinstance(chain_id_raw, str) else -1
        except Exception as exc:
            raise BalanceVerificationError("SOBYA chain identity query failed") from exc
        if chain_id != self.expected_chain_id:
            raise BalanceVerificationError("SOBYA balance RPC chain ID mismatch")
        try:
            balance_raw = self.rpc.call("eth_getBalance", [solver, "finalized"])
            if not isinstance(balance_raw, str) or not balance_raw.startswith("0x"):
                raise ValueError("malformed balance")
            balance = int(balance_raw, 16)
        except Exception as exc:
            raise BalanceVerificationError("finalized SOBY balance query failed") from exc
        if balance < 0:
            raise BalanceVerificationError("finalized SOBY balance is negative")
        return balance
