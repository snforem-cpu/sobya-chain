"""Solana finalized SPL-USDT inventory payout adapter (legacy SPL Token program)."""
from __future__ import annotations
import json
from typing import Any
from payout_executor import PayoutError, PayoutIntent, PreparedPayout


class SolanaUsdtPayoutAdapter:
    network = "solana"

    def __init__(self, *, client: Any, keypair: Any, inventory_wallet: str,
                 usdt_mint: str, token_program: str,
                 decimals: int = 6):
        if decimals != 6:
            raise ValueError("configured Solana USDT decimals must be six")
        self.client, self.keypair = client, keypair
        self.inventory, self.mint = inventory_wallet, usdt_mint
        self.decimals, self.token_program = decimals, token_program
        try:
            if str(keypair.pubkey()) != inventory_wallet:
                raise ValueError("key mismatch")
            from solders.pubkey import Pubkey
            from spl.token.constants import TOKEN_PROGRAM_ID
            if Pubkey.from_string(token_program) != TOKEN_PROGRAM_ID:
                raise ValueError("unexpected token program")
            self.owner = Pubkey.from_string(inventory_wallet)
            self.mint_key = Pubkey.from_string(usdt_mint)
            self.program = Pubkey.from_string(token_program)
            if int(client.get_token_supply(self.mint_key).value.decimals) != decimals:
                raise ValueError("mint precision mismatch")
        except Exception as exc:
            raise PayoutError("Solana key, USDT mint, or legacy Token Program configuration is invalid") from exc

    def _accounts(self, destination: str):
        from spl.token.instructions import get_associated_token_address
        from solders.pubkey import Pubkey
        recipient = Pubkey.from_string(destination)
        source_ata = get_associated_token_address(self.owner, self.mint_key, self.program)
        destination_ata = get_associated_token_address(recipient, self.mint_key, self.program)
        source_info = self.client.get_account_info(source_ata, encoding="jsonParsed").value
        if source_info is None or str(source_info.owner) != str(self.program):
            raise PayoutError("inventory USDT associated token account is missing or owned by wrong program")
        parsed = source_info.data.parsed if hasattr(source_info.data, "parsed") else None
        if not isinstance(parsed, dict):
            raise PayoutError("inventory USDT token account did not return parsed ownership evidence")
        info = parsed.get("info", {})
        if info.get("mint") != self.mint or info.get("owner") != self.inventory:
            raise PayoutError("inventory USDT token account owner or mint mismatch")
        return recipient, source_ata, destination_ata

    def prepare(self, intent: PayoutIntent) -> PreparedPayout:
        if (intent.network != self.network or intent.amount_base_units <= 0
                or intent.asset.lower() not in {self.mint.lower(), "usdt-solana", "usdt"}):
            raise PayoutError("Solana payout intent is not the configured USDT asset")
        if intent.amount_base_units > (1 << 64) - 1:
            raise PayoutError("SPL transfer amount exceeds the uint64 token amount limit")
        try:
            from solana.rpc.types import TxOpts
            from spl.token.instructions import (
                create_idempotent_associated_token_account,
                transfer_checked,
            )
            from spl.token.models import TransferCheckedParams
            from solders.message import Message
            from solders.transaction import Transaction
            from solders.hash import Hash
            recipient, source_ata, destination_ata = self._accounts(intent.destination)
            # Create the recipient ATA idempotently in the same signed transaction.
            create_ata = create_idempotent_associated_token_account(
                payer=self.owner, owner=recipient, mint=self.mint_key,
                token_program_id=self.program,
            )
            transfer = transfer_checked(TransferCheckedParams(
                program_id=self.program, source=source_ata, mint=self.mint_key,
                dest=destination_ata, owner=self.owner,
                amount=intent.amount_base_units, decimals=self.decimals,
            ))
            blockhash = self.client.get_latest_blockhash().value.blockhash
            message = Message.new_with_blockhash([create_ata, transfer], self.owner, blockhash)
            transaction = Transaction.new_unsigned(message)
            transaction.sign([self.keypair], blockhash)
            signed = bytes(transaction)
            tx_id = str(transaction.signatures[0])
            if not signed or not tx_id:
                raise ValueError("missing signed transaction or signature")
            return PreparedPayout(tx_id, signed)
        except PayoutError:
            raise
        except Exception as exc:
            raise PayoutError("Solana SPL transfer construction or local signing failed") from exc

    def broadcast(self, prepared: PreparedPayout) -> str:
        try:
            from solana.rpc.types import TxOpts
            from solana.rpc.commitment import Confirmed
            response = self.client.send_raw_transaction(
                prepared.signed_payload,
                opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed),
            )
            observed = str(response.value)
            if observed != prepared.tx_id:
                raise PayoutError("Solana RPC returned a different signature")
            return observed
        except PayoutError:
            raise
        except Exception as exc:
            raise PayoutError("Solana broadcast outcome is uncertain; retry same signed bytes") from exc

    def verify_finalized(self, intent: PayoutIntent, tx_id: str) -> bool:
        try:
            from solders.signature import Signature
            from spl.token.instructions import get_associated_token_address
            from solders.pubkey import Pubkey
            signature = Signature.from_string(tx_id)
            status = self.client.get_signature_statuses([signature], search_transaction_history=True).value[0]
            if status is None or status.err is not None or str(status.confirmation_status).lower().find("finalized") < 0:
                return False
            response = self.client.get_transaction(
                signature, encoding="jsonParsed", max_supported_transaction_version=0
            )
            value = response.value
            if value is None:
                return False
            raw = json.loads(value.to_json()) if hasattr(value, "to_json") else value
            if isinstance(raw, dict) and "result" in raw:
                raw = raw["result"]
            if not isinstance(raw, dict):
                return False
            meta = raw.get("meta") or {}
            if meta.get("err") is not None:
                return False
            recipient = Pubkey.from_string(intent.destination)
            expected_ata = str(get_associated_token_address(recipient, self.mint_key, self.program))
            matches = []
            instructions = raw.get("transaction", {}).get("message", {}).get("instructions", [])
            for instruction in instructions:
                parsed = instruction.get("parsed") if isinstance(instruction, dict) else None
                if not isinstance(parsed, dict) or parsed.get("type") != "transferChecked":
                    continue
                info = parsed.get("info", {})
                token_amount = info.get("tokenAmount", {})
                if (info.get("authority") == self.inventory
                        and info.get("mint") == self.mint
                        and info.get("destination") == expected_ata
                        and str(token_amount.get("amount")) == str(intent.amount_base_units)
                        and int(token_amount.get("decimals", -1)) == self.decimals):
                    matches.append(instruction)
            return len(matches) == 1
        except Exception:
            return False


def load_solana_keypair_from_keystore(path: str, passphrase_env: str):
    from inventory_keystore import load_inventory_keystore_from_env
    from solders.keypair import Keypair
    try:
        return Keypair.from_bytes(load_inventory_keystore_from_env(path, "solana", passphrase_env))
    except Exception as exc:
        raise PayoutError("could not unlock configured local Solana inventory keystore") from exc
