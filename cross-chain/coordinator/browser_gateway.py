"""Same-origin browser gateway for unsigned cross-chain quote previews.

Run behind the DEX host's reverse proxy. This process binds to loopback,
injects the coordinator bearer token server-side, and exposes only the
non-reserving quote-preview route. It cannot accept orders or move funds.
"""
from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


MAX_BODY_BYTES = 8192
ALLOWED_NETWORKS = {"ethereum", "tron", "solana"}


class SlidingWindowLimiter:
    def __init__(self, limit: int = 30, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate limit settings must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and current - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True


def _validate_request(body: bytes) -> dict:
    if not body or len(body) > MAX_BODY_BYTES:
        raise ValueError("request body size is invalid")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict) or set(value) != {"request"}:
        raise ValueError("request object is required")
    request = value["request"]
    required = {
        "order_id", "source_chain", "source_asset", "source_amount",
        "user", "solver", "destination_recipient",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError("quote request fields do not match the required schema")
    if request["source_chain"] not in ALLOWED_NETWORKS:
        raise ValueError("unsupported source network")
    amount = request["source_amount"]
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("source_amount must be a positive integer token base-unit amount")
    for field in required - {"source_amount"}:
        item = request[field]
        if not isinstance(item, str) or not item.strip() or len(item) > 256:
            raise ValueError(field + " is missing or invalid")
    return value


def create_gateway(
    host: str,
    port: int,
    *,
    coordinator_url: str,
    bearer_token: str,
    allowed_origins: set[str],
    requests_per_minute: int = 30,
):
    try:
        bind_ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("browser gateway must bind to a literal loopback IP") from exc
    if not bind_ip.is_loopback:
        raise ValueError("browser gateway must bind to loopback only")
    parsed = urlsplit(coordinator_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("coordinator URL must be a local HTTP loopback URL")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("coordinator URL must be an origin without a path")
    if not isinstance(bearer_token, str) or len(bearer_token.encode("utf-8")) < 32:
        raise ValueError("coordinator bearer token must contain at least 32 UTF-8 bytes")
    origins = {origin.rstrip("/") for origin in allowed_origins}
    if not origins or "*" in origins or any(urlsplit(origin).scheme != "https" for origin in origins):
        raise ValueError("explicit HTTPS DEX origins are required; wildcard origins are forbidden")

    limiter = SlidingWindowLimiter(requests_per_minute)

    class Handler(BaseHTTPRequestHandler):
        server_version = "SOBYA-Quote-Gateway"
        sys_version = ""

        def _send(self, status: int, payload: dict, origin: str | None = None):
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            origin_header = self.headers.get("Origin", "")
            origin = origin_header.rstrip("/")
            if origin not in self.server.allowed_origins:
                self._send(403, {"error": "origin not allowed"})
                return
            if urlsplit(self.path).path != "/api/cross-chain/v1/quote-previews":
                self._send(404, {"error": "not found"}, origin)
                return
            if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/json":
                self._send(415, {"error": "JSON content without transfer encoding is required"}, origin)
                return
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length.isdigit() or int(raw_length) <= 0 or int(raw_length) > MAX_BODY_BYTES:
                self._send(413, {"error": "request body size is invalid"}, origin)
                return
            try:
                body = self.rfile.read(int(raw_length))
                if len(body) != int(raw_length):
                    raise ValueError("request body is incomplete")
                _validate_request(body)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._send(400, {"error": str(exc)}, origin)
                return
            client_key = self.client_address[0]
            if not self.server.limiter.allow(client_key):
                self._send(429, {"error": "quote preview rate limit exceeded"}, origin)
                return
            request = Request(
                self.server.coordinator_url + "/v1/quote-previews",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.server.bearer_token,
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=8) as response:
                    status = response.status
                    payload = json.loads(response.read(MAX_BODY_BYTES + 1).decode("utf-8"))
                if status != 200 or not isinstance(payload, dict) or payload.get("signed") is not False or payload.get("reserved") is not False:
                    self._send(502, {"error": "coordinator did not return a valid unsigned preview"}, origin)
                    return
                self._send(200, payload, origin)
            except HTTPError as exc:
                self._send(503 if exc.code >= 500 else 422, {"error": "quote preview was not accepted"}, origin)
            except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                self._send(503, {"error": "quote coordinator is unavailable"}, origin)

        def do_GET(self):
            self._send(405, {"error": "method not allowed"})

        def do_PUT(self):
            self._send(405, {"error": "method not allowed"})

        def do_DELETE(self):
            self._send(405, {"error": "method not allowed"})

        def log_message(self, fmt, *args):
            # Never log request bodies, tokens, or user wallet addresses.
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.coordinator_url = coordinator_url.rstrip("/")
    server.bearer_token = bearer_token
    server.allowed_origins = origins
    server.limiter = limiter
    return server


def main():
    token = os.environ.get("SOBYA_COORDINATOR_BEARER_TOKEN", "")
    origins = {
        item.strip() for item in os.environ.get("SOBYA_DEX_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    coordinator_url = os.environ.get("SOBYA_COORDINATOR_URL", "http://127.0.0.1:8765")
    port = int(os.environ.get("SOBYA_QUOTE_GATEWAY_PORT", "8766"))
    server = create_gateway(
        "127.0.0.1", port, coordinator_url=coordinator_url,
        bearer_token=token, allowed_origins=origins,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
