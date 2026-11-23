"""Order/quote HTTP API for the SOBYA shared-inventory swap worker.

The API creates durable orders and submits exact transaction/event proofs to the
same SQLite-backed queue consumed by the finalized-deposit runtime. It never
signs or broadcasts transactions.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from custodial_ledger import CustodialOrderError
from inventory_deposit_watchers import InventoryDepositError
from demand_pricing import DemandSnapshot, PricingError, calculate_demand_price
from inventory_deposit_watchers import JsonRpc


class OrderApiError(ValueError):
    pass


class CustodialOrderApi:
    def __init__(self, ledger: Any, deposit_worker: Any, config: dict[str, Any],
                 *, clock: Callable[[], int] | None = None):
        self.ledger = ledger
        self.deposit_worker = deposit_worker
        self.config = config
        self.clock = clock or (lambda: int(time.time()))
        if not isinstance(config, dict) or config.get("mode") != "custodial-inventory":
            raise OrderApiError("custodial inventory configuration is required")
        self.networks = config.get("networks")
        if not isinstance(self.networks, dict):
            raise OrderApiError("network configuration is malformed")
        self.pricing = config.get("pricing", {})
        self.limits = config.get("limits", {})
        if not isinstance(self.pricing, dict) or not isinstance(self.limits, dict):
            raise OrderApiError("pricing or limits configuration is malformed")
        self.quote_lifetime = self.limits.get("quoteLifetimeSeconds", 120)
        if (not isinstance(self.quote_lifetime, int) or isinstance(self.quote_lifetime, bool)
                or not 30 <= self.quote_lifetime <= 3600):
            raise OrderApiError("quote lifetime must be between 30 and 3600 seconds")
        self.database = str(ledger.database)
        with sqlite3.connect(self.database) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS pending_inventory_deposits (
                order_id TEXT PRIMARY KEY, network TEXT NOT NULL, tx_id TEXT NOT NULL,
                event_index INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(network, tx_id, event_index))""")
            db.execute("""CREATE TABLE IF NOT EXISTS custodial_api_quotes (
                order_id TEXT PRIMARY KEY,
                price_usdt_per_soby TEXT NOT NULL,
                gross_destination_amount TEXT NOT NULL,
                fee_base_units TEXT NOT NULL,
                fee_bps INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )""")

    @staticmethod
    def _amount(value: Any) -> int:
        if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, str) and value.isdigit())):
            raise OrderApiError("source_amount_base_units must be a positive integer or digit string")
        amount = int(value)
        if amount <= 0:
            raise OrderApiError("source_amount_base_units must be positive")
        return amount

    @staticmethod
    def _required(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OrderApiError(field + " is required")
        return value.strip()

    def _network(self, name: str, *, require_watch: bool = True) -> dict[str, Any]:
        if name not in {"ethereum", "sobya"}:
            raise OrderApiError("unsupported network")
        item = self.networks.get(name)
        if not isinstance(item, dict):
            raise OrderApiError("network configuration is missing")
        if require_watch and self.config.get("depositWatchEnabled") is not True:
            raise OrderApiError("global deposit verification is disabled")
        if require_watch and item.get("depositWatchEnabled") is not True:
            raise OrderApiError("deposit verification is not enabled for " + name)
        return item

    def _price_and_fee(self) -> tuple[Decimal, int]:
        reference = self.pricing.get("referenceLiquidityUsdtBaseUnits")
        if not isinstance(reference, int) or isinstance(reference, bool) or reference <= 0:
            raise OrderApiError("verified reference liquidity is required; live quotes are paused")
        window = self.pricing.get("demandWindowSeconds", 3600)
        max_age = self.pricing.get("demandMaxAgeSeconds", 300)
        now = self.clock()
        try:
            with sqlite3.connect(self.database) as db:
                buy = db.execute("SELECT COALESCE(SUM(CAST(source_amount AS INTEGER)),0) FROM custodial_orders WHERE state='complete' AND direction='usdt_to_soby' AND source_network='ethereum' AND updated_at >= datetime('now', ?)", ("-" + str(int(window)) + " seconds",)).fetchone()[0]
                sell = db.execute("SELECT COALESCE(SUM(CAST(destination_amount AS INTEGER)),0) FROM custodial_orders WHERE state='complete' AND direction='soby_to_usdt' AND destination_network='ethereum' AND updated_at >= datetime('now', ?)", ("-" + str(int(window)) + " seconds",)).fetchone()[0]
            snapshot = DemandSnapshot(int(buy), int(sell), int(window), now, True)
            result = calculate_demand_price(base_price_usdt_per_soby=self.pricing.get("baseReferencePriceUsdtPerSoby"), reference_liquidity_usdt_base_units=reference, snapshot=snapshot, now_epoch=now, expected_window_seconds=window, max_snapshot_age_seconds=max_age, upward_sensitivity_bps=self.pricing.get("upwardDemandSensitivityBps", 10000), downward_sensitivity_bps=self.pricing.get("downwardDemandSensitivityBps", 2500))
        except (PricingError, TypeError, ValueError, sqlite3.Error) as exc:
            raise OrderApiError("demand price unavailable: " + str(exc)) from exc
        fee_bps = self.limits.get("feeBps", 100)
        if not isinstance(fee_bps, int) or isinstance(fee_bps, bool) or not 0 <= fee_bps < 10000:
            raise OrderApiError("feeBps must be an integer from 0 to 9999")
        return result.quoted_price_usdt_per_soby, fee_bps

    def _check_live_inventory(self, network: str, amount: int) -> None:
        item = self._network(network, require_watch=False)
        if self.config.get("featureEnabled") is not True or item.get("enabled") is not True:
            raise OrderApiError("destination payout network is not enabled by verified operator configuration")
        if item.get("inventoryVerified") is not True:
            raise OrderApiError("destination inventory has not passed operator balance verification")
        env_name = item.get("rpcUrlEnv")
        import os
        rpc_url = os.environ.get(env_name, "") if isinstance(env_name, str) else ""
        if not rpc_url.startswith("https://"):
            raise OrderApiError("live destination inventory RPC is not configured over HTTPS")
        try:
            rpc = JsonRpc(rpc_url)
            expected_chain = item.get("chainId")
            actual_chain = int(rpc.call("eth_chainId", []), 16)
            if actual_chain != expected_chain:
                raise OrderApiError("destination inventory RPC chain ID mismatch")
            wallet = self._required(item.get("inventoryWallet"), "destination inventory wallet")
            if network == "ethereum":
                token = self._required(item.get("usdtContract"), "Ethereum USDT contract")
                owner = wallet.lower().removeprefix("0x").rjust(64, "0")
                data = "0x70a08231" + owner
                raw = rpc.call("eth_call", [{"to": token, "data": data}, "latest"])
                available = int(raw, 16)
                required = amount
            else:
                raw = rpc.call("eth_getBalance", [wallet, "latest"])
                available = int(raw, 16)
                reserve = int(self.limits.get("minimumInventoryBaseUnits", "100000000000000000000000"))
                required = amount + reserve
            if available < required:
                raise OrderApiError("live destination inventory is insufficient after protected reserve")
        except OrderApiError:
            raise
        except Exception as exc:
            raise OrderApiError("could not verify live destination inventory; quote refused") from exc

    def create_quote(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise OrderApiError("JSON object required")
        direction = payload.get("direction")
        source_network = payload.get("source_network")
        destination_network = payload.get("destination_network")
        source_wallet = self._required(payload.get("source_wallet"), "source_wallet")
        destination_wallet = self._required(payload.get("destination_wallet"), "destination_wallet")
        source_amount = self._amount(payload.get("source_amount_base_units"))

        if direction == "usdt_to_soby":
            if source_network != "ethereum" or destination_network != "sobya":
                raise OrderApiError("USDT-to-SOBY requires Ethereum source and SOBYA destination")
            source_cfg = self._network(source_network)
            destination_cfg = self._network("sobya", require_watch=False)
            source_asset = self._required(source_cfg.get("usdtContract") if source_network != "sobya" else None, "USDT asset")
            destination_asset = "asobya"
            deposit_address = self._required(source_cfg.get("inventoryWallet"), "source inventory wallet")
            price, fee_bps = self._price_and_fee()
            gross = int((Decimal(source_amount) / Decimal(10**6) / price * Decimal(10**18)).to_integral_value(rounding=ROUND_DOWN))
        elif direction == "soby_to_usdt":
            if source_network != "sobya" or destination_network != "ethereum":
                raise OrderApiError("SOBY-to-USDT requires SOBYA source and Ethereum destination")
            source_cfg = self._network("sobya")
            destination_cfg = self._network(destination_network, require_watch=False)
            source_asset = "asobya"
            destination_asset = self._required(destination_cfg.get("usdtContract"), "USDT asset")
            deposit_address = self._required(source_cfg.get("inventoryWallet"), "SOBYA inventory wallet")
            price, fee_bps = self._price_and_fee()
            gross = int((Decimal(source_amount) / Decimal(10**18) * price * Decimal(10**6)).to_integral_value(rounding=ROUND_DOWN))
        else:
            raise OrderApiError("unsupported swap direction")

        self._check_live_inventory(destination_network, gross)
        usdt_value = source_amount if direction == "usdt_to_soby" else gross
        max_order = self.limits.get("maxOrderUsdtBaseUnits", 500000000)
        daily_cap = self.limits.get("maxDailyUsdtBaseUnitsPerNetwork", 10000000000)
        if not isinstance(max_order, int) or isinstance(max_order, bool) or max_order <= 0:
            raise OrderApiError("maxOrderUsdtBaseUnits is invalid")
        if not isinstance(daily_cap, int) or isinstance(daily_cap, bool) or daily_cap <= 0:
            raise OrderApiError("maxDailyUsdtBaseUnitsPerNetwork is invalid")
        if usdt_value > max_order:
            raise OrderApiError("order exceeds the configured 500 USDT maximum")
        with sqlite3.connect(self.database) as db:
            if direction == "usdt_to_soby":
                used = db.execute("SELECT COALESCE(SUM(CAST(source_amount AS INTEGER)),0) FROM custodial_orders WHERE direction='usdt_to_soby' AND source_network='ethereum' AND state!='rejected' AND created_at >= datetime('now','start of day')").fetchone()[0]
            else:
                used = db.execute("SELECT COALESCE(SUM(CAST(destination_amount AS INTEGER)),0) FROM custodial_orders WHERE direction='soby_to_usdt' AND destination_network='ethereum' AND state!='rejected' AND created_at >= datetime('now','start of day')").fetchone()[0]
        if int(used) + usdt_value > daily_cap:
            raise OrderApiError("daily Ethereum USDT order limit reached")

        if gross <= 0:
            raise OrderApiError("quoted destination amount rounds to zero base units")
        fee = (gross * fee_bps) // 10000
        net = gross - fee
        if net <= 0:
            raise OrderApiError("fee consumes the entire destination amount")
        now = self.clock()
        expires = now + self.quote_lifetime
        order_id = str(uuid.uuid4())
        try:
            self.ledger.create_order(
                order_id=order_id, direction=direction,
                source_network=source_network, destination_network=destination_network,
                deposit_address=deposit_address, source_wallet=source_wallet,
                destination_wallet=destination_wallet, source_asset=source_asset,
                destination_asset=destination_asset, source_amount=source_amount,
                destination_amount=net,
            )
        except CustodialOrderError as exc:
            raise OrderApiError(str(exc)) from exc
        try:
            with sqlite3.connect(self.database) as db:
                db.execute("""INSERT INTO custodial_api_quotes
                    (order_id,price_usdt_per_soby,gross_destination_amount,fee_base_units,
                     fee_bps,expires_at,created_at) VALUES(?,?,?,?,?,?,?)""",
                    (order_id, str(price), str(gross), str(fee), fee_bps, expires, now))
        except Exception:
            # A partially created order is not eligible for deposit submission:
            # the API will not return its ID and no proof has been queued.
            raise
        return {
            "order_id": order_id, "status": "created", "direction": direction,
            "source_network": source_network, "destination_network": destination_network,
            "source_asset": source_asset, "destination_asset": destination_asset,
            "source_amount_base_units": str(source_amount),
            "gross_destination_amount_base_units": str(gross),
            "fee_base_units": str(fee), "fee_bps": fee_bps,
            "destination_amount_base_units": str(net),
            "price_usdt_per_soby": str(price),
            "deposit_address": deposit_address, "destination_wallet": destination_wallet,
            "quote_expires_at": expires, "quote_lifetime_seconds": self.quote_lifetime,
            "deposit_proof_required": ["transaction_id", "event_index"],
        }

    def submit_deposit(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise OrderApiError("JSON object required")
        tx_id = self._required(payload.get("transaction_id"), "transaction_id")
        event_index = payload.get("event_index")
        if not isinstance(event_index, int) or isinstance(event_index, bool) or event_index < 0:
            raise OrderApiError("event_index must be a non-negative integer")
        with sqlite3.connect(self.database) as db:
            row = db.execute("SELECT expires_at FROM custodial_api_quotes WHERE order_id=?",
                             (order_id,)).fetchone()
        if row is None:
            raise OrderApiError("unknown order")
        if self.clock() >= row[0]:
            raise OrderApiError("quote expired; create a new order before submitting a deposit")
        try:
            self.deposit_worker.submit(order_id, tx_id, event_index)
        except InventoryDepositError as exc:
            raise OrderApiError(str(exc)) from exc
        return {"order_id": order_id, "status": "deposit_submitted",
                "transaction_id": tx_id, "event_index": event_index,
                "message": "Deposit proof queued; payout remains blocked until finalized verification."}

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self.ledger.get_order(order_id)
        if order is None:
            raise OrderApiError("unknown order")
        with sqlite3.connect(self.database) as db:
            quote = db.execute("""SELECT price_usdt_per_soby,gross_destination_amount,
                fee_base_units,fee_bps,expires_at FROM custodial_api_quotes WHERE order_id=?""",
                (order_id,)).fetchone()
        if quote is None:
            raise OrderApiError("quote metadata is unavailable")
        with sqlite3.connect(self.database) as db:
            proof = db.execute("""SELECT status,attempts,last_error,tx_id,event_index
                FROM pending_inventory_deposits WHERE order_id=?""", (order_id,)).fetchone()
        return {
            "order_id": order_id, "status": order["state"],
            "deposit_proof": ({"status": proof[0], "attempts": proof[1],
                               "last_error": proof[2], "transaction_id": proof[3],
                               "event_index": proof[4]} if proof else None),
            "quote_expired": self.clock() >= quote[4] and order["state"] == "created",
            "direction": order["direction"], "source_network": order["source_network"],
            "destination_network": order["destination_network"],
            "source_amount_base_units": order["source_amount"],
            "destination_amount_base_units": order["destination_amount"],
            "deposit_transaction_id": order.get("deposit_tx"),
            "deposit_event_index": order.get("deposit_event_index"),
            "quote": {"price_usdt_per_soby": quote[0],
                      "gross_destination_amount_base_units": quote[1],
                      "fee_base_units": quote[2], "fee_bps": quote[3],
                      "expires_at": quote[4]},
        }


def make_handler(api: CustodialOrderApi):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SOBYA-Order-API/1.0"

        def _send(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            allowed_origin = api.config.get("api", {}).get("allowedOrigin")
            request_origin = self.headers.get("Origin")
            if isinstance(allowed_origin, str) and request_origin == allowed_origin:
                self.send_header("Access-Control-Allow-Origin", allowed_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            allowed_origin = api.config.get("api", {}).get("allowedOrigin")
            request_origin = self.headers.get("Origin")
            if not isinstance(allowed_origin, str) or request_origin != allowed_origin:
                return self._send(403, {"error": "origin is not allowed"})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise OrderApiError("invalid Content-Length") from exc
            if length <= 0 or length > 16384:
                raise OrderApiError("request body must be between 1 and 16384 bytes")
            try:
                value = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise OrderApiError("malformed JSON body") from exc
            if not isinstance(value, dict):
                raise OrderApiError("JSON object required")
            return value

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"status": "ok", "service": "sobya-order-api"})
            prefix = "/v1/orders/"
            if self.path.startswith(prefix):
                order_id = self.path[len(prefix):].split("?", 1)[0]
                try:
                    return self._send(200, api.get_order(order_id))
                except OrderApiError as exc:
                    return self._send(404, {"error": str(exc)})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                body = self._body()
                if self.path == "/v1/quotes":
                    return self._send(201, api.create_quote(body))
                prefix = "/v1/orders/"
                suffix = "/deposit"
                if self.path.startswith(prefix) and self.path.endswith(suffix):
                    order_id = self.path[len(prefix):-len(suffix)].strip("/")
                    return self._send(202, api.submit_deposit(order_id, body))
                return self._send(404, {"error": "not found"})
            except OrderApiError as exc:
                return self._send(400, {"error": str(exc)})
            except Exception:
                return self._send(500, {"error": "internal server error"})

        def log_message(self, fmt, *args):
            # Avoid logging user-supplied transaction payloads or addresses.
            return

    return Handler


def start_order_api(api: CustodialOrderApi, host: str, port: int) -> ThreadingHTTPServer:
    if not isinstance(host, str) or not host:
        raise OrderApiError("API bind host is invalid")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise OrderApiError("API port is invalid")
    server = ThreadingHTTPServer((host, port), make_handler(api))
    return server
