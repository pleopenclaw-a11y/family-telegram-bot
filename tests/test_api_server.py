import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import api_server
import board_service
import family_memory as store


def fake_deps(store_patch):
    """Build a dependency object that never touches a real 9arm endpoint."""
    calls = {"preview": [], "commit": []}

    def preview(client, text, *, extract=None):
        calls["preview"].append(text)
        return board_service.PreviewResult(
            text=text,
            action="save",
            kind="event",
            normalized_text="นัดหมอพรุ่งนี้ 10 โมง",
            confidence=0.95,
            question="",
        )

    def commit(group_id, *, kind, normalized_text, user_id=None, user_name=None, source_message_id=None):
        calls["commit"].append((group_id, normalized_text))
        return board_service.commit_capture(
            group_id, kind=kind, normalized_text=normalized_text,
            user_id=user_id, user_name=user_name, source_message_id=source_message_id,
        )

    return api_server.Dependencies(
        client=None,  # never used because preview is faked
        preview=preview,
        commit=commit,
        board=board_service.get_board,
    ), calls


class RouteUnitTests(unittest.TestCase):
    """Framework-free tests of the request dispatcher (no sockets)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "t.sqlite3")
        self.patch.start()
        self.deps, self.calls = fake_deps(self.patch)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_healthz(self):
        out = api_server.route("GET", "/api/healthz", {}, self.deps)
        self.assertEqual(out["status"], "ok")

    def test_board_endpoint_requires_group(self):
        with self.assertRaises(api_server.ApiError) as ctx:
            api_server.route("GET", "/api/board", {}, self.deps)
        self.assertEqual(ctx.exception.status, 400)

    def test_board_endpoint_returns_grouped_data(self):
        board_service.commit_capture("group-a", kind="task", normalized_text="ซื้อของ")
        out = api_server.route("GET", "/api/board?group=group-a", {}, self.deps)
        self.assertEqual(out["group"], "group-a")
        self.assertEqual(len(out["by_kind"]["task"]), 1)

    def test_preview_requires_text(self):
        with self.assertRaises(api_server.ApiError) as ctx:
            api_server.route("POST", "/api/capture/preview", {}, self.deps)
        self.assertEqual(ctx.exception.status, 400)

    def test_preview_returns_draft_and_does_not_commit(self):
        out = api_server.route(
            "POST", "/api/capture/preview", {"text": "พรุ่งนี้มีนัดหมอ 10 โมง"}, self.deps
        )
        self.assertEqual(out["action"], "save")
        self.assertEqual(out["normalized_text"], "นัดหมอพรุ่งนี้ 10 โมง")
        self.assertEqual(self.calls["preview"], ["พรุ่งนี้มีนัดหมอ 10 โมง"])
        self.assertEqual(self.calls["commit"], [])
        self.assertEqual(store.list_memories("group-a"), [])

    def test_commit_requires_group_and_normalized_text(self):
        with self.assertRaises(api_server.ApiError):
            api_server.route("POST", "/api/capture/commit", {"group": "a"}, self.deps)
        with self.assertRaises(api_server.ApiError):
            api_server.route("POST", "/api/capture/commit", {"normalized_text": "x"}, self.deps)

    def test_commit_persists(self):
        out = api_server.route(
            "POST", "/api/capture/commit",
            {"group": "group-a", "kind": "expense", "normalized_text": "ค่าอาหารแมว 450 บาท"},
            self.deps,
        )
        self.assertTrue(out["committed"])
        self.assertIsInstance(out["id"], int)
        self.assertEqual(len(store.search_memories("group-a", "อาหารแมว")), 1)

    def test_unknown_route_is_404(self):
        with self.assertRaises(api_server.ApiError) as ctx:
            api_server.route("GET", "/api/nope", {}, self.deps)
        self.assertEqual(ctx.exception.status, 404)


class SocketIntegrationTests(unittest.TestCase):
    """End-to-end over a real stdlib HTTP server on localhost."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "t.sqlite3")
        self.patch.start()
        self.deps, _ = fake_deps(self.patch)
        self.server = api_server.build_server(host="127.0.0.1", port=0, deps=self.deps)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.conn = HTTPConnection("127.0.0.1", self.port, timeout=5)

    def tearDown(self):
        self.conn.close()
        self.server.shutdown()
        self.server.server_close()
        self.patch.stop()
        self.tmp.cleanup()

    def test_round_trip_preview_then_commit_over_http(self):
        self.conn.request("GET", "/api/healthz")
        resp = self.conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(json.loads(resp.read())["status"], "ok")

        self.conn.request("POST", "/api/capture/preview", json.dumps({"text": "พรุ่งนี้มีนัดหมอ"}),
                          {"Content-Type": "application/json"})
        resp = self.conn.getresponse()
        body = json.loads(resp.read())
        self.assertEqual(resp.status, 200)
        self.assertEqual(body["kind"], "event")

        self.conn.request("POST", "/api/capture/commit",
                          json.dumps({"group": "group-a", "kind": "event",
                                      "normalized_text": body["normalized_text"]}),
                          {"Content-Type": "application/json"})
        resp = self.conn.getresponse()
        commit = json.loads(resp.read())
        self.assertEqual(resp.status, 200)
        self.assertTrue(commit["committed"])
        self.assertEqual(len(store.search_memories("group-a", "นัดหมอ")), 1)

    def test_error_response_over_http(self):
        self.conn.request("GET", "/api/board")
        resp = self.conn.getresponse()
        self.assertEqual(resp.status, 400)
        payload = json.loads(resp.read())
        self.assertIn("group", payload["error"])


if __name__ == "__main__":
    unittest.main()