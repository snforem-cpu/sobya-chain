"""Loopback-only customer order/quote API for the custodial inventory swap.

The quote calculation is injected from the pricing module. No price, fee, limit,
RPC endpoint, signing key, or payout capability is guessed by this HTTP layer.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import re
import sqlite3
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable
from urllib.parse import urlsplit

from custodial_ledger import CustodialOrderError

NETWORKS = ("ethereum", "tron", "solana", "sobya")
EXTERNAL = ("ethereum", "tron", "solana")
ASSET_DECIMALS = {"ethereum": 6, "tron": 6, "solana": 6, "sobya": 18}


class OrderApiError(ValueError):
    pass


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _amount_to_units(value: Any, decimals: int) -> int:
    if not isinstance(value, str) or len(value) > 80:
        raise OrderApiError("amount must be a decimal string")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OrderApiError("amount is not a valid decimal")
    if not amount.is_finite() or amount <= 0:
        raise OrderApiError("amount must be positive")
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise OrderApiError("amount has too many decimal places")
    units = int(scaled)
    if units > 2**256 - 1:
        raise OrderApiError("amount exceeds supported range")
    return units


def _required_text(value: Any, field: str, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise OrderApiError(f"{field} is required and must be at most {maximum} characters")
    return value.strip()


def _network_assets(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    configured = config.get("networks")
    if not isinstance(configured, dict):
        raise OrderApiError("network configuration is missing")
    assets: dict[str, dict[str, Any]] = {}
    for network in NETWORKS:
        item = configured.get(network)
        if not isinstance(item, dict):
            raise OrderApiError(f"{network} configuration is missing")
        wallet = _required_text(item.get("inventoryWallet"), f"{network} inventory wallet")
        if network == "ethereum":
            asset = _required_text(item.get("usdtContract"), "Ethereum USDT contract")
            symbol = "USDT"
        elif network == "tron":
            asset = _required_text(item.get("usdtContract"), "TRON USDT contract")
            symbol = "USDT"
        elif network == "solana":
            asset = _required_text(item.get("usdtMint"), "Solana USDT mint")
            symbol = "USDT"
        else:
            asset, symbol = "native", "SOBY"
        assets[network] = {
            "inventory_wallet": wallet, "asset": asset,
            "symbol": symbol, "decimals": ASSET_DECIMALS[network],
        }
    return assets


def create_server(
    host: str,
    port: int,
    ledger: Any,
    deposit_worker: Any,
    *,
    config: dict[str, Any],
    quote_provider: Callable[[str, str, int], dict[str, Any]],
    access_secret: str,
    max_body_bytes: int = 16384,
    rate_limit_per_minute: int = 30,
) -> ThreadingHTTPServer:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("order API must bind to a literal loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("order API is loopback-only; expose it only through a trusted TLS proxy")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("invalid order API port")
    if not callable(quote_provider):
        raise ValueError("a configured quote provider is required")
    if not isinstance(access_secret, str) or len(access_secret.encode()) < 32:
        raise ValueError("order access secret must contain at least 32 bytes")
    if not 1024 <= max_body_bytes <= 65536:
        raise ValueError("request body limit must be between 1024 and 65536 bytes")
    if not 1 <= rate_limit_per_minute <= 600:
        raise ValueError("rate limit must be between 1 and 600 requests per minute")
    assets = _network_assets(config)
    enabled_directions = config.get("enabledSwapDirections", ["usdt_to_soby"])
    if (not isinstance(enabled_directions, list) or not enabled_directions
            or any(item not in {"usdt_to_soby", "soby_to_usdt"} for item in enabled_directions)
            or len(set(enabled_directions)) != len(enabled_directions)):
        raise ValueError("enabledSwapDirections must be a non-empty unique list of supported directions")
    with sqlite3.connect(ledger.database) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS custodial_order_quote_expiry (
            order_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL
        )""")
    hits: dict[str, deque[float]] = defaultdict(deque)
    hit_lock = threading.Lock()

    server: ThreadingHTTPServer | None = None

    def quote(direction: str, source_network: str, source_amount: int) -> dict[str, Any]:
        if direction not in enabled_directions:
            raise OrderApiError("this swap direction is not currently enabled")
        if direction == "usdt_to_soby" and source_network not in EXTERNAL:
            raise OrderApiError("USDT-to-SOBY source must be Ethereum, TRON, or Solana")
        if direction == "soby_to_usdt" and source_network != "sobya":
            raise OrderApiError("SOBY-to-USDT source must be SOBYA")
        result = server.quote_provider(direction, source_network, source_amount)
        if not isinstance(result, dict):
            raise OrderApiError("quote provider returned an invalid quote")
        destination_amount = result.get("destination_amount")
        if not isinstance(destination_amount, int) or isinstance(destination_amount, bool) or destination_amount <= 0:
            raise OrderApiError("quote provider did not return a positive integer destination amount")
        if result.get("executable") is not True:
            raise OrderApiError("quote is not executable")
        expires_at = result.get("expires_at")
        now = int(time.time())
        if (not isinstance(expires_at, int) or isinstance(expires_at, bool)
                or not now < expires_at <= now + 3600):
            raise OrderApiError("quote provider returned an expired or invalid expiry")
        return result

    def token_for(order_id: str) -> str:
        digest = hmac.new(access_secret.encode(), order_id.encode(), hashlib.sha256).hexdigest()
        return digest

    class Handler(BaseHTTPRequestHandler):
        server_version = "SOBYA-Order-API"
        sys_version = ""

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def authorized_order(self, order_id: str) -> bool:
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + token_for(order_id)
            return hmac.compare_digest(supplied.encode(), expected.encode())

        def read_body(self) -> dict[str, Any]:
            if self.headers.get("Transfer-Encoding"):
                raise OrderApiError("transfer-encoded requests are not accepted")
            if self.headers.get_content_type() != "application/json":
                raise OrderApiError("Content-Type must be application/json")
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or not 1 <= int(length) <= max_body_bytes:
                raise OrderApiError("request body length is invalid")
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                raise OrderApiError("request body is incomplete")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise OrderApiError("request body must be a JSON object")
            return payload

        def rate_limited(self) -> bool:
            key = self.client_address[0]
            now = time.monotonic()
            with hit_lock:
                queue = hits[key]
                while queue and now - queue[0] >= 60:
                    queue.popleft()
                if len(queue) >= rate_limit_per_minute:
                    return True
                queue.append(now)
                return False

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                page = (Path(__file__).with_name("order-ui") / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(page)
                return
            if path == "/api/networks":
                self.send_json(200, {"networks": {
                    name: {"symbol": assets[name]["symbol"], "decimals": assets[name]["decimals"]}
                    for name in NETWORKS
                }, "directions": list(enabled_directions)})
                return
            if path == "/api/health":
                self.send_json(200, {"ok": True, "service": "sobya-order-api"})
                return
            match = re.fullmatch(r"/api/orders/([A-Za-z0-9-]{8,80})", path)
            if match:
                order_id = match.group(1)
                if not self.authorized_order(order_id):
                    self.send_json(401, {"error": "order access token required"})
                    return
                order = ledger.get_order(order_id)
                if order is None:
                    self.send_json(404, {"error": "order not found"})
                    return
                safe = {key: order[key] for key in (
                    "order_id", "direction", "source_network", "destination_network",
                    "deposit_address", "source_asset", "destination_asset",
                    "source_amount", "destination_amount", "state", "deposit_tx",
                    "deposit_event_index", "payout_tx", "created_at", "updated_at",
                )}
                safe["source_amount"] = str(safe["source_amount"])
                safe["destination_amount"] = str(safe["destination_amount"])
                with sqlite3.connect(ledger.database) as db:
                    expiry = db.execute(
                        "SELECT expires_at FROM custodial_order_quote_expiry WHERE order_id=?",
                        (order_id,),
                    ).fetchone()
                safe["quote_expires_at"] = expiry[0] if expiry else None
                self.send_json(200, {"order": safe})
                return
            self.send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path not in {"/api/quote", "/api/orders"} and not re.fullmatch(
                r"/api/orders/[A-Za-z0-9-]{8,80}/deposit-proof", path
            ):
                self.send_json(404, {"error": "not found"})
                return
            if self.rate_limited():
                self.send_json(429, {"error": "rate limit exceeded"})
                return
            try:
                body = self.read_body()
                if path in {"/api/quote", "/api/orders"}:
                    required = {"direction", "source_network", "amount", "source_wallet", "destination_wallet"}
                    allowed = required | ({"destination_network"} if body.get("direction") == "soby_to_usdt" else set())
                    if set(body) != allowed:
                        raise OrderApiError("request fields do not match the required schema")
                    direction = body["direction"]
                    source_network = body["source_network"]
                    if not isinstance(direction, str) or not isinstance(source_network, str):
                        raise OrderApiError("direction and source network are required")
                    if direction == "usdt_to_soby":
                        destination_network = "sobya"
                    elif direction == "soby_to_usdt":
                        destination_network = body.get("destination_network")
                        if destination_network not in EXTERNAL:
                            raise OrderApiError("destination_network must be Ethereum, TRON, or Solana")
                    else:
                        raise OrderApiError("unsupported swap direction")
                    if direction not in enabled_directions:
                        raise OrderApiError("this swap direction is not currently enabled")
                    network_config = config.get("networks", {})
                    destination_config = network_config.get(destination_network, {})
                    if destination_config.get("payoutInventoryVerified") is not True:
                        raise OrderApiError("destination payout inventory has not been verified")
                    source = _amount_to_units(body["amount"], assets[source_network]["decimals"]) if source_network in assets else 0
                    if source <= 0:
                        raise OrderApiError("unsupported source network or amount")
                    source_wallet = _required_text(body["source_wallet"], "source wallet")
                    destination_wallet = _required_text(body["destination_wallet"], "destination wallet")
                    result = quote(direction, source_network, source)
                    source_meta, destination_meta = assets[source_network], assets[destination_network]
                    response_quote = {
                        "direction": direction, "source_network": source_network,
                        "destination_network": destination_network,
                        "source_symbol": source_meta["symbol"],
                        "destination_symbol": destination_meta["symbol"],
                        "source_amount_base_units": str(source),
                        "destination_amount_base_units": str(result["destination_amount"]),
                        "destination_amount": format(Decimal(result["destination_amount"]) / (Decimal(10) ** destination_meta["decimals"]), "f"),
                        "rate": str(result.get("rate", "")),
                        "fee_bps": result.get("fee_bps"),
                        "expires_at": result.get("expires_at"),
                    }
                    if path == "/api/quote":
                        self.send_json(200, {"quote": response_quote, "executable": True})
                        return
                    if direction == "usdt_to_soby":
                        source_asset, destination_asset = source_meta["asset"], "native"
                    else:
                        source_asset, destination_asset = "native", destination_meta["asset"]
                    deposit_address = source_meta["inventory_wallet"]
                    order_id = ledger.create_order(
                        direction=direction, source_network=source_network,
                        destination_network=destination_network,
                        deposit_address=deposit_address, source_wallet=source_wallet,
                        destination_wallet=destination_wallet, source_asset=source_asset,
                        destination_asset=destination_asset, source_amount=source,
                        destination_amount=result["destination_amount"],
                    )
                    try:
                        with sqlite3.connect(ledger.database) as db:
                            db.execute(
                                "INSERT INTO custodial_order_quote_expiry(order_id,expires_at) VALUES(?,?)",
                                (order_id, result["expires_at"]),
                            )
                    except Exception:
                        ledger.reject(order_id)
                        raise
                    self.send_json(201, {
                        "order_id": order_id, "order_token": token_for(order_id),
                        "state": "created", "deposit_address": deposit_address,
                        "deposit_asset": source_meta["symbol"],
                        "deposit_amount_base_units": str(source),
                        "deposit_amount": body["amount"],
                        "quote": response_quote,
                    })
                    return
                match = re.fullmatch(r"/api/orders/([A-Za-z0-9-]{8,80})/deposit-proof", path)
                if match:
                    order_id = match.group(1)
                    if not self.authorized_order(order_id):
                        self.send_json(401, {"error": "order access token required"})
                        return
                    with sqlite3.connect(ledger.database) as db:
                        expiry = db.execute(
                            "SELECT expires_at FROM custodial_order_quote_expiry WHERE order_id=?",
                            (order_id,),
                        ).fetchone()
                    if expiry is None or int(time.time()) >= expiry[0]:
                        raise OrderApiError("quote expired or order quote metadata is missing")
                    if set(body) != {"tx_id", "event_index"}:
                        raise OrderApiError("tx_id and event_index are required")
                    tx_id = _required_text(body["tx_id"], "transaction ID", 180)
                    event_index = body["event_index"]
                    if not isinstance(event_index, int) or isinstance(event_index, bool) or event_index < 0:
                        raise OrderApiError("event_index must be a non-negative integer")
                    deposit_worker.submit(order_id, tx_id, event_index)
                    self.send_json(202, {"accepted": True, "order_id": order_id, "state": "deposit_verification_pending"})
                    return
            except (OrderApiError, CustodialOrderError, ValueError, TypeError, KeyError) as exc:
                self.send_json(400, {"error": str(exc)[:240]})
            except Exception:
                self.send_json(503, {"error": "quote or order service temporarily unavailable"})

        def do_PUT(self) -> None:
            self.send_json(405, {"error": "method not allowed"})

        def do_DELETE(self) -> None:
            self.send_json(405, {"error": "method not allowed"})

    server = ThreadingHTTPServer((host, port), Handler)
    server.quote_provider = quote_provider
    server.daemon_threads = True
    return server
