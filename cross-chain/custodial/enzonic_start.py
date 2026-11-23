"""Fail-closed Enzonic launcher with explicit validation for live operator config."""
from __future__ import annotations
import json, os, stat, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent

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
    for name in ("ethereum", "sobya"):
        item = networks.get(name)
        if not isinstance(item, dict) or item.get("enabled") is not True or item.get("depositWatchEnabled") is not True:
            raise SystemExit(name + " must have enabled and depositWatchEnabled set true")
        if item.get("inventoryVerified") is not True:
            raise SystemExit(name + " inventory must be independently verified before live mode")
        rpc_env, key_env, pass_env = item.get("rpcUrlEnv"), item.get("keystorePathEnv"), item.get("keystorePassphraseEnv")
        rpc = os.environ.get(rpc_env, "") if isinstance(rpc_env, str) else ""
        key = os.environ.get(key_env, "") if isinstance(key_env, str) else ""
        secret = os.environ.get(pass_env, "") if isinstance(pass_env, str) else ""
        if not rpc.startswith("https://") or not key or not secret:
            raise SystemExit(name + " requires HTTPS RPC and external keystore/passphrase environment variables")
        if not Path(key).is_file():
            raise SystemExit(name + " keystore file is missing")
    if any(isinstance(networks.get(name), dict) and (networks[name].get("enabled") is True or networks[name].get("depositWatchEnabled") is True) for name in ("tron", "solana")):
        raise SystemExit("TRON and Solana are not supported in this SOBYA launch")
    api = config.get("api", {})
    if not isinstance(api, dict) or api.get("enabled") is not True or api.get("host", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise SystemExit("live order API must be enabled on loopback behind HTTPS ingress")
    if not isinstance(api.get("allowedOrigin"), str) or not api["allowedOrigin"].startswith("https://"):
        raise SystemExit("live API requires an explicit HTTPS browser origin allowlist")
    pricing = config.get("pricing", {})
    if not isinstance(pricing.get("referenceLiquidityUsdtBaseUnits"), int) or pricing["referenceLiquidityUsdtBaseUnits"] <= 0:
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
