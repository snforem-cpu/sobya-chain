"""Read-only verifiers for direct deposits into SOBYA shared inventory wallets.

The verifier accepts only an order-bound transaction/signature and exact transfer
index. It never scans by balance delta, signs, or broadcasts. RPC endpoints and
asset identities are operator configuration; no token address is guessed here.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

TRANSFER_TOPIC = "0xddf252ad1be2c69b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# Canonical ERC-20/TRC-20 Transfer(address,address,uint256) topic.
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class InventoryDepositError(ValueError):
    pass


@dataclass(frozen=True)
class ExpectedInventoryDeposit:
    network: str
    tx_id: str
    sender: str
    inventory_wallet: str
    asset: str
    amount_base_units: int
    event_index: int


@dataclass(frozen=True)
class VerifiedInventoryDeposit:
    network: str
    tx_id: str
    sender: str
    inventory_wallet: str
    asset: str
    amount_base_units: int
    event_index: int
    finalized_reference: str


def _positive_amount(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise InventoryDepositError("expected amount must be a positive integer")


def _evm_address(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise InventoryDepositError(f"{field} must be a 20-byte EVM address")
    try:
        bytes.fromhex(value[2:])
    except ValueError as exc:
        raise InventoryDepositError(f"{field} must be hexadecimal") from exc
    return value.lower()


def _hex_quantity(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise InventoryDepositError(f"{field} is not an RPC quantity")
    try:
        result = int(value, 16)
    except ValueError as exc:
        raise InventoryDepositError(f"{field} is malformed") from exc
    if result < 0:
        raise InventoryDepositError(f"{field} is negative")
    return result


def _hash32(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 66 or not value.startswith("0x"):
        raise InventoryDepositError(f"{field} must be 32 bytes")
    try:
        bytes.fromhex(value[2:])
    except ValueError as exc:
        raise InventoryDepositError(f"{field} is malformed") from exc
    return value.lower()


class JsonRpc:
    def __init__(self, url: str, timeout: int = 20,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("production RPC endpoint must use HTTPS")
        self.url, self.timeout = url, timeout
        self.transport = transport or self._http
        self._id = 0

    @staticmethod
    def _http(url: str, payload: dict[str, Any], timeout: int) -> Any:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def call(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        response = self.transport(self.url, {
            "jsonrpc": "2.0", "id": self._id, "method": method, "params": params,
        }, self.timeout)
        if not isinstance(response, dict) or response.get("id") != self._id:
            raise InventoryDepositError("invalid JSON-RPC response envelope")
        if response.get("error") or "result" not in response:
            raise InventoryDepositError(f"RPC call failed: {method}")
        return response["result"]


class EvmInventoryDepositVerifier:
    """Verifies either ERC-20 USDT or native EVM coin sent to inventory."""

    def __init__(self, rpc: JsonRpc, chain_id: int):
        if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
            raise ValueError("configured EVM chain ID must be positive")
        self.rpc, self.chain_id = rpc, chain_id

    def verify(self, expected: ExpectedInventoryDeposit) -> VerifiedInventoryDeposit:
        if expected.network not in {"ethereum", "sobya"}:
            raise InventoryDepositError("EVM verifier only supports Ethereum and SOBYA")
        _positive_amount(expected.amount_base_units)
        if not isinstance(expected.event_index, int) or isinstance(expected.event_index, bool) or expected.event_index < 0:
            raise InventoryDepositError("event index must be a non-negative integer")
        tx_hash = _hash32(expected.tx_id, "transaction hash")
        sender = _evm_address(expected.sender, "sender")
        inventory = _evm_address(expected.inventory_wallet, "inventory wallet")
        asset = expected.asset
        chain = _hex_quantity(self.rpc.call("eth_chainId", []), "chain ID")
        if chain != self.chain_id:
            raise InventoryDepositError("RPC chain ID does not match configured network")

        receipt = self.rpc.call("eth_getTransactionReceipt", [tx_hash])
        if not isinstance(receipt, dict) or receipt.get("transactionHash", "").lower() != tx_hash:
            raise InventoryDepositError("transaction receipt is missing or mismatched")
        if _hex_quantity(receipt.get("status"), "receipt status") != 1:
            raise InventoryDepositError("deposit transaction failed")
        block_number = _hex_quantity(receipt.get("blockNumber"), "receipt block")
        block_hash = _hash32(receipt.get("blockHash"), "receipt block hash")
        finalized = self.rpc.call("eth_getBlockByNumber", ["finalized", False])
        if not isinstance(finalized, dict) or _hex_quantity(finalized.get("number"), "finalized height") < block_number:
            raise InventoryDepositError("deposit is not finalized")
        canonical = self.rpc.call("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(canonical, dict) or canonical.get("hash", "").lower() != block_hash:
            raise InventoryDepositError("deposit block is not canonical")

        if expected.network == "sobya":
            # SOBY is the native coin on the SOBYA EVM chain, not an ERC-20.
            tx = self.rpc.call("eth_getTransactionByHash", [tx_hash])
            if not isinstance(tx, dict):
                raise InventoryDepositError("native deposit transaction is missing")
            if _evm_address(tx.get("from", ""), "transaction sender") != sender:
                raise InventoryDepositError("native deposit sender mismatch")
            if _evm_address(tx.get("to", ""), "transaction recipient") != inventory:
                raise InventoryDepositError("native deposit recipient mismatch")
            if _hex_quantity(tx.get("value"), "native transfer value") != expected.amount_base_units:
                raise InventoryDepositError("native deposit amount mismatch")
            if expected.event_index != 0:
                raise InventoryDepositError("native transfer event index must be zero")
        else:
            token = _evm_address(asset, "USDT contract")
            matches = []
            for log in receipt.get("logs", []):
                if _hex_quantity(log.get("logIndex"), "log index") != expected.event_index:
                    continue
                topics = log.get("topics", [])
                if (log.get("removed") is True or _evm_address(log.get("address", ""), "log token") != token
                        or len(topics) != 3 or topics[0].lower() != TRANSFER_TOPIC):
                    continue
                if len(topics[1]) != 66 or len(topics[2]) != 66:
                    continue
                event_sender = _evm_address("0x" + topics[1][-40:], "Transfer sender")
                event_to = _evm_address("0x" + topics[2][-40:], "Transfer recipient")
                amount = _hex_quantity(log.get("data"), "Transfer amount")
                if event_sender == sender and event_to == inventory and amount == expected.amount_base_units:
                    matches.append(log)
            if len(matches) != 1:
                raise InventoryDepositError("exact expected ERC-20 Transfer event not found")
        return VerifiedInventoryDeposit(expected.network, tx_hash, sender, inventory,
            asset, expected.amount_base_units, expected.event_index,
            f"{expected.network}:finalized:{block_number}")


def _tron_hex_address(value: str, field: str) -> str:
    """Normalize TRON base58check or 41-prefixed hex to lowercase 21-byte hex."""
    if not isinstance(value, str):
        raise InventoryDepositError(f"{field} is not a TRON address")
    if value.startswith("41") and len(value) == 42:
        try:
            bytes.fromhex(value)
            return value.lower()
        except ValueError:
            pass
    # Base58Check decode without accepting an invalid checksum.
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    try:
        number = 0
        for char in value:
            number = number * 58 + alphabet.index(char)
        raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
        raw = b"\x00" * (len(value) - len(value.lstrip("1"))) + raw
    except (ValueError, OverflowError) as exc:
        raise InventoryDepositError(f"{field} is not valid base58") from exc
    if len(raw) != 25:
        raise InventoryDepositError(f"{field} has invalid TRON address length")
    import hashlib
    if hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] != raw[21:]:
        raise InventoryDepositError(f"{field} has invalid TRON checksum")
    if raw[0] != 0x41:
        raise InventoryDepositError(f"{field} is not a mainnet TRON address")
    return raw[:21].hex()


class TronInventoryDepositVerifier:
    """Verifies a TRC-20 Transfer from TRON's Solidity Node (solidified state)."""

    def __init__(self, solidity_node_url: str, timeout: int = 20,
                 transport: Callable[[str, dict[str, Any], int], Any] | None = None):
        if not isinstance(solidity_node_url, str) or not solidity_node_url.startswith("https://"):
            raise ValueError("TRON Solidity Node endpoint must use HTTPS")
        self.url, self.timeout = solidity_node_url.rstrip("/"), timeout
        self.transport = transport or self._http

    @staticmethod
    def _http(url: str, payload: dict[str, Any], timeout: int) -> Any:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())

    def _call(self, path: str, payload: dict[str, Any]) -> Any:
        result = self.transport(self.url + path, payload, self.timeout)
        if not isinstance(result, dict):
            raise InventoryDepositError("invalid TRON Solidity Node response")
        return result

    def verify(self, expected: ExpectedInventoryDeposit) -> VerifiedInventoryDeposit:
        if expected.network != "tron":
            raise InventoryDepositError("TRON verifier only supports TRON deposits")
        _positive_amount(expected.amount_base_units)
        if not isinstance(expected.event_index, int) or isinstance(expected.event_index, bool) or expected.event_index < 0:
            raise InventoryDepositError("event index must be non-negative")
        txid = expected.tx_id.lower()
        if len(txid) != 64:
            raise InventoryDepositError("TRON transaction ID must be 32 bytes")
        try:
            bytes.fromhex(txid)
        except ValueError as exc:
            raise InventoryDepositError("TRON transaction ID is malformed") from exc
        info = self._call("/walletsolidity/gettransactioninfobyid", {"value": txid})
        if info.get("id", "").lower() != txid or not info.get("blockNumber"):
            raise InventoryDepositError("solidified TRON transaction is missing")
        receipt = info.get("receipt") or {}
        if receipt.get("result") != "SUCCESS":
            raise InventoryDepositError("TRON transaction did not succeed")
        block_number = info["blockNumber"]
        block = self._call("/walletsolidity/getblockbynum", {"num": block_number})
        block_id = block.get("blockID")
        if not isinstance(block_id, str) or len(block_id) != 64:
            raise InventoryDepositError("solidified TRON block identity is missing")
        logs = info.get("log", [])
        matches = []
        token = _tron_hex_address(expected.asset, "USDT contract")
        sender = _tron_hex_address(expected.sender, "sender")
        inventory = _tron_hex_address(expected.inventory_wallet, "inventory wallet")
        for index, log in enumerate(logs):
            if index != expected.event_index:
                continue
            if _tron_hex_address(log.get("address", ""), "log contract") != token:
                continue
            topics = log.get("topics", [])
            if len(topics) != 3 or topics[0].lower() != TRANSFER_TOPIC[2:]:
                continue
            try:
                event_from = "41" + topics[1][-40:].lower()
                event_to = "41" + topics[2][-40:].lower()
                amount = int(log.get("data", ""), 16)
            except (ValueError, TypeError) as exc:
                raise InventoryDepositError("TRON Transfer event is malformed") from exc
            if event_from == sender and event_to == inventory and amount == expected.amount_base_units:
                matches.append(log)
        if len(matches) != 1:
            raise InventoryDepositError("exact expected TRC-20 Transfer event not found")
        return VerifiedInventoryDeposit("tron", txid, expected.sender,
            expected.inventory_wallet, expected.asset, expected.amount_base_units,
            expected.event_index, f"tron:solidified:{block_number}:{block_id.lower()}")


