import unittest
from types import SimpleNamespace

from solders.keypair import Keypair

from solana_inventory_payout import SolanaUsdtPayoutAdapter
from payout_executor import PayoutError, PayoutIntent

USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


class FakeClient:
    def __init__(self, decimals=6):
        self.decimals = decimals
    def get_token_supply(self, mint):
        return SimpleNamespace(value=SimpleNamespace(decimals=self.decimals))


class SolanaInventoryPayoutTests(unittest.TestCase):
    def setUp(self):
        self.keypair = Keypair()
        self.adapter = SolanaUsdtPayoutAdapter(
            client=FakeClient(), keypair=self.keypair,
            inventory_wallet=str(self.keypair.pubkey()),
            usdt_mint=USDT_MINT, token_program=TOKEN_PROGRAM,
        )

    def test_inventory_signer_must_match_configured_wallet(self):
        with self.assertRaises(PayoutError):
            SolanaUsdtPayoutAdapter(
                client=FakeClient(), keypair=self.keypair,
                inventory_wallet=str(Keypair().pubkey()),
                usdt_mint=USDT_MINT, token_program=TOKEN_PROGRAM,
            )

    def test_only_six_decimal_configured_usdt_is_accepted(self):
        with self.assertRaises(PayoutError):
            SolanaUsdtPayoutAdapter(
                client=FakeClient(decimals=9), keypair=self.keypair,
                inventory_wallet=str(self.keypair.pubkey()),
                usdt_mint=USDT_MINT, token_program=TOKEN_PROGRAM,
            )

    def test_wrong_asset_and_network_rejected_before_transaction_signing(self):
        with self.assertRaises(PayoutError):
            self.adapter.prepare(PayoutIntent(
                "order-sol", "solana", "OTHER", 1_000_000, str(Keypair().pubkey())
            ))
        with self.assertRaises(PayoutError):
            self.adapter.prepare(PayoutIntent(
                "order-sol", "ethereum", "USDT", 1_000_000, str(Keypair().pubkey())
            ))


if __name__ == "__main__":
    unittest.main()
