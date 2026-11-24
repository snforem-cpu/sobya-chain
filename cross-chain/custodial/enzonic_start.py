"""Fail-closed Enzonic launcher with explicit validation for live operator config."""
from __future__ import annotations
import json, os, stat, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent

def _valid_evm_address(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        return False
    try:
        bytes.fromhex(value[2:])
    except ValueError:
        return False
    return True

def _validate_operator_config(config: dict) -> None:
    if not isinstance(config, dict) or config.get("mode") != "custodial-inventory":
        raise SystemExit("invalid custodial-inventory config")
    if config.get("featureEnabled") is not True:
        return
    networks = config.get("networks")
    if not isinstance(networks, dict):
        raise SystemExit("live config requires network settings")
    if config.get("depositWatchEnabled") is not True:
        raise SystemExit("live config requires global depositWatchEnabled=true")
    eth = networks.get("ethereum")
    sobya = networks.get("sobya")
    if not isinstance(eth, dict) or not isinstance(sobya, dict):
        raise SystemExit("live config requires Ethereum and SOBYA network objects")
    if eth.get("chainId") != 1 or sobya.get("chainId") != 357812033857:
        raise SystemExit("live config must pin Ethereum chain ID 1 and SOBYA EVM chain ID 357812033857")
    if str(eth.get("usdtContract", "")).lower() != "0xdac17f958d2ee523a2206206994597c13d831ec7":
        raise SystemExit("Ethereum USDT contract does not match the canonical mainnet token")
    if eth.get("usdtDecimals") != 6 or not _valid_evm_address(eth.get("inventoryWallet")):
        raise SystemExit("Ethereum USDT source wallet or six-decimal token configuration is invalid")
    if not _valid_evm_address(sobya.get("inventoryWallet")):
        raise SystemExit("SOBYA payout inventory wallet must be a valid EVM address")
    if any(isinstance(networks.get(name), dict) and (networks[name].get("enabled") is True or networks[name].get("depositWatchEnabled") is True) for name in ("tron", "solana")):
        raise SystemExit("TRON and Solana are not supported in this SOBYA launch")
    # This launch is deliberately one-way: Ethereum is a read-only USDT
    # deposit source; SOBYA is the only signing/payout destination.
    if eth.get("enabled") is True or eth.get("depositWatchEnabled") is not True:
        raise SystemExit("Ethereum must be deposit-watch-only (enabled=false, depositWatchEnabled=true)")
    eth_rpc_env = eth.get("rpcUrlEnv")
    eth_rpc = os.environ.get(eth_rpc_env, "") if isinstance(eth_rpc_env, str) else ""
    if not eth_rpc.startswith("https://"):
        raise SystemExit("Ethereum deposit watcher requires an HTTPS RPC endpoint")
    if sobya.get("enabled") is not True or sobya.get("depositWatchEnabled") is not False:
        raise SystemExit("SOBYA must be payout-only (enabled=true, depositWatchEnabled=false)")
    if sobya.get("inventoryVerified") is not True:
        raise SystemExit("SOBYA payout inventory must be independently verified before live mode")
    rpc_env, key_env, pass_env = sobya.get("rpcUrlEnv"), sobya.get("keystorePathEnv"), sobya.get("keystorePassphraseEnv")
    rpc = os.environ.get(rpc_env, "") if isinstance(rpc_env, str) else ""
    key = os.environ.get(key_env, "") if isinstance(key_env, str) else ""
    secret = os.environ.get(pass_env, "") if isinstance(pass_env, str) else ""
    if not rpc.startswith("https://") or not key or not secret:
        raise SystemExit("SOBYA payout requires HTTPS RPC and external keystore/passphrase environment variables")
    if not Path(key).is_file():
        raise SystemExit("SOBYA payout keystore file is missing")
    api = config.get("api", {})
    if not isinstance(api, dict) or api.get("enabled") is not True:
        raise SystemExit("live order API must be enabled")
    if api.get("host") != "0.0.0.0" or api.get("port") != 25701:
        raise SystemExit("live API must bind to the Enzonic Connect primary port 25701")
    token_env = api.get("gatewayTokenEnv")
    if not isinstance(token_env, str) or len(os.environ.get(token_env, "")) < 64:
        raise SystemExit("live API requires a shared gateway token of at least 64 characters in the Enzonic Connect environment")
    if api.get("allowedOrigin") != "https://snforem-cpu.github.io":
        raise SystemExit("live API origin must match the published SOBYA DEX origin")
    pricing = config.get("pricing", {})
    limits = config.get("limits", {})
    if not isinstance(pricing, dict) or not isinstance(limits, dict):
        raise SystemExit("live pricing and limits must be JSON objects")
    if pricing.get("baseReferencePriceUsdtPerSoby") != "0.005" or pricing.get("upwardDemandSensitivityBps") != 10000 or pricing.get("downwardDemandSensitivityBps") != 2500:
        raise SystemExit("live pricing settings do not match the approved SOBYA policy")
    if pricing.get("priceCeiling") is not None or pricing.get("priceFloor") is not None:
        raise SystemExit("SOBYA live pricing must remain uncapped and without a floor")
    if limits.get("feeBps") != 100 or limits.get("maxOrderUsdtBaseUnits") != 500000000 or limits.get("maxDailyUsdtBaseUnitsPerNetwork") != 10000000000:
        raise SystemExit("live fee or USDT order/daily limits do not match the approved policy")
    if str(limits.get("minimumInventoryBaseUnits")) != "100000000000000000000000":
        raise SystemExit("live SOBY protected inventory reserve must remain 100,000 SOBY")
    if pricing.get("referenceLiquidityVerified") is not True or not isinstance(pricing.get("referenceLiquidityUsdtBaseUnits"), int) or pricing["referenceLiquidityUsdtBaseUnits"] <= 0:
        raise SystemExit("live mode requires independently verified referenceLiquidityUsdtBaseUnits")

def main() -> int:
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    config_path = Path(os.environ.get("SOBYA_CUSTODIAL_CONFIG", str(HERE / "config.json"))).expanduser()
    if not config_path.is_absolute():
        config_path = (HERE / config_path).resolve()
    if not config_path.exists():
        template_path = HERE / "config.example.json"
        if not template_path.is_file():
            raise SystemExit("custodial config template is missing; refusing to start")
        template = json.loads(template_path.read_text(encoding="utf-8"))
        if template.get("featureEnabled") is not False:
            raise SystemExit("refusing to bootstrap from a template with payouts enabled")
        config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        config_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
        print("Created local disabled config.json; deposits and payouts remain fail-closed.")
    active = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_operator_config(active)
    os.environ["SOBYA_CUSTODIAL_CONFIG"] = str(config_path.resolve())
    os.environ.setdefault("SOBYA_CUSTODIAL_DB", str(HERE / "data" / "orders.sqlite3"))
    os.environ.setdefault("SOBYA_PAYOUT_JOURNAL", str(HERE / "data" / "payout-journal.sqlite3"))
    from custodial_runtime import main as runtime_main
    return runtime_main()

if __name__ == "__main__":
    raise SystemExit(main())
