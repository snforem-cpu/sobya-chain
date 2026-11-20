import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "observer"))

from admission import ReadinessAdmissionGuard
from order_ledger import CrossChainOrderLedger
from pricing import InventoryAwareQuotePricer, PricingConfig
from eip712_quote_verifier import Eip712QuoteDomain
from source_observer_router import EthereumSourceConfig, TronSourceConfig, SolanaSourceConfig
from destination_payout_router import SobyaSettlementConfig, SourceIdentity
from runtime import build_local_server
from test_admission import FakeMonitor


class RuntimeCompositionTests(unittest.TestCase):
    def test_factory_wires_real_verifiers_without_starting_server(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = CrossChainOrderLedger(str(Path(directory) / "orders.sqlite"))
            try:
                solver = "0x" + "44" * 20
                ledger.set_solver_inventory(solver, 150_000_000 * 10**18)
                pricer = InventoryAwareQuotePricer(
                    PricingConfig(
                        usdt_atoms_numerator=2_000_000,
                        min_source_amount=1_000_000,
                        max_source_amount=100_000_000,
                    ),
                    ledger,
                    destination_chain_id=357812033857,
                )

                class PrivateRpc:
                    url = "http://127.0.0.1:8545"

                server = build_local_server(
                    host="127.0.0.1", port=0,
                    bearer_token="runtime-test-token-that-is-longer-than-32-bytes",
                    monitor=FakeMonitor(), ledger=ledger,
                    quote_domains={
                        "ethereum": Eip712QuoteDomain(1, "0x" + "11" * 20),
                        "tron": Eip712QuoteDomain(728126428, "0x" + "12" * 20),
                    },
                    ethereum_sources={
                        "ethereum": EthereumSourceConfig(1, "0x" + "11" * 20, PrivateRpc())
                    },
                    tron_sources={},
                    solana_source=None,
                    sobya_settlement=SobyaSettlementConfig(
                        357812033857, "0x" + "66" * 20, 2, PrivateRpc()
                    ),
                    source_identities={
                        "ethereum": SourceIdentity(
                            "0x" + "01" * 32, "0x" + "00" * 12 + "11" * 20,
                            "0x" + "00" * 12 + "33" * 20,
                        )
                    },
                    quote_pricer=pricer,
                )
                try:
                    self.assertEqual(server.server_address[0], "127.0.0.1")
                    self.assertTrue(callable(server.verify_quote_signature))
                    self.assertTrue(callable(server.verify_source_deposit))
                    self.assertTrue(callable(server.verify_destination_payout))
                    self.assertIs(server.quote_pricer, pricer)
                finally:
                    server.server_close()
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