class SolanaInventoryDepositVerifier:
    """Verifies a finalized SPL-USDT transfer into the inventory owner's token account."""

    def __init__(self, rpc: JsonRpc, token_program: str):
        if not isinstance(token_program, str) or not token_program:
            raise ValueError("SPL token program ID must be configured")
        self.rpc, self.token_program = rpc, token_program

    def verify(self, expected: ExpectedInventoryDeposit) -> VerifiedInventoryDeposit:
        if expected.network != "solana":
            raise InventoryDepositError("Solana verifier only supports Solana deposits")
        _positive_amount(expected.amount_base_units)
        if not isinstance(expected.event_index, int) or isinstance(expected.event_index, bool) or expected.event_index < 0:
            raise InventoryDepositError("instruction index must be non-negative")
        tx = self.rpc.call("getTransaction", [expected.tx_id, {
            "encoding": "jsonParsed", "commitment": "finalized",
            "maxSupportedTransactionVersion": 0,
        }])
        if not isinstance(tx, dict):
            raise InventoryDepositError("Solana transaction is not finalized or not found")
        meta = tx.get("meta") or {}
        if meta.get("err") is not None:
            raise InventoryDepositError("Solana deposit transaction failed")
        slot = tx.get("slot")
        if not isinstance(slot, int) or slot <= 0:
            raise InventoryDepositError("Solana finalized slot is invalid")
        transaction = tx.get("transaction", {})
        signatures = transaction.get("signatures", [])
        if not signatures or signatures[0] != expected.tx_id:
            raise InventoryDepositError("Solana transaction signature does not match submitted signature")
        message = transaction.get("message", {})
        keys = message.get("accountKeys", [])
        pubkeys = [item.get("pubkey") if isinstance(item, dict) else item for item in keys]
        instructions = message.get("instructions", [])
        if expected.event_index >= len(instructions):
            raise InventoryDepositError("Solana instruction index is outside transaction")
        ix = instructions[expected.event_index]
        program_index = ix.get("programIdIndex")
        program_id = pubkeys[program_index] if isinstance(program_index, int) and program_index < len(pubkeys) else ix.get("programId")
        if program_id != self.token_program:
            raise InventoryDepositError("Solana instruction is not from configured SPL Token program")
        parsed = ix.get("parsed") or {}
        if parsed.get("type") not in {"transfer", "transferChecked"}:
            raise InventoryDepositError("Solana instruction is not an SPL token transfer")
        info = parsed.get("info") or {}
        if info.get("destination") is None or info.get("source") is None:
            raise InventoryDepositError("SPL transfer accounts are missing")
        if info.get("authority") != expected.sender:
            raise InventoryDepositError("SPL transfer authority does not match expected sender")
        if parsed.get("type") == "transferChecked":
            if info.get("mint") != expected.asset:
                raise InventoryDepositError("SPL transfer mint does not match configured USDT mint")
            amount = info.get("tokenAmount", {}).get("amount")
        else:
            amount = info.get("amount")
            source_info = self.rpc.call("getAccountInfo", [info["source"], {
                "encoding": "jsonParsed", "commitment": "finalized",
            }]).get("value")
            if not source_info:
                raise InventoryDepositError("SPL source token account is missing")
            source_parsed = source_info.get("data", {}).get("parsed", {}).get("info", {})
            if source_parsed.get("mint") != expected.asset or source_parsed.get("owner") != expected.sender:
                raise InventoryDepositError("SPL source token account mint or authority mismatch")
        if str(amount) != str(expected.amount_base_units):
            raise InventoryDepositError("SPL transfer amount does not match order")
        destination = info["destination"]
        dest_info = self.rpc.call("getAccountInfo", [destination, {
            "encoding": "jsonParsed", "commitment": "finalized",
        }]).get("value")
        if not dest_info or dest_info.get("owner") != self.token_program:
            raise InventoryDepositError("SPL destination account is missing or has wrong token program")
        dest_parsed = dest_info.get("data", {}).get("parsed", {}).get("info", {})
        if dest_parsed.get("mint") != expected.asset or dest_parsed.get("owner") != expected.inventory_wallet:
            raise InventoryDepositError("SPL destination account is not the configured inventory USDT account")
        return VerifiedInventoryDeposit("solana", expected.tx_id, expected.sender,
            expected.inventory_wallet, expected.asset, expected.amount_base_units,
            expected.event_index, f"solana:finalized:{slot}")


