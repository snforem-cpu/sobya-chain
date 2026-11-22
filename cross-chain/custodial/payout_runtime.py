"""Build only explicitly enabled payout adapters from operator-owned config."""
from __future__ import annotations
import os
from typing import Any
from payout_executor import InventoryPayoutExecutor, PayoutJournal


class PayoutConfigurationError(ValueError):
    pass


def build_inventory_payout_executor(config: dict[str, Any], ledger: Any,
                                    journal_path: str) -> InventoryPayoutExecutor:
    if not isinstance(config, dict) or config.get("mode") != "custodial-inventory":
        raise PayoutConfigurationError("custodial inventory configuration is required")
    network_cfg = config.get("networks", {})
    if not isinstance(network_cfg, dict):
        raise PayoutConfigurationError("network configuration is malformed")
    adapters = {}
    feature_enabled = config.get("featureEnabled") is True
    if feature_enabled:
        # Initial release pays only native SOBY from the SOBYA inventory.
        # Ethereum is deposit-only; TRON and Solana are deferred entirely.
        for name in ("ethereum", "tron", "solana"):
            item = network_cfg.get(name, {})
            if isinstance(item, dict) and item.get("enabled") is True:
                raise PayoutConfigurationError(
                    f"{name} payouts are not supported in the Ethereum-to-SOBYA launch"
                )
        sobya_item = network_cfg.get("sobya")
        sobya_wallet = sobya_item.get("inventoryWallet") if isinstance(sobya_item, dict) else None
        if not isinstance(sobya_wallet, str) or not sobya_wallet.strip():
            raise PayoutConfigurationError("sobya inventory wallet is required")
        if network_cfg.get("sobya", {}).get("enabled") is True:
            from web3 import Web3
            from evm_inventory_payout import EvmInventoryPayoutAdapter, load_evm_account_from_keystore
            item = network_cfg["sobya"]
            rpc_url = os.environ.get(item.get("rpcUrlEnv", ""))
            if not rpc_url or not rpc_url.startswith("https://"):
                raise PayoutConfigurationError("SOBYA HTTPS RPC endpoint is missing")
            web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
            account = load_evm_account_from_keystore(
                os.environ.get(item.get("keystorePathEnv", ""), ""),
                "sobya", item.get("keystorePassphraseEnv", ""),
            )
            adapters["sobya"] = EvmInventoryPayoutAdapter(
                network="sobya", web3=web3, account=account, chain_id=int(item["chainId"]),
                inventory_wallet=item["inventoryWallet"], confirmations=int(item.get("confirmations", 2)),
            )
        if network_cfg.get("solana", {}).get("enabled") is True:
            from solana.rpc.api import Client
            from solana_inventory_payout import SolanaUsdtPayoutAdapter, load_solana_keypair_from_keystore
            item = network_cfg["solana"]
            rpc_url = os.environ.get(item.get("rpcUrlEnv", ""))
            if not rpc_url or not rpc_url.startswith("https://"):
                raise PayoutConfigurationError("Solana HTTPS RPC endpoint is missing")
            client = Client(rpc_url, timeout=20)
            keypair = load_solana_keypair_from_keystore(
                os.environ.get(item.get("keystorePathEnv", ""), ""),
                item.get("keystorePassphraseEnv", ""),
            )
            adapters["solana"] = SolanaUsdtPayoutAdapter(
                client=client, keypair=keypair, inventory_wallet=item["inventoryWallet"],
                usdt_mint=item["usdtMint"], token_program=item["tokenProgram"],
                decimals=int(item.get("usdtDecimals", 6)),
            )
    enabled = feature_enabled and network_cfg.get("sobya", {}).get("enabled") is True
    return InventoryPayoutExecutor(ledger, PayoutJournal(journal_path), adapters, enabled=enabled)
