"""Local read-only HTTP readiness service for the SOBYA self-hosted supervisor.

Binds to loopback only. It never signs, broadcasts, accepts swap orders, or
changes escrow state. Order APIs must consult /ready and fail closed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from rpc_probes import supervisor_from_config

LOG = logging.getLogger("sobya.supervisor.service")


class Monitor:
    def __init__(self, supervisor: Any, *, max_snapshot_age: float = 15.0):
        if max_snapshot_age <= 0:
            raise ValueError("max_snapshot_age must be positive")
        self.supervisor = supervisor
        self.max_snapshot_age = max_snapshot_age
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] | None = None
        self._checked_at = 0.0

    def refresh(self) -> dict[str, Any]:
        results = self.supervisor.all_ready()
        snapshot = {
            "networks": {
                result.network: {
                    "ready": result.ready,
                    "checkedNodes": list(result.checked_nodes),
                    "failures": list(result.failures),
                }
                for result in results
            }
        }
        with self._lock:
            self._snapshot = snapshot
            self._checked_at = time.monotonic()
        return snapshot

    def snapshot(self) -> tuple[dict[str, Any] | None, float]:
        with self._lock:
            if self._snapshot is None:
                return None, float("inf")
            age = time.monotonic() - self._checked_at
            return json.loads(json.dumps(self._snapshot)), age


    def admission(self, source_network: str, destination_network: str = "sobya") -> tuple[bool, dict[str, Any]]:
        """Require both source and destination chains ready before new order admission."""
        source_ready, source = self.readiness(source_network)
        destination_ready, destination = self.readiness(destination_network)
        ready = source_ready and destination_ready
        return ready, {
            "admissible": ready,
            "source": source,
            "destination": destination,
        }

    def readiness(self, network: str) -> tuple[bool, dict[str, Any]]:
        snapshot, age = self.snapshot()
        if snapshot is None:
            return False, {"ready": False, "reason": "no health check has completed"}
        if age > self.max_snapshot_age:
            return False, {"ready": False, "reason": "health snapshot is stale"}
        state = snapshot["networks"].get(network)
        if state is None:
            return False, {"ready": False, "reason": "network is not configured"}
        return bool(state["ready"]), {
            "ready": bool(state["ready"]),
            "network": network,
            "checkedNodes": state["checkedNodes"],
            "failures": state["failures"],
            "snapshotAgeSeconds": round(age, 3),
        }


def make_handler(monitor: Monitor):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SOBYA-Supervisor"
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

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path == "/healthz":
                snapshot, age = monitor.snapshot()
                self._send(200, {
                    "ok": True,
                    "hasSnapshot": snapshot is not None,
                    "snapshotAgeSeconds": None if snapshot is None else round(age, 3),
                })
                return

            if parsed.path == "/admission":
                query = parse_qs(parsed.query, strict_parsing=False)
                source_values = query.get("source", [])
                destination_values = query.get("destination", ["sobya"])
                if len(source_values) != 1 or len(destination_values) != 1:
                    self._send(400, {"admissible": False, "reason": "exactly one source and destination are required"})
                    return
                admissible, payload = monitor.admission(source_values[0], destination_values[0])
                self._send(200 if admissible else 503, payload)
                return
            if parsed.path == "/ready":
                query = parse_qs(parsed.query, strict_parsing=False)
                network_values = query.get("network", [])
                if len(network_values) != 1 or not network_values[0].strip():
                    self._send(400, {"ready": False, "reason": "exactly one network query parameter is required"})
                    return
                ready, payload = monitor.readiness(network_values[0])
                self._send(200 if ready else 503, payload)
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            self._send(405, {"error": "method not allowed"})

        def log_message(self, fmt: str, *args: Any) -> None:
            LOG.info("http %s", fmt % args)

    return Handler


def create_server(host: str, port: int, monitor: Monitor) -> ThreadingHTTPServer:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("service bind host must be a literal loopback IP") from exc
    if not address.is_loopback:
        raise ValueError("service must bind to loopback only")
    if not 0 <= port <= 65535:
        raise ValueError("invalid service port")
    return ThreadingHTTPServer((host, port), make_handler(monitor))


def load_config(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    config = json.loads(raw)
    if not isinstance(config, dict):
        raise ValueError("supervisor config must be a JSON object")
    return config


def run(config_path: str, *, host: str = "127.0.0.1", port: int = 8765,
        interval: float = 5.0, max_snapshot_age: float = 15.0) -> None:
    if interval <= 0:
        raise ValueError("poll interval must be positive")
    supervisor = supervisor_from_config(load_config(config_path))
    monitor = Monitor(supervisor, max_snapshot_age=max_snapshot_age)
    server = create_server(host, port, monitor)
    stop = threading.Event()

    def poll() -> None:
        while not stop.is_set():
            try:
                monitor.refresh()
            except Exception as exc:
                # Do not preserve an old healthy snapshot after a probe failure.
                LOG.error("supervisor refresh failed: %s", type(exc).__name__)
                with monitor._lock:
                    monitor._snapshot = None
                    monitor._checked_at = 0.0
            stop.wait(interval)

    worker = threading.Thread(target=poll, name="sobya-node-health-poller", daemon=True)
    worker.start()
    LOG.info("readiness service listening on %s:%s", host, server.server_address[1])
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=interval + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SOBYA self-hosted read-only node readiness service")
    parser.add_argument("--config", required=True, help="path to self-hosted-nodes JSON config")
    parser.add_argument("--host", default="127.0.0.1", help="loopback bind IP only")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--max-snapshot-age", type=float, default=15.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.config, host=args.host, port=args.port, interval=args.interval,
        max_snapshot_age=args.max_snapshot_age)


if __name__ == "__main__":
    main()
