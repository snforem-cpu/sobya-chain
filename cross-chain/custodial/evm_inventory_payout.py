"""Ethereum/SOBYA EVM inventory payout adapter.

Supports native SOBY on SOBYA and the configured USDT ERC-20 on Ethereum.
It signs locally, persists the signed bytes through PayoutJournal before broadcast,
and verifies exact finalized receipt contents before allowing ledger completion.
"""
from __future__ import annotations

from typing import Any
import importlib.util
import os
from pathlib import Path


from payout_executor import PayoutError, PayoutIntent, PreparedPayout

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _address(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise PayoutError(f"{field} must be a 20-byte EVM address")
    try:
        raw = bytes.fromhex(value[2:])
    except ValueError as exc:
        raise PayoutError(f"{field} is not valid hexadecimal") from exc
    if len(raw) != 20 or raw == bytes(20):
        raise PayoutError(f"{field} is invalid")
    return "0x" + raw.hex()


def _quantity(value: Any, field: str) -> int:
    if isinstance(value, str) and value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError as exc:
            raise PayoutError(f"{field} is malformed") from exc
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, "big")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise PayoutError(f"{field} is malformed")


class EvmInventoryPayoutAdapter:
    """Narrow EVM sender; signer is an already-unlocked local account object."""
    def __init__(self, *, network: str, web3: Any, account: Any, chain_id: int,
                 inventory_wallet: str, confirmations: int,
                 token_contract: str | None = None):
        if network not in {"ethereum", "sobya"}:
            raise ValueError("EVM adapter supports only ethereum or sobya")
        if chain_id <= 0 or confirmations < 1:
            raise ValueError("chain ID and finality confirmations must be positive")
        self.network, self.w3, self.account = network, web3, account
        self.chain_id, self.confirmations = chain_id, confirmations
        self.inventory = _address(inventory_wallet, "inventory wallet")
        self.token = _address(token_contract, "USDT contract") if token_contract else None
        if network == "ethereum" and not self.token:
            raise ValueError("Ethereum USDT contract is required")
        if network == "sobya" and self.token:
            raise ValueError("SOBYA inventory payout must be native SOBY, not an ERC-20")
        if _address(account.address, "signer address") != self.inventory:
            raise ValueError("local signer address does not match configured inventory wallet")
        if int(self.w3.eth.chain_id) != chain_id:
            raise ValueError("connected RPC chain ID does not match configured network")

    def _build(self, intent: PayoutIntent) -> dict[str, Any]:
        if intent.network != self.network or intent.amount_base_units <= 0:
            raise PayoutError("payout intent network or amount is invalid")
        recipient = _address(intent.destination, "payout destination")
        nonce = self.w3.eth.get_transaction_count(self.inventory, "pending")
        base = {"from": self.inventory, "nonce": nonce, "chainId": self.chain_id}
        if self.network == "sobya":
            tx = {**base, "to": recipient, "value": intent.amount_base_units, "data": b""}
        else:
            if intent.asset.lower() not in {self.token.lower(), "usdt-eth", "usdt"}:
                raise PayoutError("Ethereum payout asset is not the pinned USDT contract")
            # transfer(address,uint256), fixed ERC-20 ABI; no arbitrary calldata.
            data = "0xa9059cbb" + recipient[2:].rjust(64, "0") + hex(intent.amount_base_units)[2:].rjust(64, "0")
            tx = {**base, "to": self.token, "value": 0, "data": data}
        try:
            estimate = int(self.w3.eth.estimate_gas(tx))
            latest = self.w3.eth.get_block("latest")
            if "baseFeePerGas" in latest:
                priority = int(self.w3.eth.max_priority_fee)
                tx["maxPriorityFeePerGas"] = priority
                tx["maxFeePerGas"] = int(latest["baseFeePerGas"]) * 2 + priority
                tx.pop("gasPrice", None)
            else:
                tx["gasPrice"] = int(self.w3.eth.gas_price)
            tx["gas"] = (estimate * 120 + 99) // 100
        except Exception as exc:
            raise PayoutError("could not safely estimate EVM payout fees") from exc
        return tx

    def prepare(self, intent: PayoutIntent) -> PreparedPayout:
        tx = self._build(intent)
        try:
            signed = self.account.sign_transaction(tx)
            raw = bytes(signed.raw_transaction)
            tx_id = "0x" + bytes(signed.hash).hex()
        except Exception as exc:
            raise PayoutError("local EVM signing failed") from exc
        if not raw or len(tx_id) != 66:
            raise PayoutError("local EVM signer returned malformed signed transaction")
        return PreparedPayout(tx_id, raw)

    def broadcast(self, prepared: PreparedPayout) -> str:
        try:
            observed = self.w3.eth.send_raw_transaction(prepared.signed_payload)
            tx_id = observed.hex()
            if not tx_id.startswith("0x"):
                tx_id = "0x" + tx_id
            if tx_id.lower() != prepared.tx_id.lower():
                raise PayoutError("EVM RPC returned a different transaction hash")
            return tx_id
        except PayoutError:
            raise
        except Exception as exc:
            # A timeout or "already known" is uncertain. If the exact locally
            # derived hash is already visible, treat it as the same broadcast.
            try:
                self.w3.eth.get_transaction(prepared.tx_id)
                return prepared.tx_id
            except Exception:
                raise PayoutError("EVM broadcast outcome is uncertain; safe retry required") from exc

    def verify_finalized(self, intent: PayoutIntent, tx_id: str) -> bool:
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_id)
        except Exception:
            return False
        if receipt is None or int(receipt["status"]) != 1:
            return False
        block_number = int(receipt["blockNumber"])
        block_hash = receipt["blockHash"].hex()
        if not block_hash.startswith("0x"):
            block_hash = "0x" + block_hash
        latest = int(self.w3.eth.block_number)
        if latest - block_number + 1 < self.confirmations:
            return False
        try:
            finalized = self.w3.eth.get_block("finalized")
        except Exception:
            return False
        if int(finalized["number"]) < block_number:
            return False
        canonical = self.w3.eth.get_block(block_number)
        canonical_hash = canonical["hash"].hex()
        if not canonical_hash.startswith("0x"):
            canonical_hash = "0x" + canonical_hash
        if canonical_hash.lower() != block_hash.lower():
            return False
        tx = self.w3.eth.get_transaction(tx_id)
        if self.network == "sobya":
            return (
                _address(tx["from"], "observed sender") == self.inventory
                and _address(tx["to"], "observed recipient") == _address(intent.destination, "destination")
                and int(tx["value"]) == intent.amount_base_units
                and int(tx.get("value", 0)) > 0
            )
        if _address(tx["from"], "observed sender") != self.inventory or _address(tx["to"], "observed token") != self.token:
            return False
        recipient = _address(intent.destination, "destination").lower()
        expected_topic = "0x" + recipient[2:].rjust(64, "0")
        matches = []
        for log in receipt["logs"]:
            topics = [x.hex() if hasattr(x, "hex") else str(x) for x in log["topics"]]
            topics = [x if x.startswith("0x") else "0x" + x for x in topics]
            address = _address(log["address"], "log token")
            if address.lower() != self.token.lower() or len(topics) != 3 or topics[0].lower() != TRANSFER_TOPIC:
                continue
            expected_sender = "0x" + self.inventory[2:].lower().rjust(64, "0")
            if (topics[1].lower() == expected_sender.lower()
                    and topics[2].lower() == expected_topic.lower()
                    and _quantity(log["data"], "Transfer event amount") == intent.amount_base_units):
                matches.append(log)
        return len(matches) == 1


def load_evm_account_from_keystore(path: str, network: str, passphrase_env: str):
    """Unlock the network-bound encrypted local inventory key; never accepts key text."""
    from inventory_keystore import load_inventory_keystore_from_env
    if network not in {"ethereum", "sobya"}:
        raise PayoutError("EVM inventory keystore network must be ethereum or sobya")
    try:
        raw = load_inventory_keystore_from_env(path, network, passphrase_env)
        from eth_account import Account
        return Account.from_key(raw)
    except Exception as exc:
        raise PayoutError("could not unlock configured local EVM inventory keystore") from exc
