from __future__ import annotations

import json
import hmac
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ENABLE_FEDERATION
from .store import MemoryStore


class ControlPlaneHandler(BaseHTTPRequestHandler):
    server_version = "AgentShieldMissionControl/3.0"

    def _authorized(self) -> bool:
        expected = self.server.access_token  # type: ignore[attr-defined]
        supplied = self.headers.get("Authorization", "")
        return not expected or hmac.compare_digest(supplied, f"Bearer {expected}")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dashboard(self) -> None:
        body = self.server.dashboard.read_bytes()  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_allowed(self) -> bool:
        """Block DNS-rebinding: on a loopback bind only loopback Host headers are accepted."""
        if not getattr(self.server, "loopback_only", False):  # type: ignore[attr-defined]
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in {"127.0.0.1", "localhost", "::1"}

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._json(421, {"error": "host_not_allowed"})
            return
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._dashboard()
            return
        if path == "/healthz":
            self._json(200, {"status": "ok", "service": "ai-dlc-mission-control"})
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        store: MemoryStore = self.server.store  # type: ignore[attr-defined]
        if path == "/api/overview":
            with store._connect() as conn:
                swarms = {row["status"]: row["count"] for row in conn.execute("SELECT status,COUNT(*) count FROM swarm_runs WHERE workspace_id=? GROUP BY status", (store.workspace_id,))}
                nodes = {row["status"]: row["count"] for row in conn.execute("SELECT status,COUNT(*) count FROM federation_nodes WHERE workspace_id=? GROUP BY status", (store.workspace_id,))}
            stats = store.stats()
            safe_memory = {key: value for key, value in stats.items() if key not in {"db_path", "workspace_id"}}
            self._json(200, {"memory": safe_memory, "swarms": swarms, "federation": nodes})
        elif path == "/api/swarms":
            with store._connect() as conn:
                rows = conn.execute("SELECT id,project_id,objective,status,max_parallel,created_at,updated_at FROM swarm_runs WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100", (store.workspace_id,)).fetchall()
            self._json(200, [dict(row) for row in rows])
        elif path == "/api/federation/nodes":
            with store._connect() as conn:
                rows = conn.execute("SELECT id,name,endpoint,capabilities_json,status,last_seen_at FROM federation_nodes WHERE workspace_id=? ORDER BY name", (store.workspace_id,)).fetchall()
            self._json(200, [dict(row) for row in rows])
        elif path == "/api/marketplace":
            self._json(200, store.list_marketplace_items())
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self._json(421, {"error": "host_not_allowed"})
            return
        path = urlparse(self.path).path
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        swarm_action = re.fullmatch(r"/api/swarms/([A-Za-z0-9_-]{1,128})/(pause|resume|cancel)", path)
        if swarm_action:
            origin = self.headers.get("Origin")
            expected_origin = f"http://{self.headers.get('Host')}"
            if origin and origin != expected_origin:
                self._json(403, {"error": "origin_not_allowed"})
                return
            if "application/json" not in self.headers.get("Content-Type", "").lower():
                self._json(415, {"error": "content_type_must_be_json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16_384:
                    raise ValueError("invalid payload length")
                payload = json.loads(self.rfile.read(length))
                result = self.server.store.set_swarm_state(swarm_action.group(1), swarm_action.group(2), str(payload.get("reason") or "Mission Control operator"))  # type: ignore[attr-defined]
                self._json(200, result)
            except KeyError:
                self._json(404, {"error": "swarm_not_found"})
            except (ValueError, json.JSONDecodeError, TypeError):
                self._json(409, {"error": "invalid_swarm_transition"})
            return
        if path != "/api/federation/inbox" or not ENABLE_FEDERATION:
            self._json(404, {"error": "not_found"})
            return
        secret = os.getenv("AGENTSHIELD_FEDERATION_SECRET", "")
        if len(secret) < 32:
            self._json(503, {"error": "federation_not_configured"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_048_576:
                raise ValueError("invalid payload length")
            payload = json.loads(self.rfile.read(length))
            result = self.server.store.accept_federation_message(payload, secret)  # type: ignore[attr-defined]
            self._json(202, result)
        except PermissionError as exc:
            self._json(403, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError, KeyError, TypeError):
            self._json(400, {"error": "invalid_federation_envelope"})

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.getenv("AGENTSHIELD_HTTP_LOG", "0") == "1":
            super().log_message(fmt, *args)


def serve_control_plane(store: MemoryStore, host: str, port: int, dashboard: Path, access_token: str | None = None) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and not access_token:
        raise ValueError("AGENTSHIELD_CONTROL_TOKEN is required when binding beyond loopback")
    server = ThreadingHTTPServer((host, port), ControlPlaneHandler)
    server.store = store  # type: ignore[attr-defined]
    server.dashboard = dashboard  # type: ignore[attr-defined]
    server.access_token = access_token  # type: ignore[attr-defined]
    server.loopback_only = host in {"127.0.0.1", "localhost", "::1"}  # type: ignore[attr-defined]
    print(f"AgentShield Mission Control: http://{host}:{port}")
    server.serve_forever()
