"""Safe Enzonic entry point for the SOBYA custodial payout worker.

The launcher creates a local disabled config from the committed example only when
no operator config exists. It never enables a network or writes wallet secrets.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> int:
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    config_path = Path(
        os.environ.get("SOBYA_CUSTODIAL_CONFIG", str(HERE / "config.json"))
    ).expanduser()
    if not config_path.is_absolute():
        config_path = (HERE / config_path).resolve()

    if not config_path.exists():
        template_path = HERE / "config.example.json"
        if not template_path.is_file():
            raise SystemExit("custodial config template is missing; refusing to start")
        template = json.loads(template_path.read_text(encoding="utf-8"))
        if template.get("featureEnabled") is not False:
            raise SystemExit("refusing to bootstrap from a template with payouts enabled")
        networks = template.get("networks", {})
        if not isinstance(networks, dict) or any(
            not isinstance(networks.get(name), dict)
            or networks[name].get("enabled") is not False
            for name in ("ethereum", "tron", "solana", "sobya")
        ):
            raise SystemExit("refusing to bootstrap from a template with an enabled network")
        config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(template, indent=2) + "\n", encoding="utf-8"
        )
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
        print("Created local config.json from the disabled example; all payouts remain disabled.")

    # The first Enzonic deployment is an idle-only validation. Refuse to
    # start if a pre-existing local config has any live payout gate enabled.
    active_config = json.loads(config_path.read_text(encoding="utf-8"))
    if active_config.get("featureEnabled") is not False:
        raise SystemExit("live custodial payouts are not authorized for the Enzonic idle-start stage")
    active_networks = active_config.get("networks", {})
    if not isinstance(active_networks, dict) or any(
        not isinstance(active_networks.get(name), dict)
        or active_networks[name].get("enabled") is not False
        for name in ("ethereum", "tron", "solana", "sobya")
    ):
        raise SystemExit("all four network payout gates must remain disabled for the Enzonic idle-start stage")

    # Bootstrap the SOBYA keystore only when an operator supplies the one-time
    # Enzonic secret. This does not enable deposits, orders, or payouts.
    from inventory_keystore_bootstrap import bootstrap_sobya_keystore
    keystore_status = bootstrap_sobya_keystore(active_config, ROOT)
    if keystore_status == "created":
        print("Created and address-verified the encrypted SOBYA keystore outside the Git checkout.")
    elif keystore_status == "not_configured":
        print("SOBYA keystore not configured yet; payouts remain disabled.")

    os.environ["SOBYA_CUSTODIAL_CONFIG"] = str(config_path.resolve())
    os.environ.setdefault("SOBYA_CUSTODIAL_DB", str(HERE / "data" / "orders.sqlite3"))
    os.environ.setdefault("SOBYA_PAYOUT_JOURNAL", str(HERE / "data" / "payout-journal.sqlite3"))

    from custodial_runtime import main as runtime_main

    return runtime_main()


if __name__ == "__main__":
    raise SystemExit(main())
