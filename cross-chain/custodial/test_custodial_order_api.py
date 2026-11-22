import json
import threading
import time
import unittest
from unittest.mock import patch
from http.client import HTTPConnection

from custodial_ledger import CustodialOrderLedger
from custodial_order_api import create_server


class FakeDepositWorker:
    def __init__(self): self.submitted = []
    def submit(self, order_id, tx_id, event_index):
        self.submitted.append((order_id, tx_id, event_index))


class OrderApiTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = CustodialOrderLedger(self.temp.name + "/orders.sqlite")
        self.worker = FakeDepositWorker()
        self.config = {"enabledSwapDirections": ["usdt_to_soby"],
            "enabledSourceNetworks": ["ethereum"], "networks": {
            "ethereum": {"inventoryWallet":"0x"+"11"*20,"usdtContract":"0x"+"22"*20,"payoutInventoryVerified":True},
            "tron": {"inventoryWallet":"T"+"1"*33,"usdtContract":"T"+"2"*33,"payoutInventoryVerified":True},
            "solana": {"inventoryWallet":"S"*44,"usdtMint":"M"*44,"payoutInventoryVerified":True},
            "sobya": {"inventoryWallet":"0x"+"33"*20,"payoutInventoryVerified":True},
        }}
        def price(direction, network, amount):
            return {"destination_amount": amount * 2, "rate":"2", "fee_bps":25,
                    "expires_at":int(time.time()) + 300,"executable":True}
        self.server = create_server("127.0.0.1",0,self.ledger,self.worker,
            config=self.config,quote_provider=price,access_secret="x"*48)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.temp.cleanup()

    def post(self,path,payload,token=None):
        c=HTTPConnection("127.0.0.1",self.port,timeout=3)
        headers={"Content-Type":"application/json"}
        if token: headers["Authorization"]="Bearer "+token
        c.request("POST",path,json.dumps(payload),headers)
        r=c.getresponse(); data=json.loads(r.read()); c.close()
        return r.status,data

    def get(self,path,token=None):
        c=HTTPConnection("127.0.0.1",self.port,timeout=3)
        headers={}
        if token: headers["Authorization"]="Bearer "+token
        c.request("GET",path,headers=headers)
        r=c.getresponse(); data=json.loads(r.read()); c.close()
        return r.status,data

    def request(self, **overrides):
        value={"direction":"usdt_to_soby","source_network":"ethereum","amount":"12.5",
               "source_wallet":"0x"+"44"*20,"destination_wallet":"0x"+"55"*20}
        value.update(overrides); return value

    def test_quote_preview_and_order_create(self):
        status,preview=self.post("/api/quote",self.request())
        self.assertEqual(status,200); self.assertEqual(preview["quote"]["destination_amount_base_units"],"25000000")
        status,created=self.post("/api/orders",self.request())
        self.assertEqual(status,201); self.assertEqual(created["deposit_address"],self.config["networks"]["ethereum"]["inventoryWallet"])
        oid,token=created["order_id"],created["order_token"]
        status,order=self.get("/api/orders/"+oid,token)
        self.assertEqual(status,200); self.assertEqual(order["order"]["state"],"created")

    def test_launch_exposes_only_ethereum_as_usdt_source(self):
        status, result = self.get("/api/networks")
        self.assertEqual(status, 200)
        self.assertEqual(result["sourceNetworks"], ["ethereum"])
        self.assertEqual(set(result["networks"]), {"ethereum", "sobya"})

    def test_tron_and_solana_usdt_quotes_and_orders_are_rejected(self):
        for network in ("tron", "solana"):
            for path in ("/api/quote", "/api/orders"):
                status, result = self.post(path, self.request(source_network=network))
                self.assertEqual(status, 400, (network, path, result))
                self.assertIn("not enabled", result["error"])

    def test_quote_and_create_reject_invalid_direction(self):
        for path in ("/api/quote","/api/orders"):
            status,_=self.post(path,self.request(direction="bad"))
            self.assertEqual(status,400)

    def test_invalid_amount_precision_rejected(self):
        status,_=self.post("/api/quote",self.request(amount="0.0000001"))
        self.assertEqual(status,400)

    def test_soby_to_usdt_requires_external_destination(self):
        self.config["enabledSwapDirections"].append("soby_to_usdt")
        payload=self.request(direction="soby_to_usdt",source_network="sobya",destination_network="tron",amount="1")
        status,result=self.post("/api/quote",payload)
        self.assertEqual(status,200,result)
        self.assertEqual(result["quote"]["destination_network"],"tron")

    def test_order_access_token_required_and_deposit_proof_bound(self):
        status,created=self.post("/api/orders",self.request())
        oid,token=created["order_id"],created["order_token"]
        status,_=self.get("/api/orders/"+oid)
        self.assertEqual(status,401)
        status,_=self.post("/api/orders/"+oid+"/deposit-proof",{"tx_id":"0xabc","event_index":0})
        self.assertEqual(status,401)
        status,result=self.post("/api/orders/"+oid+"/deposit-proof",{"tx_id":"0xabc","event_index":0},token)
        self.assertEqual(status,202,result)
        self.assertEqual(self.worker.submitted,[(oid,"0xabc",0)])

    def test_quote_expiry_must_be_future_and_bounded(self):
        self.server.quote_provider = lambda *_: {
            "destination_amount": 100, "rate": "2", "fee_bps": 25,
            "expires_at": 1, "executable": True,
        }
        status, _ = self.post("/api/quote", self.request())
        self.assertEqual(status, 400)

    def test_deposit_proof_is_rejected_after_order_quote_expiry(self):
        status, created = self.post("/api/orders", self.request())
        self.assertEqual(status, 201)
        order_id, token = created["order_id"], created["order_token"]
        with patch("custodial_order_api.time.time", return_value=2_000_000_001):
            status, result = self.post(
                "/api/orders/" + order_id + "/deposit-proof",
                {"tx_id": "0xabc", "event_index": 0}, token,
            )
        self.assertEqual(status, 400)
        self.assertIn("quote expired", result["error"])
        self.assertEqual(self.worker.submitted, [])

    def test_soby_to_usdt_is_disabled_by_default(self):
        payload=self.request(direction="soby_to_usdt",source_network="sobya",destination_network="tron",amount="1")
        status,result=self.post("/api/quote",payload)
        self.assertEqual(status,400)
        self.assertIn("not currently enabled",result["error"])

    def test_sobya_quote_uses_live_inventory_check_not_static_config_flag(self):
        # The quote provider checks the SOBYA balance against a finalized RPC
        # block; a stale static boolean must not block or replace that check.
        self.config["networks"]["sobya"]["payoutInventoryVerified"] = False
        status,result=self.post("/api/quote",self.request())
        self.assertEqual(status,200,result)

    def test_external_payout_still_requires_verified_inventory(self):
        self.config["enabledSwapDirections"].append("soby_to_usdt")
        self.config["networks"]["tron"]["payoutInventoryVerified"] = False
        payload=self.request(direction="soby_to_usdt",source_network="sobya",
                             destination_network="tron",amount="1")
        status,result=self.post("/api/quote",payload)
        self.assertEqual(status,400)
        self.assertIn("inventory has not been verified",result["error"])

    def test_api_never_binds_public_interface(self):
        with self.assertRaisesRegex(ValueError,"loopback"):
            create_server("0.0.0.0",0,self.ledger,self.worker,config=self.config,
                quote_provider=lambda *_:{},access_secret="x"*48)

    def test_quote_provider_failure_fails_closed(self):
        self.server.quote_provider = lambda *_: {"destination_amount":100,"executable":False}
        status,_=self.post("/api/quote",self.request())
        self.assertEqual(status,400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
