import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from browser_gateway import create_gateway, _validate_request, SlidingWindowLimiter


TOKEN = "gateway-test-token-that-is-longer-than-32-bytes"
ORIGIN = "https://dex.example.invalid"


class FakeCoordinatorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/quote-previews" or self.headers.get("Authorization") != "Bearer " + TOKEN:
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        response = json.dumps({
            "signed": False, "reserved": False,
            "quote": {"order_id": payload["request"]["order_id"]},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args):
        return


class BrowserGatewayTests(unittest.TestCase):
    def setUp(self):
        self.backend = ThreadingHTTPServer(("127.0.0.1", 0), FakeCoordinatorHandler)
        self.backend_thread = threading.Thread(target=self.backend.serve_forever, daemon=True)
        self.backend_thread.start()
        self.gateway = create_gateway(
            "127.0.0.1", 0,
            coordinator_url=f"http://127.0.0.1:{self.backend.server_address[1]}",
            bearer_token=TOKEN, allowed_origins={ORIGIN},
        )
        self.gateway_thread = threading.Thread(target=self.gateway.serve_forever, daemon=True)
        self.gateway_thread.start()
        self.port = self.gateway.server_address[1]

    def tearDown(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.gateway_thread.join(timeout=2)
        self.backend.shutdown()
        self.backend.server_close()
        self.backend_thread.join(timeout=2)

    def request(self, path="/api/cross-chain/v1/quote-previews", payload=None, origin=ORIGIN):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = json.dumps(payload if payload is not None else {"request": {
            "order_id": "order-1", "source_chain": "ethereum",
            "source_asset": "0x" + "11" * 20, "source_amount": 1_000_000,
            "user": "0x" + "22" * 20, "solver": "0x" + "33" * 20,
            "destination_recipient": "0x" + "44" * 20,
        }})
        connection.request("POST", path, body=body, headers={
            "Content-Type": "application/json", "Origin": origin,
        })
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def test_quote_preview_is_forwarded_and_remains_unsigned_unreserved(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertFalse(result["signed"])
        self.assertFalse(result["reserved"])
        self.assertEqual(result["quote"]["order_id"], "order-1")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), ORIGIN)

    def test_rejects_unapproved_origin(self):
        status, _, _ = self.request(origin="https://attacker.invalid")
        self.assertEqual(status, 403)

    def test_exposes_only_quote_preview_route(self):
        status, _, _ = self.request(path="/api/cross-chain/v1/quotes")
        self.assertEqual(status, 404)

    def test_gateway_rejects_non_loopback_bind(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            create_gateway(
                "0.0.0.0", 8766, coordinator_url="http://127.0.0.1:8765",
                bearer_token=TOKEN, allowed_origins={ORIGIN},
            )

    def test_gateway_requires_explicit_https_origins(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            create_gateway(
                "127.0.0.1", 0, coordinator_url="http://127.0.0.1:8765",
                bearer_token=TOKEN, allowed_origins={"*"},
            )

    def test_request_schema_rejects_unsupported_network_and_boolean_amount(self):
        payload = {"request": {
            "order_id": "order-1", "source_chain": "bitcoin",
            "source_asset": "asset", "source_amount": 1,
            "user": "user", "solver": "solver", "destination_recipient": "recipient",
        }}
        with self.assertRaisesRegex(ValueError, "unsupported"):
            _validate_request(json.dumps(payload).encode())
        payload["request"]["source_chain"] = "ethereum"
        payload["request"]["source_amount"] = True
        with self.assertRaisesRegex(ValueError, "positive integer"):
            _validate_request(json.dumps(payload).encode())

    def test_sliding_window_limiter(self):
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow("client", now=0))
        self.assertTrue(limiter.allow("client", now=1))
        self.assertFalse(limiter.allow("client", now=2))
        self.assertTrue(limiter.allow("client", now=61))


if __name__ == "__main__":
    unittest.main(verbosity=2)
