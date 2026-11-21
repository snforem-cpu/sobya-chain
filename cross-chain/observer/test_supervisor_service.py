import json
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from supervisor_service import Monitor, create_server, make_handler


class Ready:
    network = "ethereum"
    ready = True
    checked_nodes = ("eth-a", "eth-b")
    failures = ()


class NotReady:
    network = "ethereum"
    ready = False
    checked_nodes = ("eth-a", "eth-b")
    failures = ("eth-b: NodeHealthError",)


class FakeSupervisor:
    def __init__(self, result=Ready()):
        self.result = result
    def all_ready(self):
        return (self.result,)


class ServiceTests(unittest.TestCase):
    def test_readiness_is_closed_before_first_snapshot(self):
        monitor = Monitor(FakeSupervisor())
        ready, payload = monitor.readiness("ethereum")
        self.assertFalse(ready)
        self.assertIn("no health check", payload["reason"])

    def test_ready_after_successful_refresh(self):
        monitor = Monitor(FakeSupervisor())
        monitor.refresh()
        ready, payload = monitor.readiness("ethereum")
        self.assertTrue(ready)
        self.assertEqual(payload["checkedNodes"], ["eth-a", "eth-b"])

    def test_failed_network_is_not_ready(self):
        monitor = Monitor(FakeSupervisor(NotReady()))
        monitor.refresh()
        ready, payload = monitor.readiness("ethereum")
        self.assertFalse(ready)
        self.assertEqual(payload["failures"], ["eth-b: NodeHealthError"])

    def test_stale_snapshot_fails_closed(self):
        monitor = Monitor(FakeSupervisor(), max_snapshot_age=0.01)
        monitor.refresh()
        time.sleep(0.02)
        ready, payload = monitor.readiness("ethereum")
        self.assertFalse(ready)
        self.assertEqual(payload["reason"], "health snapshot is stale")

    def test_unknown_network_fails_closed(self):
        monitor = Monitor(FakeSupervisor())
        monitor.refresh()
        ready, payload = monitor.readiness("tron")
        self.assertFalse(ready)
        self.assertEqual(payload["reason"], "network is not configured")

    def test_service_refuses_non_loopback_bind(self):
        monitor = Monitor(FakeSupervisor())
        with self.assertRaisesRegex(ValueError, "loopback only"):
            create_server("0.0.0.0", 8765, monitor)


    def test_admission_requires_source_and_destination_ready(self):
        class SobyaReady:
            network = "sobya"
            ready = True
            checked_nodes = ("sobya-a",)
            failures = ()
        class TronNotReady:
            network = "tron"
            ready = False
            checked_nodes = ("tron-a",)
            failures = ("tron-a: ProbeError",)
        class MultiSupervisor:
            def all_ready(self):
                return (SobyaReady(), TronNotReady())
        monitor = Monitor(MultiSupervisor())
        monitor.refresh()
        admissible, payload = monitor.admission("tron", "sobya")
        self.assertFalse(admissible)
        self.assertFalse(payload["admissible"])
        self.assertTrue(payload["destination"]["ready"])
        self.assertFalse(payload["source"]["ready"])

    def test_admission_is_closed_for_missing_destination(self):
        monitor = Monitor(FakeSupervisor())
        monitor.refresh()
        admissible, payload = monitor.admission("ethereum", "sobya")
        self.assertFalse(admissible)
        self.assertFalse(payload["destination"]["ready"])

    def test_http_ready_endpoint_and_method_rejection(self):
        monitor = Monitor(FakeSupervisor())
        monitor.refresh()
        server = create_server("127.0.0.1", 0, monitor)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
            conn.request("GET", "/ready?network=ethereum")
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(payload["ready"])
            conn.request("POST", "/ready?network=ethereum")
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 405)
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