class InventoryDepositService:
    """Order-bound deposit entry point used by the DEX/API.

    The caller supplies only the submitted tx/signature and transfer index. All
    expected sender, asset, amount, and inventory values come from the persisted
    order, never from untrusted request fields.
    """

    def __init__(self, ledger: Any, verifiers: dict[str, Any]):
        self.ledger = ledger
        self.verifiers = {str(key).lower(): value for key, value in verifiers.items()}
        self.recorder = InventoryDepositRecorder(ledger)

    def verify_order_deposit(self, order_id: str, tx_id: str,
                             event_index: int) -> VerifiedInventoryDeposit:
        order = self.ledger.get_order(order_id)
        if order is None:
            raise InventoryDepositError("unknown order")
        network = order.get("source_network", "").lower()
        if network not in {"ethereum", "tron", "solana", "sobya"}:
            raise InventoryDepositError("order has unsupported source network")
        verifier = self.verifiers.get(network)
        if verifier is None:
            raise InventoryDepositError("source network verifier is not configured")
        if order.get("state") not in {"created", "deposit_seen", "deposit_final"}:
            raise InventoryDepositError("order is not awaiting deposit verification")
        expected = ExpectedInventoryDeposit(
            network=network, tx_id=tx_id, sender=order["source_wallet"],
            inventory_wallet=order["deposit_address"], asset=order["source_asset"],
            amount_base_units=int(order["source_amount"]), event_index=event_index,
        )
        return self.recorder.verify_and_record(verifier, order_id, expected)

class InventoryDepositRecorder:
    """The only bridge from verified chain evidence into the custodial order ledger."""

    def __init__(self, ledger: Any):
        self.ledger = ledger

    def verify_and_record(self, verifier: Any, order_id: str,
                          expected: ExpectedInventoryDeposit) -> VerifiedInventoryDeposit:
        verified = verifier.verify(expected)
        inserted = self.ledger.record_deposit(
            order_id, tx_id=verified.tx_id, event_index=verified.event_index,
            observed_amount=verified.amount_base_units,
            observed_recipient=verified.inventory_wallet,
            observed_asset=verified.asset,
        )
        if inserted:
            self.ledger.confirm_deposit_final(order_id, verified=True)
        else:
            # A retry after a crash may encounter the same event already credited.
            # Treat the already-final order as success; never advance another state.
            order = self.ledger.get_order(order_id)
            if order is None or order.get("state") not in {"deposit_seen", "deposit_final"}:
                raise InventoryDepositError("duplicate event is not attached to a deposit-pending order")
            if order.get("state") == "deposit_seen":
                self.ledger.confirm_deposit_final(order_id, verified=True)
        return verified
