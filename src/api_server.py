"""Track C — minimal local HTTP API for the Family Board and Telegram.

A small, studiable HTTP boundary implemented on the Python standard library
(``http.server``) so no new third-party dependency is required in the current
environment. FastAPI/Flask can replace this later without changing the service
layer in :mod:`board_service`.

Endpoints (JSON only):

- ``GET  /api/healthz``            -> ``{"status": "ok"}``
- ``GET  /api/board?group=<id>``    -> grouped board view (read-only)
- ``POST /api/capture/preview``     -> AI capture draft, NO persistence
- ``POST /api/capture/commit``      -> persist an explicitly confirmed capture

Credentials stay server-side
----------------------------
The 9arm API key is consumed only inside ``preview`` via the injected
:class:`~ninearm_client.NineArmClient`. No endpoint ever returns an API key; the
browser/Family Board never sees one. In production the server should be bound to
localhost or behind an authenticated proxy and called by a backend Telegram
worker, never exposed broadly.

Run::

    PYTHONPATH=src ./.venv/bin/python -m api_server            # binds 127.0.0.1:8787
    PYTHONPATH=src ./.venv/bin/python api_server.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board_service
from config import load_settings
from extractor import extract_message
from ninearm_client import NineArmClient


@dataclass(frozen=True)
class Dependencies:
    """Injected service boundary so tests can run without credentials/network."""

    client: NineArmClient
    preview: Callable[..., board_service.PreviewResult]
    commit: Callable[..., board_service.CommitResult]
    board: Callable[..., dict[str, Any]]


def route(method: str, path: str, body: dict[str, Any], deps: Dependencies) -> dict[str, Any]:
    """Pure dispatcher: maps an HTTP method+path to a service call.

    Kept framework-free so it can be unit-tested directly (no sockets), and so
    the same contract can later be wrapped by telegram or an ASGI app.
    """
    path_only = path.split("?", 1)[0].rstrip("/") or "/"

    if method == "GET" and path_only == "/api/healthz":
        return {"ok": True, "status": "ok"}

    if method == "GET" and path_only == "/api/board":
        qs = path.split("?", 1)[1] if "?" in path else ""
        params = _parse_query(qs)
        group = params.get("group", "")
        if not group:
            raise ApiError(400, "Missing required query param: group")
        return deps.board(group_id=group)

    if method == "POST" and path_only == "/api/capture/preview":
        text = str(body.get("text", "")).strip()
        if not text:
            raise ApiError(400, "Missing required field: text")
        return deps.preview(client=deps.client, text=text).to_dict()

    if method == "POST" and path_only == "/api/capture/commit":
        group = str(body.get("group", "")).strip()
        normalized_text = str(body.get("normalized_text", "")).strip()
        if not group or not normalized_text:
            raise ApiError(400, "Requires fields: group, normalized_text")
        result = deps.commit(
            group,
            kind=str(body.get("kind", "note")),
            normalized_text=normalized_text,
            user_id=body.get("user_id"),
            user_name=body.get("user_name"),
            source_message_id=body.get("source_message_id"),
        )
        return {"committed": True, **result.to_dict()}

    raise ApiError(404, f"Not found: {method} {path_only}")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _parse_query(qs: str) -> dict[str, str]:
    from urllib.parse import parse_qs

    return {k: v[0] for k, v in parse_qs(qs).items()}


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "FamilyBoardAPI/0.1"

    def _deps(self) -> Dependencies:
        deps = getattr(self.server, "deps", None)  # type: ignore[attr-defined]
        if deps is None:
            deps = build_default_dependencies()
        return deps

    def _send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        origin = self.headers.get("Origin")
        allowed_origin = getattr(self.server, "allowed_origin", "")  # type: ignore[attr-defined]
        if origin and allowed_origin and origin == allowed_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Request body must be valid JSON")
        return parsed if isinstance(parsed, dict) else {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204, "")

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def _handle(self, method: str) -> None:
        try:
            if method != "OPTIONS" and not self._authorized():
                self._send_json(401, {"error": "Unauthorized"})
                return
            body = self._read_body() if method == "POST" else {}
            payload = route(method, self.path, body, self._deps())
            self._send_json(200, payload)
        except ApiError as exc:
            self._send_json(exc.status, {"error": exc.message})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"Internal server error: {type(exc).__name__}"})

    def _authorized(self) -> bool:
        if self.path.split("?", 1)[0].rstrip("/") == "/api/healthz":
            return True
        expected = getattr(self.server, "api_token", "")  # type: ignore[attr-defined]
        if not expected:
            return True
        supplied = self.headers.get("Authorization", "")
        return supplied == f"Bearer {expected}"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep stdout clean; silence default request logging.
        pass


def build_default_dependencies() -> Dependencies:
    settings = load_settings()
    client = NineArmClient(
        settings.ninearm_base_url,
        settings.ninearm_api_key,
        settings.primary_model,
        settings.fallback_model,
    )
    return Dependencies(
        client=client,
        preview=board_service.preview_capture,
        commit=board_service.commit_capture,
        board=board_service.get_board,
    )


def build_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    deps: Dependencies | None = None,
) -> ThreadingHTTPServer:
    dependencies = deps or build_default_dependencies()
    server = ThreadingHTTPServer((host, port), ApiHandler)
    server.deps = dependencies  # type: ignore[attr-defined]
    settings = load_settings()
    server.api_token = settings.family_board_api_token  # type: ignore[attr-defined]
    server.allowed_origin = settings.family_board_allowed_origin  # type: ignore[attr-defined]
    return server


def main() -> None:
    settings = load_settings()
    server = build_server()
    host, port = server.server_address[:2]
    print(f"Family Board API listening on http://{host}:{port}")
    # The 9arm key stays server-side; nothing is printed here.
    if not settings.ninearm_api_key:
        print("WARNING: NINEARM_API_KEY is empty; /api/capture/preview will fail until it is set.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
