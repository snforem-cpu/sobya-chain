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
        # Ethereum and SOBYA are separate EVM chains and may intentionally use
        # the same address when derived from the same private key. TRON and
        # Solana inventory addresses must remain distinct from each other and
        # from the EVM inventory address.
        required = ("ethereum", "tron", "solana", "sobya")
        wallets = {}
        for name in required:
            item = network_cfg.get(name)
            address = item.get("inventoryWallet") if isinstance(item, dict) else None
            if not isinstance(address, str) or not address.strip():
                raise PayoutConfigurationError(f"{name} inventory wallet is required")
            normalized = address.strip().lower()
            if normalized in wallets:
                previous = wallets[normalized]
                if {name, previous} != {"ethereum", "sobya"}:
                    raise PayoutConfigurationError(
                        f"{name} inventory wallet duplicates the {previous} wallet"
                    )
            else:
                wallets[normalized] = name
        if network_cfg.get("ethereum", {}).get("enabled") is True:
            from web3 import Web3
            from evm_inventory_payout import EvmInventoryPayoutAdapter, load_evm_account_from_keystore
            item = network_cfg["ethereum"]
            rpc_url = os.environ.get(item.get("rpcUrlEnv", ""))
            if not rpc_url or not rpc_url.startswith("https://"):
                raise PayoutConfigurationError("Ethereum HTTPS RPC endpoint is missing")
            web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
            account = load_evm_account_from_keystore(
                os.environ.get(item.get("keystorePathEnv", ""), ""),
                "ethereum", item.get("keystorePassphraseEnv", ""),
            )
            adapters["ethereum"] = EvmInventoryPayoutAdapter(
                network="ethereum", web3=web3, account=account, chain_id=int(item["chainId"]),
                inventory_wallet=item["inventoryWallet"], confirmations=int(item.get("confirmations", 64)),
                token_contract=item["usdtContract"],
            )
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
        if network_cfg.get("tron", {}).get("enabled") is True:
            from tronpy import Tron
            from tronpy.providers import HTTPProvider
            from tron_inventory_payout import TronUsdtPayoutAdapter, load_tron_private_key_from_keystore
            item = network_cfg["tron"]
            rpc_url = os.environ.get(item.get("rpcUrlEnv", ""))
            if not rpc_url or not rpc_url.startswith("https://"):
                raise PayoutConfigurationError("TRON HTTPS RPC endpoint is missing")
            client = Tron(HTTPProvider(endpoint_uri=rpc_url))
            private_key = load_tron_private_key_from_keystore(
                os.environ.get(item.get("keystorePathEnv", ""), ""),
                item.get("keystorePassphraseEnv", ""),
            )
            adapters["tron"] = TronUsdtPayoutAdapter(
                client=client, private_key=private_key, inventory_wallet=item["inventoryWallet"],
                usdt_contract=item["usdtContract"], fee_limit_sun=int(item.get("feeLimitSun", 100_000_000)),
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
    enabled = feature_enabled and any(
        network_cfg.get(name, {}).get("enabled") is True for name in ("ethereum","tron","solana","sobya")
    )
    return InventoryPayoutExecutor(ledger, PayoutJournal(journal_path), adapters, enabled=enabled)
