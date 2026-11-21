"""Read-only finalized ERC-20 deposit verifier for Ethereum and SOBYA EVM chains.

This verifies a wallet-submitted transfer into a shared inventory address. It
never signs, broadcasts, or treats an arbitrary transaction as a credited order.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class EvmDepositError(ValueError):
    pass


@dataclass(frozen=True)
class ExpectedErc20Deposit:
    chain_id: int
    tx_hash: str
    token_contract: str
    inventory_wallet: str
    sender_wallet: str
    amount_base_units: int
    log_index: int


@dataclass(frozen=True)
class VerifiedErc20Deposit:
    chain_id: int
    tx_hash: str
    token_contract: str
    inventory_wallet: str
    sender_wallet: str
    amount_base_units: int
    log_index: int
    block_number: int
    block_hash: str


class EvmRpc:
    def __init__(self, url: str, timeout: int = 20,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("EVM production RPC must use HTTPS")
        self.url, self.timeout = url, timeout
        self.transport = transport or self._http_transport
        self._request_id = 0

    @staticmethod
    def _http_transport(url: str, payload: dict[str, Any], timeout: int) -> Any:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())

    def call(self, method: str, params: list[Any]) -> Any:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id,
                   "method": method, "params": params}
        result = self.transport(self.url, payload, self.timeout)
        if not isinstance(result, dict) or result.get("id") != self._request_id:
            raise EvmDepositError("invalid EVM JSON-RPC response envelope")
        if result.get("error") or "result" not in result:
            raise EvmDepositError(f"EVM RPC {method} failed")
        return result["result"]


def _address(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise EvmDepositError(f"{label} is not a 20-byte EVM address")
    try:
        int(value[2:], 16)
    except ValueError as exc:
        raise EvmDepositError(f"{label} is not hexadecimal") from exc
    return value.lower()


def _quantity(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise EvmDepositError(f"{label} is not an RPC quantity")
    try:
        number = int(value, 16)
    except ValueError as exc:
        raise EvmDepositError(f"{label} is malformed") from exc
    if number < 0:
        raise EvmDepositError(f"{label} is negative")
    return number


class Erc20DepositVerifier:
    """Verify one exact Transfer log and require the chain's finalized block."""

    def __init__(self, rpc: EvmRpc):
        self.rpc = rpc

    def verify(self, expected: ExpectedErc20Deposit) -> VerifiedErc20Deposit:
        if not isinstance(expected.chain_id, int) or isinstance(expected.chain_id, bool) or expected.chain_id <= 0:
            raise EvmDepositError("expected chain ID must be a positive integer")
        if not isinstance(expected.amount_base_units, int) or isinstance(expected.amount_base_units, bool) or expected.amount_base_units <= 0:
            raise EvmDepositError("expected token amount must be a positive integer")
        if not isinstance(expected.log_index, int) or isinstance(expected.log_index, bool) or expected.log_index < 0:
            raise EvmDepositError("expected log index must be a non-negative integer")
        tx_hash = expected.tx_hash.lower() if isinstance(expected.tx_hash, str) else ""
        if len(tx_hash) != 66 or not tx_hash.startswith("0x"):
            raise EvmDepositError("transaction hash must be 32 bytes")
        try:
            bytes.fromhex(tx_hash[2:])
        except ValueError as exc:
            raise EvmDepositError("transaction hash is malformed") from exc

        chain_id = _quantity(self.rpc.call("eth_chainId", []), "chain ID")
        if chain_id != expected.chain_id:
            raise EvmDepositError("RPC chain ID does not match configured network")
        receipt = self.rpc.call("eth_getTransactionReceipt", [tx_hash])
        if not isinstance(receipt, dict) or receipt.get("transactionHash", "").lower() != tx_hash:
            raise EvmDepositError("deposit receipt missing or transaction hash mismatch")
        if _quantity(receipt.get("status"), "receipt status") != 1:
            raise EvmDepositError("deposit transaction did not succeed")
        block_number = _quantity(receipt.get("blockNumber"), "receipt block number")
        block_hash = receipt.get("blockHash")
        if not isinstance(block_hash, str) or len(block_hash) != 66:
            raise EvmDepositError("receipt block hash is missing or malformed")
        finalized = self.rpc.call("eth_getBlockByNumber", ["finalized", False])
        if not isinstance(finalized, dict):
            raise EvmDepositError("chain did not provide a finalized block")
        finalized_height = _quantity(finalized.get("number"), "finalized block number")
        if block_number > finalized_height:
            raise EvmDepositError("deposit is not finalized")

        token = _address(expected.token_contract, "configured token")
        inventory = _address(expected.inventory_wallet, "inventory wallet")
        sender = _address(expected.sender_wallet, "expected sender")
        matches = []
        for log in receipt.get("logs", []):
            if _quantity(log.get("logIndex"), "log index") != expected.log_index:
                continue
            topics = log.get("topics", [])
            if (log.get("removed") is True or _address(log.get("address", ""), "log token") != token
                    or len(topics) != 3 or topics[0].lower() != TRANSFER_TOPIC):
                continue
            if len(topics[1]) != 66 or len(topics[2]) != 66:
                continue
            event_sender = _address("0x" + topics[1][-40:], "Transfer sender")
            event_recipient = _address("0x" + topics[2][-40:], "Transfer recipient")
            amount = _quantity(log.get("data"), "Transfer amount")
            if event_sender == sender and event_recipient == inventory and amount == expected.amount_base_units:
                matches.append(log)
        if len(matches) != 1:
            raise EvmDepositError("exact expected ERC-20 Transfer log not found")
        return VerifiedErc20Deposit(chain_id, tx_hash, token, inventory, sender,
            expected.amount_base_units, expected.log_index, block_number, block_hash.lower())
