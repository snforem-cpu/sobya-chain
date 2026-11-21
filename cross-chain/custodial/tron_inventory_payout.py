"""TRON TRC-20 USDT inventory payout adapter using local TronPy signing."""
from __future__ import annotations
import json
from typing import Any
from payout_executor import PayoutError, PayoutIntent, PreparedPayout

TRANSFER_TOPIC = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _norm_hex(value: str) -> str:
    value = str(value).lower().removeprefix("0x")
    if value.startswith("41"):
        value = value[2:]
    return value


class TronUsdtPayoutAdapter:
    network = "tron"

    def __init__(self, *, client: Any, private_key: Any, inventory_wallet: str,
                 usdt_contract: str, fee_limit_sun: int = 100_000_000):
        if fee_limit_sun < 1:
            raise ValueError("TRON fee limit must be positive SUN")
        self.client, self.private_key = client, private_key
        self.inventory, self.token = inventory_wallet, usdt_contract
        self.fee_limit_sun = fee_limit_sun
        try:
            signer = private_key.public_key.to_base58check_address()
        except Exception as exc:
            raise PayoutError("TRON local signer key is invalid") from exc
        if signer != inventory_wallet:
            raise PayoutError("TRON signer address does not match inventory wallet")
        contract = client.get_contract(usdt_contract)
        if contract is None:
            raise PayoutError("configured TRON USDT contract is unavailable")
        if contract.functions.decimals() != 6:
            raise PayoutError("configured TRON USDT contract decimals are not six")
        self.contract = contract

    def prepare(self, intent: PayoutIntent) -> PreparedPayout:
        if intent.network != self.network or intent.asset.lower() not in {
            self.token.lower(), "usdt-tron", "usdt"
        } or intent.amount_base_units <= 0:
            raise PayoutError("TRON payout intent is not the configured USDT asset")
        try:
            txn = (
                self.contract.functions.transfer(intent.destination, intent.amount_base_units)
                .with_owner(self.inventory)
                .fee_limit(self.fee_limit_sun)
                .build()
                .sign(self.private_key)
            )
            document = txn.to_json()
            txid = txn.txid
            if not txid or not isinstance(document, dict):
                raise ValueError("signed transaction missing ID or JSON")
            return PreparedPayout(txid.lower(), json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
        except Exception as exc:
            raise PayoutError("TRON transaction construction or local signing failed") from exc

    def broadcast(self, prepared: PreparedPayout) -> str:
        try:
            from tronpy.tron import Transaction
            document = json.loads(prepared.signed_payload.decode("utf-8"))
            transaction = Transaction.from_json(document, client=self.client)
            result = transaction.broadcast()
            if not isinstance(result, dict) or result.get("result") is not True:
                raise PayoutError("TRON node did not accept signed transaction")
            observed = str(result.get("txid", "")).lower()
            if observed != prepared.tx_id.lower():
                raise PayoutError("TRON node returned a different transaction ID")
            return observed
        except PayoutError:
            raise
        except Exception as exc:
            raise PayoutError("TRON broadcast outcome is uncertain; retry same signed transaction") from exc

    def verify_finalized(self, intent: PayoutIntent, tx_id: str) -> bool:
        try:
            info = self.client.get_solid_transaction_info(tx_id)
            if not info or not info.get("blockNumber") or str(info.get("id", "")).lower() != tx_id.lower():
                return False
            receipt = info.get("receipt", {})
            if receipt.get("result") != "SUCCESS":
                return False
            token_hex = _norm_hex(self.client.to_hex_address(self.token))
            sender_hex = _norm_hex(self.client.to_hex_address(self.inventory))
            destination_hex = _norm_hex(self.client.to_hex_address(intent.destination))
            matches = []
            for log in info.get("log", []):
                topics = [str(x).lower().removeprefix("0x") for x in log.get("topics", [])]
                if ( _norm_hex(log.get("address", "")) != token_hex
                        or len(topics) != 3 or topics[0] != TRANSFER_TOPIC):
                    continue
                if (topics[1][-40:] == sender_hex[-40:]
                        and topics[2][-40:] == destination_hex[-40:]
                        and int(log.get("data", "0"), 16) == intent.amount_base_units):
                    matches.append(log)
            return len(matches) == 1
        except Exception:
            return False


def load_tron_private_key_from_keystore(path: str, passphrase_env: str):
    from inventory_keystore import load_inventory_keystore_from_env
    from tronpy.keys import PrivateKey
    try:
        return PrivateKey(load_inventory_keystore_from_env(path, "tron", passphrase_env))
    except Exception as exc:
        raise PayoutError("could not unlock configured local TRON inventory keystore") from exc
