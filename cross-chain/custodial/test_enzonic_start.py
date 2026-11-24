import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import enzonic_start


def disabled_config():
    return {
        "mode": "custodial-inventory",
        "featureEnabled": False,
        "depositWatchEnabled": False,
        "networks": {
            "ethereum": {"enabled": False, "depositWatchEnabled": False},
            "sobya": {"enabled": False, "depositWatchEnabled": False},
        },
        "api": {
            "enabled": True, "host": "127.0.0.1", "port": 8080,
            "allowedOrigin": "https://snforem-cpu.github.io",
            "gatewayTokenEnv": "SOBYA_GATEWAY_TOKEN",
        },
    }


def live_one_way_config(eth_keystore=None):
    return {
        "mode": "custodial-inventory",
        "featureEnabled": True,
        "depositWatchEnabled": True,
        "networks": {
            "ethereum": {
                "enabled": False,
                "depositWatchEnabled": True,
                "chainId": 1,
                "usdtContract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "inventoryWallet": "0x" + "22" * 20,
                "rpcUrlEnv": "ETH_RPC",
            },
            "sobya": {
                "enabled": True,
                "depositWatchEnabled": False,
                "chainId": 357812033857,
                "inventoryWallet": "0x" + "33" * 20,
                "inventoryVerified": True,
                "rpcUrlEnv": "SOB_RPC",
                "keystorePathEnv": "SOB_KEY",
                "keystorePassphraseEnv": "SOB_PASS",
            },
        },
        "api": {
            "enabled": True,
            "host": "0.0.0.0",
            "port": 25701,
            "gatewayTokenEnv": "SOBYA_GATEWAY_TOKEN",
            "allowedOrigin": "https://snforem-cpu.github.io",
        },
        "pricing": {
            "baseReferencePriceUsdtPerSoby": "0.005",
            "upwardDemandSensitivityBps": 10000,
            "downwardDemandSensitivityBps": 2500,
            "priceCeiling": None,
            "priceFloor": None,
            "referenceLiquidityUsdtBaseUnits": 1000000000000,
            "referenceLiquidityVerified": True,
        },
        "limits": {
            "feeBps": 100,
            "maxOrderUsdtBaseUnits": 500000000,
            "maxDailyUsdtBaseUnitsPerNetwork": 10000000000,
            "minimumInventoryBaseUnits": "100000000000000000000000",
        },
    }


class EnzonicLauncherTests(unittest.TestCase):
    def test_bootstraps_only_disabled_local_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.example.json").write_text(json.dumps(disabled_config()), encoding="utf-8")
            old = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(os.environ, {}, clear=True), patch("custodial_runtime.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
                    self.assertFalse(cfg["featureEnabled"])
                    self.assertEqual(os.environ["SOBYA_CUSTODIAL_CONFIG"], str(root / "config.json"))
                finally:
                    os.chdir(old)

    def test_disabled_operator_config_is_accepted_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = disabled_config()
            (root / "config.example.json").write_text("{}", encoding="utf-8")
            path = root / "config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            old = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(os.environ, {"SOBYA_CUSTODIAL_CONFIG": str(path)}, clear=True), patch("custodial_runtime.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    self.assertEqual(json.loads(path.read_text(encoding="utf-8")), cfg)
                finally:
                    os.chdir(old)

    def test_incomplete_live_config_is_rejected(self):
        cfg = disabled_config()
        cfg["featureEnabled"] = True
        with self.assertRaisesRegex(SystemExit, "global depositWatchEnabled"):
            enzonic_start._validate_operator_config(cfg)

    def test_one_way_live_config_needs_only_sobya_signing_keystore(self):
        with tempfile.TemporaryDirectory() as directory:
            sobya_key = Path(directory) / "sobya.json"
            sobya_key.write_text("{}", encoding="utf-8")
            cfg = live_one_way_config()
            env = {
                "ETH_RPC": "https://eth.example/rpc",
                "SOB_RPC": "https://sob.example/rpc",
                "SOB_KEY": str(sobya_key),
                "SOB_PASS": "secret",
                "SOBYA_GATEWAY_TOKEN": "a" * 64,
            }
            with patch.dict(os.environ, env, clear=True):
                enzonic_start._validate_operator_config(cfg)

    def test_rejects_ethereum_payout_signer_requirement_or_mode(self):
        cfg = live_one_way_config()
        cfg["networks"]["ethereum"]["enabled"] = True
        with self.assertRaisesRegex(SystemExit, "Ethereum must be deposit-watch-only"):
            enzonic_start._validate_operator_config(cfg)

    def test_rejects_sobya_deposit_watcher_in_one_way_launch(self):
        cfg = live_one_way_config()
        cfg["networks"]["sobya"]["depositWatchEnabled"] = True
        with self.assertRaisesRegex(SystemExit, "SOBYA must be payout-only"):
            enzonic_start._validate_operator_config(cfg)


if __name__ == "__main__":
    unittest.main()
