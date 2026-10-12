from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any


class AgentShieldError(RuntimeError):
    pass


class AgentShieldClient:
    """Minimal MCP Streamable HTTP client with no runtime dependencies.

    The token is only sent in the Authorization header and is never included in
    exception text, tracing attributes, or serialized client state.
    """

    def __init__(self, endpoint: str | None = None, token: str | None = None, timeout: float = 30.0):
        endpoint = (endpoint or os.environ.get("AI_DLC_REMOTE_URL", "")).strip()
        if not endpoint:
            raise AgentShieldError("endpoint is required: pass endpoint=... or set AI_DLC_REMOTE_URL")
        self.endpoint = endpoint.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.session_id: str | None = None
        self._request_id = 0

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or {}}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "agentshield-python/3.2.0"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.session_id = response.headers.get("Mcp-Session-Id", self.session_id)
                content_type = response.headers.get("Content-Type", "")
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise AgentShieldError(f"AgentShield returned HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise AgentShieldError(f"AgentShield connection failed: {exc.reason}") from None
        if "text/event-stream" in content_type:
            payloads = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
            raw = payloads[-1] if payloads else "{}"
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            raise AgentShieldError("AgentShield returned an invalid JSON response") from None
        if envelope.get("error"):
            error = envelope["error"]
            raise AgentShieldError(f"MCP {error.get('code', 'error')}: {error.get('message', 'request failed')}")
        return envelope.get("result")

    def initialize(self) -> dict[str, Any]:
        result = self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "agentshield-python", "version": "3.2.0"}})
        return result or {}

    def list_tools(self) -> list[dict[str, Any]]:
        return (self._rpc("tools/list") or {}).get("tools", [])

    def call(self, tool: str, **arguments: Any) -> Any:
        result = self._rpc("tools/call", {"name": tool, "arguments": arguments}) or {}
        if result.get("isError"):
            text = " ".join(item.get("text", "") for item in result.get("content", []) if item.get("type") == "text")
            raise AgentShieldError(text or f"Tool {tool} failed")
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content", [])
        if len(content) == 1 and content[0].get("type") == "text":
            text = content[0].get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return content

    def route(self, task: str, project_id: str | None = None) -> Any:
        arguments: dict[str, Any] = {"task": task}
        if project_id:
            arguments["project_id"] = project_id
        return self.call("route_task", **arguments)

    def remember(self, *, kind: str, title: str, content: str, project_id: str | None = None, tags: list[str] | None = None) -> Any:
        return self.call("save_memory", kind=kind, title=title, content=content, project_id=project_id or "", tags=",".join(tags or []))

    def search(self, query: str, project_id: str | None = None, limit: int = 8) -> Any:
        return self.call("search_memory", query=query, project_id=project_id or "", limit=limit)

    def create_swarm(self, project_id: str, objective: str, tasks: list[dict[str, Any]], max_parallel: int = 4) -> Any:
        return self.call("create_swarm", project_id=project_id, objective=objective, tasks=tasks, max_parallel=max_parallel, idempotency_key=str(uuid.uuid4()))
