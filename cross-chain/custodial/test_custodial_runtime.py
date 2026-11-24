import os
import unittest
from unittest.mock import patch

from custodial_runtime import (
    CustodialDepositPayoutRuntime,
    DepositRuntimeConfigurationError,
    build_inventory_deposit_verifiers,
)


def config():
    return {
        "mode": "custodial-inventory",
        "depositWatchEnabled": True,
        "networks": {
            "ethereum": {"depositWatchEnabled": True, "rpcUrlEnv": "ETH_RPC", "chainId": 1},
            "sobya": {"depositWatchEnabled": True, "rpcUrlEnv": "SOBYA_RPC", "chainId": 357812033857},
        },
    }


class DepositRuntimeBuilderTests(unittest.TestCase):
    def test_disabled_global_gate_builds_no_rpc_clients(self):
        cfg = config()
        cfg["depositWatchEnabled"] = False
        self.assertEqual(build_inventory_deposit_verifiers(cfg), {})

    def test_builds_only_ethereum_and_sobya_read_only_verifiers_from_https_env(self):
        with patch.dict(os.environ, {
            "ETH_RPC": "https://eth.invalid",
            "SOBYA_RPC": "https://sobya.invalid",
        }, clear=True):
            verifiers = build_inventory_deposit_verifiers(config())
        self.assertEqual(set(verifiers), {"ethereum", "sobya"})

    def test_missing_rpc_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(DepositRuntimeConfigurationError, "HTTPS RPC"):
                build_inventory_deposit_verifiers(config())




class UnifiedRuntimeTests(unittest.TestCase):
    def test_verification_runs_before_payout_worker(self):
        events = []

        class Deposits:
            def run_once(self):
                events.append("deposit")
                return {"verified": 1, "pending": 0, "failed": 0}

        class Payouts:
            def run_once(self):
                events.append("payout")
                return {"disabled": 1, "submitted": 0, "finalized": 0,
                        "pending": 0, "errors": 0}

        runtime = CustodialDepositPayoutRuntime(object(), Deposits(), Payouts())
        result = runtime.run_once()
        self.assertEqual(events, ["deposit", "payout"])
        self.assertEqual(result["deposits"]["verified"], 1)
        self.assertEqual(result["payouts"]["disabled"], 1)


if __name__ == "__main__":
    unittest.main()
