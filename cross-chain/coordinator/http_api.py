"""Authenticated loopback-only HTTP API for the local cross-chain coordinator.

The API requires injected, reviewed cryptographic/observer verifiers. It has no
signing keys, transaction broadcaster, RPC client, or public-bind capability.
"""
from __future__ import annotations

from dataclasses import asdict, fields
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import threading
from typing import Any, Callable
from urllib.parse import urlsplit

from coordinator import LocalCoordinator
from order_ledger import (
    DestinationPayoutEvidence,
    OrderQuote,
    SourceDepositEvidence,
)
from solver_balance_reader import FinalizedNativeBalanceReader

LOG = logging.getLogger("sobya.coordinator.http")


def _strict_dataclass(model: type, payload: Any):
    if not isinstance(payload, dict):
        raise ValueError("record must be a JSON object")
    expected = {field.name for field in fields(model)}
    if set(payload) != expected:
        raise ValueError("record fields do not match the required schema")
    values = {}
    for field in fields(model):
        value = payload[field.name]
        if field.name in {
            "source_amount", "destination_amount", "destination_chain_id",
            "quote_expiry", "refund_after", "event_index",
        }:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("integer field has invalid type")
        elif not isinstance(value, str) or not value:
            raise ValueError("string field is missing or invalid")
        values[field.name] = value
    return model(**values)


