import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import enzonic_start


class EnzonicLauncherTests(unittest.TestCase):
    def test_bootstraps_only_a_disabled_local_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.example.json").write_text(json.dumps({
                "featureEnabled": False,
                "networks": {
                    name: {"enabled": False}
                    for name in ("ethereum", "tron", "solana", "sobya")
                },
            }), encoding="utf-8")
            old_cwd = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(
                os.environ,
                {
                    "SOBYA_CUSTODIAL_CONFIG": "",
                    "SOBYA_CUSTODIAL_DB": "",
                    "SOBYA_PAYOUT_JOURNAL": "",
                },
            ), patch("payout_worker.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
                    self.assertFalse(config["featureEnabled"])
                    self.assertTrue(all(
                        config["networks"][name]["enabled"] is False
                        for name in ("ethereum", "tron", "solana", "sobya")
                    ))
                    self.assertEqual(
                        os.environ["SOBYA_CUSTODIAL_CONFIG"], str(root / "config.json")
                    )
                    self.assertEqual(
                        Path(os.environ["SOBYA_CUSTODIAL_DB"]),
                        root / "data" / "orders.sqlite3",
                    )
                finally:
                    os.chdir(old_cwd)

    def test_existing_operator_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.example.json").write_text("{}", encoding="utf-8")
            config_path = root / "config.json"
            config_path.write_text('{"operatorConfig": true}', encoding="utf-8")
            old_cwd = Path.cwd()
            with patch.object(enzonic_start, "HERE", root), patch.dict(
                os.environ,
                {
                    "SOBYA_CUSTODIAL_CONFIG": str(config_path),
                    "SOBYA_CUSTODIAL_DB": "",
                    "SOBYA_PAYOUT_JOURNAL": "",
                },
            ), patch("payout_worker.main", return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(), 0)
                    self.assertEqual(
                        config_path.read_text(encoding="utf-8"),
                        '{"operatorConfig": true}',
                    )
                finally:
                    os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
