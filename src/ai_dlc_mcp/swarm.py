from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ._store_base import uid, utcnow
from .security import ValidationError, assert_no_secrets, clean_text


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SwarmRuntimeMixin:
    def create_swarm(self, project_id: str, objective: str, tasks: list[dict[str, Any]], max_parallel: int = 4, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        objective = clean_text(objective, "objective", 2_000, required=True)
        if not tasks or len(tasks) > 500:
            raise ValidationError("between 1 and 500 tasks are required")
        assert_no_secrets({"objective": objective, "tasks": _json(tasks), "metadata": _json(metadata or {})})
        project_id = self.ensure_project(project_id)["id"]
        swarm_id, now = uid("swarm"), utcnow()
        task_ids = [str(task.get("id") or uid("task")) for task in tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("task ids must be unique")
        valid_ids = set(task_ids)
        graph = {task_id: [str(value) for value in task.get("depends_on", [])] for task_id, task in zip(task_ids, tasks, strict=True)}
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("task dependency graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                if dependency not in valid_ids or dependency == node:
                    raise ValueError(f"invalid dependency graph for {node}")
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
        for task_id in task_ids:
            visit(task_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO swarm_runs(id,workspace_id,project_id,objective,status,max_parallel,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (swarm_id, self.workspace_id, project_id, objective, "created", max(1, min(int(max_parallel), 64)), _json(metadata or {}), now, now),
            )
            for task_id, task in zip(task_ids, tasks, strict=True):
                dependencies = [str(value) for value in task.get("depends_on", [])]
                conn.execute(
                    """INSERT INTO swarm_tasks(id,swarm_id,agent_name,title,input_json,status,depends_on_json,created_at,updated_at)
                       VALUES(?,?,?,?,?,'queued',?,?,?)""",
                    (task_id, swarm_id, str(task.get("agent") or "general"), str(task.get("title") or task_id), _json(task.get("input") or {}), _json(dependencies), now, now),
                )
            conn.execute("UPDATE swarm_runs SET status='running',updated_at=? WHERE id=?", (now, swarm_id))
            self._audit(conn, "swarm.created", "swarm", swarm_id, {"project_id": project_id, "tasks": len(tasks), "max_parallel": max_parallel})
        return self.get_swarm(swarm_id)

    def get_swarm(self, swarm_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            run = conn.execute("SELECT * FROM swarm_runs WHERE id=? AND workspace_id=?", (swarm_id, self.workspace_id)).fetchone()
            if not run:
                raise KeyError(f"Swarm not found: {swarm_id}")
            tasks = conn.execute("SELECT * FROM swarm_tasks WHERE swarm_id=? ORDER BY created_at,id", (swarm_id,)).fetchall()
        result = dict(run)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        result["tasks"] = []
        for row in tasks:
            item = dict(row)
            item["input"] = json.loads(item.pop("input_json"))
            item["output"] = json.loads(item.pop("output_json")) if item.get("output_json") else None
            item["depends_on"] = json.loads(item.pop("depends_on_json"))
            result["tasks"].append(item)
        return result

    def set_swarm_state(self, swarm_id: str, action: str, reason: str = "") -> dict[str, Any]:
        transitions = {"pause": ("paused", {"running"}), "resume": ("running", {"paused"}), "cancel": ("cancelled", {"created", "running", "paused"})}
        if action not in transitions:
            raise ValueError("action must be pause, resume, or cancel")
        target, allowed = transitions[action]
        with self._connect() as conn:
            now = utcnow()
            run = conn.execute("SELECT * FROM swarm_runs WHERE id=? AND workspace_id=?", (swarm_id, self.workspace_id)).fetchone()
            if not run:
                raise KeyError(f"Swarm not found: {swarm_id}")
            if run["status"] not in allowed:
                raise ValueError(f"cannot {action} swarm in {run['status']} state")
            conn.execute("UPDATE swarm_runs SET status=?,updated_at=?,completed_at=? WHERE id=?", (target, now, now if target == "cancelled" else None, swarm_id))
            if action == "pause":
                conn.execute("UPDATE swarm_tasks SET status='paused',updated_at=? WHERE swarm_id=? AND status IN ('queued','leased','running')", (now, swarm_id))
            elif action == "resume":
                conn.execute("UPDATE swarm_tasks SET status='queued',lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE swarm_id=? AND status='paused'", (now, swarm_id))
            else:
                conn.execute("UPDATE swarm_tasks SET status='cancelled',lease_owner=NULL,lease_expires_at=NULL,updated_at=?,completed_at=? WHERE swarm_id=? AND status NOT IN ('completed','failed','cancelled')", (now, now, swarm_id))
            self._audit(conn, f"swarm.{action}d" if action != "pause" else "swarm.paused", "swarm", swarm_id, {"reason": reason})
        return self.get_swarm(swarm_id)

    def claim_swarm_task(self, swarm_id: str, worker_id: str, lease_seconds: int = 300) -> dict[str, Any] | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        with self._connect() as conn:
            now_dt = datetime.now(timezone.utc)
            now, expires = now_dt.isoformat(timespec="seconds"), (now_dt + timedelta(seconds=max(30, min(lease_seconds, 3600)))).isoformat(timespec="seconds")
            run = conn.execute("SELECT status,max_parallel FROM swarm_runs WHERE id=? AND workspace_id=?", (swarm_id, self.workspace_id)).fetchone()
            if not run or run["status"] != "running":
                return None
            conn.execute("UPDATE swarm_tasks SET status='queued',lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE swarm_id=? AND status IN ('leased','running') AND lease_expires_at<=?", (now, swarm_id, now))
            active = conn.execute("SELECT COUNT(*) FROM swarm_tasks WHERE swarm_id=? AND status IN ('leased','running')", (swarm_id,)).fetchone()[0]
            if active >= run["max_parallel"]:
                return None
            rows = conn.execute("SELECT * FROM swarm_tasks WHERE swarm_id=? AND status='queued' ORDER BY created_at,id", (swarm_id,)).fetchall()
            selected = None
            for row in rows:
                dependencies = json.loads(row["depends_on_json"])
                if not dependencies:
                    selected = row
                    break
                placeholders = ",".join("?" for _ in dependencies)
                complete = conn.execute(f"SELECT COUNT(*) FROM swarm_tasks WHERE swarm_id=? AND id IN ({placeholders}) AND status='completed'", [swarm_id, *dependencies]).fetchone()[0]
                if complete == len(dependencies):
                    selected = row
                    break
            if not selected:
                return None
            conn.execute("UPDATE swarm_tasks SET status='leased',lease_owner=?,lease_expires_at=?,attempt=attempt+1,updated_at=? WHERE id=? AND status='queued'", (worker_id, expires, now, selected["id"]))
            claimed = conn.execute("SELECT * FROM swarm_tasks WHERE id=?", (selected["id"],)).fetchone()
            self._audit(conn, "swarm.task_claimed", "swarm_task", selected["id"], {"swarm_id": swarm_id, "worker_id": worker_id, "lease_expires_at": expires})
        return dict(claimed) if claimed else None

    def complete_swarm_task(self, task_id: str, worker_id: str, output: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
        target = "failed" if error else "completed"
        with self._connect() as conn:
            now = utcnow()
            task = conn.execute(
                """SELECT t.* FROM swarm_tasks t JOIN swarm_runs s ON s.id=t.swarm_id
                   WHERE t.id=? AND s.workspace_id=? AND s.status='running'""",
                (task_id, self.workspace_id),
            ).fetchone()
            if (not task or task["lease_owner"] != worker_id
                    or task["status"] not in {"leased", "running"}
                    or not task["lease_expires_at"] or task["lease_expires_at"] <= now):
                raise PermissionError("task lease is not owned, active, or unexpired")
            conn.execute("UPDATE swarm_tasks SET status=?,output_json=?,error=?,lease_owner=NULL,lease_expires_at=NULL,updated_at=?,completed_at=? WHERE id=?", (target, _json(output or {}), error or None, now, now, task_id))
            if error:
                conn.execute("UPDATE swarm_tasks SET status='cancelled',error='dependency failed',lease_owner=NULL,lease_expires_at=NULL,updated_at=?,completed_at=? WHERE swarm_id=? AND status NOT IN ('completed','failed','cancelled')", (now, now, task["swarm_id"]))
            remaining = conn.execute("SELECT COUNT(*) FROM swarm_tasks WHERE swarm_id=? AND status NOT IN ('completed','failed','cancelled')", (task["swarm_id"],)).fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM swarm_tasks WHERE swarm_id=? AND status='failed'", (task["swarm_id"],)).fetchone()[0]
            if remaining == 0:
                conn.execute("UPDATE swarm_runs SET status=?,updated_at=?,completed_at=? WHERE id=?", ("failed" if failed else "completed", now, now, task["swarm_id"]))
            self._audit(conn, f"swarm.task_{target}", "swarm_task", task_id, {"swarm_id": task["swarm_id"], "worker_id": worker_id})
            result = conn.execute("SELECT * FROM swarm_tasks WHERE id=?", (task_id,)).fetchone()
        return dict(result)

    def create_task_worktree(self, task_id: str, repository: str, base_ref: str = "HEAD", root: str | None = None) -> dict[str, str]:
        with self._connect() as conn:
            task = conn.execute(
                """SELECT t.* FROM swarm_tasks t JOIN swarm_runs s ON s.id=t.swarm_id
                   WHERE t.id=? AND s.workspace_id=?""",
                (task_id, self.workspace_id),
            ).fetchone()
            if not task:
                raise KeyError(f"Task not found: {task_id}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/~^@{}-]{0,199}", base_ref or "") or ".." in base_ref:
            raise ValidationError("base_ref must be a plain git revision (no options or ranges)")
        repo = Path(repository).resolve()
        if not (repo / ".git").exists() and not subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], capture_output=True).returncode == 0:
            raise ValueError("repository must be a Git worktree")
        safe_task = re.sub(r"[^a-zA-Z0-9_-]+", "-", task_id).strip("-")[:48]
        target_root = Path(root).resolve() if root else repo / ".agentshield" / "worktrees"
        target_root.mkdir(parents=True, exist_ok=True)
        target = (target_root / safe_task).resolve()
        if target_root not in target.parents:
            raise ValueError("worktree target escapes configured root")
        branch = f"agentshield/{task['swarm_id']}/{safe_task}"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(target), base_ref], check=True, capture_output=True, text=True)
        with self._connect() as conn:
            conn.execute("UPDATE swarm_tasks SET worktree_path=?,updated_at=? WHERE id=?", (str(target), utcnow(), task_id))
            self._audit(conn, "swarm.worktree_created", "swarm_task", task_id, {"path": str(target), "branch": branch})
        return {"task_id": task_id, "path": str(target), "branch": branch}

    def register_federation_node(self, node_id: str, name: str, endpoint: str, public_key_id: str, capabilities: list[str] | None = None) -> dict[str, Any]:
        try:
            parsed = urllib.parse.urlsplit(endpoint)
            host = parsed.hostname
            _ = parsed.port  # Reject malformed ports before persisting the endpoint.
        except ValueError:
            raise ValueError("invalid federation endpoint") from None
        if (
            not host
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"})
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(char.isspace() or ord(char) < 32 for char in endpoint)
        ):
            raise ValueError("federation endpoint must use HTTPS except on loopback")
        now = utcnow()
        with self._connect() as conn:
            result = conn.execute("""INSERT INTO federation_nodes(id,workspace_id,name,endpoint,public_key_id,capabilities_json,status,last_seen_at,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,'active',?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,endpoint=excluded.endpoint,
                            public_key_id=excluded.public_key_id,capabilities_json=excluded.capabilities_json,status='active',last_seen_at=excluded.last_seen_at,updated_at=excluded.updated_at
                            WHERE federation_nodes.workspace_id=excluded.workspace_id""",
                         (node_id, self.workspace_id, name, endpoint.rstrip("/"), public_key_id, _json(capabilities or []), now, now, now))
            if result.rowcount != 1:
                raise PermissionError("federation node is not available")
            row = conn.execute("SELECT * FROM federation_nodes WHERE id=? AND workspace_id=?", (node_id, self.workspace_id)).fetchone()
        return dict(row)

    def create_federation_message(self, source_node_id: str, target_node_id: str, message_type: str, payload: dict[str, Any], shared_secret: str) -> dict[str, Any]:
        if len(shared_secret) < 32:
            raise ValueError("shared_secret must contain at least 32 characters")
        if not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,127}", message_type):
            raise ValueError("invalid federation message type")
        assert_no_secrets({"payload": _json(payload)})
        if len(_json(payload).encode("utf-8")) > 524_288:
            raise ValueError("federation payload exceeds 512 KiB")
        message_id, nonce, now = uid("msg"), secrets.token_hex(16), utcnow()
        canonical = _json({"id": message_id, "source": source_node_id, "target": target_node_id, "type": message_type, "payload": payload, "nonce": nonce, "created_at": now})
        signature = hmac.new(shared_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        with self._connect() as conn:
            conn.execute("INSERT INTO federation_messages(id,workspace_id,source_node_id,target_node_id,message_type,payload_json,nonce,signature,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (message_id, self.workspace_id, source_node_id, target_node_id, message_type, _json(payload), nonce, signature, "pending", now))
        return {"id": message_id, "source": source_node_id, "target": target_node_id, "type": message_type, "payload": payload, "nonce": nonce, "signature": signature, "created_at": now}

    @staticmethod
    def verify_federation_message(message: dict[str, Any], shared_secret: str) -> bool:
        signature = str(message.get("signature") or "")
        unsigned = {key: message[key] for key in ("id", "source", "target", "type", "payload", "nonce", "created_at")}
        expected = hmac.new(shared_secret.encode(), _json(unsigned).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def accept_federation_message(self, message: dict[str, Any], shared_secret: str) -> dict[str, Any]:
        if not self.verify_federation_message(message, shared_secret):
            raise PermissionError("invalid federation signature")
        try:
            created_at = datetime.fromisoformat(str(message["created_at"]).replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = abs((datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds())
        except (KeyError, ValueError):
            raise PermissionError("invalid federation timestamp") from None
        if age > 900:
            raise PermissionError("expired federation message")
        with self._connect() as conn:
            source = conn.execute("SELECT id FROM federation_nodes WHERE id=? AND workspace_id=? AND status='active'", (message.get("source"), self.workspace_id)).fetchone()
            target = conn.execute("SELECT id FROM federation_nodes WHERE id=? AND workspace_id=? AND status='active'", (message.get("target"), self.workspace_id)).fetchone()
            if not source or not target:
                raise PermissionError("federation node is unknown or inactive")
            try:
                conn.execute("INSERT INTO federation_messages(id,workspace_id,source_node_id,target_node_id,message_type,payload_json,nonce,signature,status,created_at,delivered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                             (message["id"], self.workspace_id, message["source"], message["target"], message["type"], _json(message["payload"]), message["nonce"], message["signature"], "delivered", message["created_at"], utcnow()))
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    raise PermissionError("federation replay rejected") from None
                raise
            self._audit(conn, "federation.message_received", "federation_message", message["id"], {"source": message["source"], "target": message["target"], "type": message["type"]})
        return {"id": message["id"], "status": "delivered"}

    def dispatch_federation_message(self, message_id: str, shared_secret: str, access_token: str | None = None, timeout: float = 15.0) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT m.*,n.endpoint FROM federation_messages m JOIN federation_nodes n ON n.id=m.target_node_id WHERE m.id=? AND m.workspace_id=?", (message_id, self.workspace_id)).fetchone()
            if not row:
                raise KeyError(f"Federation message not found: {message_id}")
        message = {"id": row["id"], "source": row["source_node_id"], "target": row["target_node_id"], "type": row["message_type"], "payload": json.loads(row["payload_json"]), "nonce": row["nonce"], "signature": row["signature"], "created_at": row["created_at"]}
        if not self.verify_federation_message(message, shared_secret):
            raise PermissionError("local federation message signature is invalid")
        headers = {"Content-Type": "application/json", "User-Agent": "AgentShield-Federation/3.0"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        request = urllib.request.Request(f"{row['endpoint']}/api/federation/inbox", data=_json(message).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode())
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            with self._connect() as conn:
                conn.execute("UPDATE federation_messages SET status='failed' WHERE id=?", (message_id,))
            raise RuntimeError(f"federation delivery failed: {type(exc).__name__}") from None
        with self._connect() as conn:
            conn.execute("UPDATE federation_messages SET status='delivered',delivered_at=? WHERE id=?", (utcnow(), message_id))
        return result

    def publish_marketplace_item(self, kind: str, name: str, version: str, description: str, manifest: dict[str, Any], publisher: str, verified: bool = False) -> dict[str, Any]:
        if kind not in {"plugin", "agent", "workflow"} or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,127}", name):
            raise ValueError("invalid marketplace kind or name")
        checksum = hashlib.sha256(_json(manifest).encode()).hexdigest()
        item_id = "market:" + hashlib.sha256(_json([self.workspace_id, kind, name, version]).encode()).hexdigest()
        now = utcnow()
        with self._connect() as conn:
            conn.execute("""INSERT INTO marketplace_items(id,workspace_id,kind,name,version,description,manifest_json,checksum,publisher,verified,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(workspace_id,kind,name,version) DO UPDATE SET description=excluded.description,
                            manifest_json=excluded.manifest_json,checksum=excluded.checksum,publisher=excluded.publisher,verified=excluded.verified,updated_at=excluded.updated_at""",
                         (item_id, self.workspace_id, kind, name, version, description, _json(manifest), checksum, publisher, int(verified), now, now))
            row = conn.execute("SELECT * FROM marketplace_items WHERE workspace_id=? AND kind=? AND name=? AND version=?",
                               (self.workspace_id, kind, name, version)).fetchone()
        return dict(row)

    def list_marketplace_items(self, kind: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if kind:
                rows = conn.execute("SELECT * FROM marketplace_items WHERE workspace_id=? AND kind=? ORDER BY name,version DESC", (self.workspace_id, kind)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM marketplace_items WHERE workspace_id=? ORDER BY kind,name,version DESC", (self.workspace_id,)).fetchall()
        return [dict(row) for row in rows]