def create_server(
    host: str,
    port: int,
    coordinator: LocalCoordinator,
    *,
    bearer_token: str,
    verify_quote_signature: Callable[..., bool],
    verify_source_deposit: Callable[..., bool],
    verify_destination_payout: Callable[..., bool],
    quote_pricer: Any | None = None,
    max_body_bytes: int = 65536,
) -> ThreadingHTTPServer:
    try:
        bind_ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("coordinator API bind host must be a literal loopback IP") from exc
    if not bind_ip.is_loopback:
        raise ValueError("coordinator API must bind to loopback only")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("invalid coordinator API port")
    if not isinstance(bearer_token, str) or len(bearer_token.encode("utf-8")) < 32:
        raise ValueError("bearer token must contain at least 32 UTF-8 bytes")
    if max_body_bytes <= 0 or max_body_bytes > 1_048_576:
        raise ValueError("max request body must be between 1 and 1048576 bytes")
    if not all(callable(fn) for fn in (
        verify_quote_signature, verify_source_deposit, verify_destination_payout
    )):
        raise ValueError("all cryptographic and observer verifiers are required")
    inventory_guard = getattr(coordinator, "inventory_guard", None)
    quote_inventory_guard = getattr(quote_pricer, "assert_quote_inventory", None)
    balance_reader = getattr(quote_pricer, "finalized_balance", None)
    if not isinstance(balance_reader, FinalizedNativeBalanceReader):
        raise ValueError("HTTP API requires a pinned finalized SOBYA native-balance reader")
    if balance_reader.expected_chain_id != getattr(quote_pricer, "destination_chain_id", None):
        raise ValueError("quote pricing and finalized balance reader chain IDs differ")
    if not callable(quote_inventory_guard) or inventory_guard != quote_inventory_guard:
        raise ValueError("HTTP API must use the quote pricer's finalized inventory guard")

    class Handler(BaseHTTPRequestHandler):
        server_version = "SOBYA-Coordinator"
        sys_version = ""

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + bearer_token
            return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

        def _body(self) -> dict[str, Any]:
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("transfer-encoded requests are not accepted")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            raw_length = self.headers.get("Content-Length")
            if raw_length is None or not raw_length.isdigit():
                raise ValueError("a valid Content-Length is required")
            length = int(raw_length)
            if length <= 0 or length > max_body_bytes:
                raise OverflowError("request body size is invalid")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("request body is incomplete")
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def do_POST(self) -> None:
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            path = urlsplit(self.path).path
            try:
                body = self._body()
                if path == "/v1/quote-previews":
                    if self.server.quote_pricer is None:
                        self._send(503, {"error": "quote pricing is not configured"})
                        return
                    if set(body) != {"request"} or not isinstance(body["request"], dict):
                        raise ValueError("request object is required")
                    request = body["request"]
                    required = {
                        "order_id", "source_chain", "source_asset", "source_amount",
                        "user", "solver", "destination_recipient",
                    }
                    if set(request) != required:
                        raise ValueError("quote request fields do not match the required schema")
                    if not isinstance(request["source_amount"], int) or isinstance(request["source_amount"], bool):
                        raise ValueError("source_amount must be an integer token base-unit amount")
                    for field in required - {"source_amount"}:
                        if not isinstance(request[field], str) or not request[field]:
                            raise ValueError(f"{field} is required")
                    quote = self.server.quote_pricer.quote(**request)
                    self._send(200, {"signed": False, "reserved": False, "quote": asdict(quote)})
                    return
                if path == "/v1/quotes":
                    if set(body) != {"quote", "signature"} or not isinstance(body["signature"], str):
                        raise ValueError("quote and hex signature are required")
                    try:
                        signature = bytes.fromhex(body["signature"])
                    except ValueError as exc:
                        raise ValueError("signature must be valid hex") from exc
                    quote = _strict_dataclass(OrderQuote, body["quote"])
                    self.server.coordinator.issue_quote(
                        quote, signature, self.server.verify_quote_signature
                    )
                    self._send(201, {"accepted": True, "orderId": quote.order_id, "status": "QUOTED"})
                    return
                if path == "/v1/expire-quotes":
                    if set(body) != {"order_id"} or not isinstance(body["order_id"], str) or not body["order_id"]:
                        raise ValueError("a non-empty order_id is required")
                    self.server.coordinator.expire_unfunded_quote(body["order_id"])
                    self._send(200, {"accepted": True, "orderId": body["order_id"], "status": "EXPIRED"})
                    return
                if path == "/v1/source-deposits":
                    if set(body) != {"evidence", "proof"}:
                        raise ValueError("evidence and proof are required")
                    evidence = _strict_dataclass(SourceDepositEvidence, body["evidence"])
                    self.server.coordinator.accept_source_deposit(
                        evidence, body["proof"], self.server.verify_source_deposit
                    )
                    self._send(200, {"accepted": True, "orderId": evidence.order_id, "status": "SOURCE_FUNDED"})
                    return
                if path == "/v1/destination-payouts":
                    if set(body) != {"evidence", "proof"}:
                        raise ValueError("evidence and proof are required")
                    evidence = _strict_dataclass(DestinationPayoutEvidence, body["evidence"])
                    self.server.coordinator.record_destination_payout(
                        evidence, body["proof"], self.server.verify_destination_payout
                    )
                    self._send(200, {"accepted": True, "orderId": evidence.order_id, "status": "DESTINATION_PAID"})
                    return
                self._send(404, {"error": "not found"})
            except OverflowError as exc:
                self._send(413, {"error": str(exc)})
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                self._send(400, {"error": str(exc)})
            except Exception as exc:
                # Do not disclose verifier, ledger, or internal exception details.
                LOG.warning("coordinator request rejected: %s", type(exc).__name__)
                self._send(422, {"error": "request was not accepted"})

        def do_GET(self) -> None:
            self._send(405, {"error": "method not allowed"})

        def do_PUT(self) -> None:
            self._send(405, {"error": "method not allowed"})

        def do_DELETE(self) -> None:
            self._send(405, {"error": "method not allowed"})

        def log_message(self, fmt: str, *args: Any) -> None:
            LOG.info("http %s", fmt % args)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.coordinator = coordinator
    server.verify_quote_signature = verify_quote_signature
    server.verify_source_deposit = verify_source_deposit
    server.verify_destination_payout = verify_destination_payout
    server.quote_pricer = quote_pricer
    return server
