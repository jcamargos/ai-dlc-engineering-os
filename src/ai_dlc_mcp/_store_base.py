"""SQLite persistence for AI-DLC Engineering OS engineering memory.

Design notes
- One short-lived connection per operation (opened, committed/rolled back, closed).
  Several MCP hosts (Codex, Claude Code, Cursor) may run the server concurrently
  against the same file; WAL + busy_timeout + BEGIN IMMEDIATE for migrations.
- Schema is versioned with PRAGMA user_version and migrated forward in place,
  never destructively. Version 0 is the original v2.0.0 schema.
- Full-text search uses FTS5/BM25 when available, with a portable fallback.
- Only searchable state is indexed: superseded memories, rejected learnings and
  non-approved rules never reach retrieval.
- Audit payloads hold identifiers and enums only, never free text, so a purge
  really removes the content.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import (
    MAX_TEXT,
    MAX_TITLE,
    ValidationError,
    assert_no_secrets,
    clean_text,
    normalize_project_id,
)

log = logging.getLogger("ai_dlc_mcp.store")

SCHEMA_VERSION = 2
GLOBAL = ""  # project_id value used in the search index for global memory

ENTITY_TABLES = {
    "memory": "memories",
    "decision": "decisions",
    "learning": "learnings",
    "rule": "rules",
    "incident": "incidents",
    "outcome": "task_outcomes",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


_TOKEN_RE = re.compile(r"[\w][\w\-\.]*", re.UNICODE)


def _tokens(text: str) -> list[str]:
    seen: list[str] = []
    for t in _TOKEN_RE.findall((text or "").lower()):
        t = t.strip("-.")
        if len(t) > 1 and t not in seen:
            seen.append(t)
    return seen


def _overlap_score(query: str, text: str) -> float:
    q = set(_tokens(query))
    if not q:
        return 0.0
    hay = (text or "").lower()
    return len(q & set(_tokens(hay))) / len(q) + (1.0 if query.lower().strip() in hay else 0.0)


def _clip(text: str | None, limit: int = 1800) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _flags(row: sqlite3.Row) -> list[str]:
    try:
        return json.loads(row["flags_json"] or "[]")
    except (KeyError, IndexError, json.JSONDecodeError):
        return []


@dataclass
class MemoryHit:
    type: str
    id: str
    title: str
    content: str
    project_id: str | None
    score: float
    metadata: dict[str, Any]


# --------------------------------------------------------------------------- base schema (v2.0.0 == user_version 0)
BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL, repo_path TEXT, summary TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id));
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT, scope TEXT NOT NULL CHECK(scope IN ('global','project')),
  kind TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, tags_json TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.8, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded')),
  source TEXT, evidence TEXT, superseded_reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, title TEXT NOT NULL, context TEXT NOT NULL,
  decision TEXT NOT NULL, alternatives TEXT, consequences TEXT, status TEXT NOT NULL DEFAULT 'accepted', created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS learnings (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, category TEXT NOT NULL, problem TEXT NOT NULL,
  root_cause TEXT, solution TEXT NOT NULL, rule_candidate TEXT, evidence TEXT, confidence REAL NOT NULL DEFAULT 0.7,
  status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','verified','rejected')), created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS rules (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT, agent_name TEXT NOT NULL, rule_text TEXT NOT NULL,
  rationale TEXT NOT NULL, source_learning_id TEXT, status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','approved','rejected')),
  reviewer TEXT, review_notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(source_learning_id) REFERENCES learnings(id));
CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, severity TEXT NOT NULL, summary TEXT NOT NULL,
  impact TEXT, root_cause TEXT, remediation TEXT, prevention TEXT, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS task_outcomes (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, task TEXT NOT NULL, outcome TEXT NOT NULL,
  what_worked TEXT, what_failed TEXT, reusable_lessons TEXT, evidence TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS agent_eval_cases (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, agent_name TEXT NOT NULL,
          name TEXT NOT NULL, task TEXT NOT NULL, assertions_json TEXT NOT NULL DEFAULT '[]', risk_tier TEXT NOT NULL DEFAULT 'R1'
          CHECK(risk_tier IN ('R0','R1','R2','R3')), active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id),
          UNIQUE(workspace_id, project_id, agent_name, name));
        CREATE TABLE IF NOT EXISTS agent_eval_runs (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, agent_name TEXT NOT NULL,
          candidate_version TEXT NOT NULL, baseline_version TEXT, contract_checksum TEXT NOT NULL, prompt_checksum TEXT NOT NULL,
          model_id TEXT NOT NULL, commit_sha TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running'
          CHECK(status IN ('running','passed','failed','cancelled')), threshold REAL NOT NULL DEFAULT 0.85,
          baseline_score REAL, score REAL, metrics_json TEXT NOT NULL DEFAULT '{}', gates_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL, completed_at TEXT,
          FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
        CREATE TABLE IF NOT EXISTS agent_eval_results (
          id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, score REAL NOT NULL CHECK(score BETWEEN 0 AND 1),
          passed INTEGER NOT NULL CHECK(passed IN (0,1)), safety_violations_json TEXT NOT NULL DEFAULT '[]',
          evidence_json TEXT NOT NULL DEFAULT '[]', latency_ms INTEGER, cost_usd REAL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES agent_eval_runs(id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES agent_eval_cases(id), UNIQUE(run_id, case_id));
        CREATE TABLE IF NOT EXISTS agent_releases (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, agent_name TEXT NOT NULL,
          version TEXT NOT NULL, contract_json TEXT NOT NULL, contract_checksum TEXT NOT NULL, evaluation_run_id TEXT NOT NULL,
          risk_tier TEXT NOT NULL CHECK(risk_tier IN ('R0','R1','R2','R3')), status TEXT NOT NULL DEFAULT 'candidate'
          CHECK(status IN ('candidate','approved','rejected','shadow','canary','active','retired','rolled_back')),
          traffic_percent INTEGER NOT NULL DEFAULT 0 CHECK(traffic_percent BETWEEN 0 AND 100),
          required_approvals INTEGER NOT NULL DEFAULT 1 CHECK(required_approvals BETWEEN 1 AND 2)
          CHECK(risk_tier != 'R3' OR required_approvals = 2),
          approvals_json TEXT NOT NULL DEFAULT '[]', previous_release_id TEXT, created_by TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, activated_at TEXT, rollback_reason TEXT,
          FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id),
          FOREIGN KEY(evaluation_run_id) REFERENCES agent_eval_runs(id), FOREIGN KEY(previous_release_id) REFERENCES agent_releases(id),
          UNIQUE(workspace_id, project_id, agent_name, version));
        CREATE TABLE IF NOT EXISTS agent_execution_receipts (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, run_id TEXT, step_id TEXT,
          agent_name TEXT NOT NULL, agent_version TEXT NOT NULL, contract_checksum TEXT NOT NULL, prompt_checksum TEXT NOT NULL, model_id TEXT NOT NULL,
          config_hash TEXT NOT NULL, commit_sha TEXT NOT NULL, context_manifest_json TEXT NOT NULL DEFAULT '{}',
          tool_manifest_json TEXT NOT NULL DEFAULT '[]', output_hash TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '[]',
          metrics_json TEXT NOT NULL DEFAULT '{}', previous_hash TEXT, receipt_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
          FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, event_type TEXT NOT NULL, entity_type TEXT,
  entity_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(workspace_id, project_id, status);
CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(workspace_id, project_id, status);
CREATE INDEX IF NOT EXISTS idx_rules_agent ON rules(workspace_id, agent_name, project_id, status);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(workspace_id, project_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_eval_cases ON agent_eval_cases(workspace_id, project_id, agent_name, active);
CREATE INDEX IF NOT EXISTS idx_agent_eval_runs ON agent_eval_runs(workspace_id, project_id, agent_name, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_releases ON agent_releases(workspace_id, project_id, agent_name, status);
CREATE INDEX IF NOT EXISTS idx_agent_receipts ON agent_execution_receipts(workspace_id, project_id, agent_name, created_at);
"""

# Platform v3 (schema v2): semantic index, persistent swarms, federation and marketplace.
PLATFORM_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_embeddings (
  memory_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, model TEXT NOT NULL, dimensions INTEGER NOT NULL,
  vector_json TEXT NOT NULL, source_system TEXT NOT NULL DEFAULT 'agentshield', external_id TEXT,
  content_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE,
  UNIQUE(workspace_id, source_system, external_id));
CREATE TABLE IF NOT EXISTS swarm_runs (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL, objective TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('created','running','paused','completed','failed','cancelled')),
  max_parallel INTEGER NOT NULL DEFAULT 4 CHECK(max_parallel BETWEEN 1 AND 64),
  metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  completed_at TEXT, FOREIGN KEY(project_id) REFERENCES projects(id));
CREATE TABLE IF NOT EXISTS swarm_tasks (
  id TEXT PRIMARY KEY, swarm_id TEXT NOT NULL, agent_name TEXT NOT NULL, title TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT '{}', output_json TEXT, status TEXT NOT NULL
  CHECK(status IN ('queued','leased','running','paused','completed','failed','cancelled')),
  depends_on_json TEXT NOT NULL DEFAULT '[]', attempt INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT, lease_expires_at TEXT, worktree_path TEXT, error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
  FOREIGN KEY(swarm_id) REFERENCES swarm_runs(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS federation_nodes (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL, endpoint TEXT NOT NULL,
  public_key_id TEXT NOT NULL, capabilities_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'active'
  CHECK(status IN ('active','draining','offline','revoked')), last_seen_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_messages (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL,
  message_type TEXT NOT NULL, payload_json TEXT NOT NULL, nonce TEXT NOT NULL, signature TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','delivered','acknowledged','failed','rejected')),
  created_at TEXT NOT NULL, delivered_at TEXT, UNIQUE(source_node_id, nonce));
CREATE TABLE IF NOT EXISTS marketplace_items (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('plugin','agent','workflow')),
  name TEXT NOT NULL, version TEXT NOT NULL, description TEXT NOT NULL, manifest_json TEXT NOT NULL,
  checksum TEXT NOT NULL, publisher TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1)),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(workspace_id, kind, name, version));
CREATE INDEX IF NOT EXISTS idx_swarm_tasks_claim ON swarm_tasks(swarm_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_federation_messages_target ON federation_messages(target_node_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_marketplace_items ON marketplace_items(workspace_id, kind, name);
"""

# (table, column, ddl) added in schema v1
V1_COLUMNS = [
    ("memories", "content_hash", "TEXT"),
    ("memories", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("decisions", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("decisions", "superseded_by", "TEXT"),
    ("learnings", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("learnings", "verified_by", "TEXT"),
    ("rules", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("rules", "approved_via", "TEXT"),
    ("incidents", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("task_outcomes", "flags_json", "TEXT NOT NULL DEFAULT '[]'"),
]

PROJECT_CHILD_TABLES = ["memories", "decisions", "learnings", "rules", "incidents", "task_outcomes"]
EVOLUTION_TABLES = ["agent_eval_cases", "agent_eval_runs", "agent_releases", "agent_execution_receipts"]
PLATFORM_PROJECT_TABLES = ["swarm_runs"]  # schema v2; swarm_tasks/embeddings cascade from their parents


class MemoryStoreBase:
    def __init__(self, db_path: Path, workspace_id: str, workspace_name: str = "Workspace"):
        self.db_path = Path(db_path)
        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fts = False
        self._migrate()

    # ------------------------------------------------------------------ connections
    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _tx(self, write: bool = True) -> Iterator[sqlite3.Connection]:
        conn = self._open()
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.execute("COMMIT")
        except BaseException:
            if write and conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # Backwards-compatible name used by the evolution mixin: a write transaction.
    def _connect(self):
        return self._tx(write=True)

    # ------------------------------------------------------------------ migrations
    @staticmethod
    def _fts_available(conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp._fts_probe USING fts5(x)")
            conn.execute("DROP TABLE temp._fts_probe")
            return True
        except sqlite3.OperationalError:
            return False

    def _migrate(self) -> None:
        conn = self._open()
        try:
            conn.execute("PRAGMA foreign_keys = OFF")  # allowed only outside a transaction
            conn.execute("BEGIN IMMEDIATE")
            try:
                for stmt in filter(None, (s.strip() for s in BASE_SCHEMA.split(";"))):
                    conn.execute(stmt)
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version < 1:
                    self._migrate_v1(conn)
                if version < 2:
                    for stmt in filter(None, (x.strip() for x in PLATFORM_V2_SCHEMA.split(";"))):
                        conn.execute(stmt)
                if version < SCHEMA_VERSION:
                    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                conn.execute(
                    "INSERT OR IGNORE INTO workspaces(id,name,created_at) VALUES(?,?,?)",
                    (self.workspace_id, self.workspace_name, utcnow()),
                )
                self.fts = bool(
                    conn.execute("SELECT 1 FROM sqlite_master WHERE name='search_index'").fetchone()
                )
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"Migration aborted: {len(violations)} foreign key violations")
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        log.info("Migrating memory schema to v1 at %s", self.db_path)
        for table, column, ddl in V1_COLUMNS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(workspace_id, project_id, content_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_project ON incidents(workspace_id, project_id, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_project ON task_outcomes(workspace_id, project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_id)")

        # Normalise legacy project ids ("FleetOS" -> "fleetos"); merge on collision.
        for row in conn.execute("SELECT id, workspace_id FROM projects").fetchall():
            old = row["id"]
            try:
                new = normalize_project_id(old)
            except ValidationError:
                continue
            if new == old:
                continue
            exists = conn.execute("SELECT 1 FROM projects WHERE id=?", (new,)).fetchone()
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in PROJECT_CHILD_TABLES + EVOLUTION_TABLES + PLATFORM_PROJECT_TABLES:
                if table in existing:
                    conn.execute(f"UPDATE {table} SET project_id=? WHERE project_id=?", (new, old))
            if exists:
                conn.execute("DELETE FROM projects WHERE id=?", (old,))
            else:
                conn.execute("UPDATE projects SET id=? WHERE id=?", (new, old))
            conn.execute("UPDATE audit_log SET entity_id=? WHERE entity_type='project' AND entity_id=?", (new, old))

        # Backfill content hashes for dedup.
        for r in conn.execute("SELECT id, project_id, kind, title, content FROM memories WHERE content_hash IS NULL").fetchall():
            conn.execute(
                "UPDATE memories SET content_hash=? WHERE id=?",
                (_sha(r["project_id"] or GLOBAL, r["kind"], r["title"].strip().lower(), r["content"].strip()), r["id"]),
            )

        if self._fts_available(conn):
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5("
                "title, body, entity_type UNINDEXED, entity_id UNINDEXED, project_id UNINDEXED, "
                "tokenize = 'unicode61 remove_diacritics 2')"
            )
            for etype, table in ENTITY_TABLES.items():
                for r in conn.execute(f"SELECT id FROM {table}").fetchall():
                    self._index(conn, etype, r["id"], fts=True)

    # ------------------------------------------------------------------ indexing
    def _index(self, conn: sqlite3.Connection, etype: str, entity_id: str, fts: bool | None = None) -> None:
        use_fts = self.fts if fts is None else fts
        if not use_fts:
            return
        conn.execute("DELETE FROM search_index WHERE entity_id=?", (entity_id,))
        row = conn.execute(f"SELECT * FROM {ENTITY_TABLES[etype]} WHERE id=?", (entity_id,)).fetchone()
        if not row:
            return
        doc = self._document(etype, row)
        if doc is None:
            return
        title, body = doc
        conn.execute(
            "INSERT INTO search_index(title, body, entity_type, entity_id, project_id) VALUES(?,?,?,?,?)",
            (title, body, etype, entity_id, row["project_id"] or GLOBAL),
        )

    @staticmethod
    def _document(etype: str, r: sqlite3.Row) -> tuple[str, str] | None:
        """Return (title, body) for searchable rows, None for non-retrievable state."""
        if etype == "memory":
            if r["status"] != "active":
                return None
            return r["title"], " ".join([r["kind"], r["content"], r["evidence"] or "", r["tags_json"] or ""])
        if etype == "decision":
            return r["title"], "\n".join(str(r[f] or "") for f in ("context", "decision", "alternatives", "consequences"))
        if etype == "learning":
            if r["status"] == "rejected":
                return None
            return r["category"], "\n".join(str(r[f] or "") for f in ("problem", "root_cause", "solution", "rule_candidate", "evidence"))
        if etype == "rule":
            if r["status"] != "approved":
                return None
            return r["agent_name"], f"{r['rule_text']}\n{r['rationale']}"
        if etype == "incident":
            return r["summary"], "\n".join(str(r[f] or "") for f in ("severity", "impact", "root_cause", "remediation", "prevention"))
        if etype == "outcome":
            return r["task"], "\n".join(str(r[f] or "") for f in ("outcome", "what_worked", "what_failed", "reusable_lessons", "evidence"))
        return None

    # ------------------------------------------------------------------ audit
    def _audit(self, conn: sqlite3.Connection, event_type: str, entity_type: str, entity_id: str, payload: dict[str, Any]) -> None:
        """Payload must contain identifiers/enums only — never free text (see purge)."""
        conn.execute(
            "INSERT INTO audit_log(workspace_id,event_type,entity_type,entity_id,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (self.workspace_id, event_type, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), utcnow()),
        )

    # ------------------------------------------------------------------ projects
    def _pid(self, project_id: str | None, required: bool = True) -> str | None:
        if not (project_id or "").strip():
            if required:
                raise ValidationError("project_id is required.")
            return None
        return normalize_project_id(project_id)

    def _ensure_project_conn(self, conn: sqlite3.Connection, pid: str) -> None:
        if not conn.execute("SELECT 1 FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone():
            now = utcnow()
            conn.execute(
                "INSERT INTO projects(id,workspace_id,name,repo_path,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (pid, self.workspace_id, pid, "", "", now, now),
            )
            self._audit(conn, "project.created", "project", pid, {"implicit": True})

    def ensure_project(self, project_id: str, name: str | None = None, repo_path: str = "", summary: str = "") -> dict[str, Any]:
        pid = self._pid(project_id)
        name = clean_text(name, "name", MAX_TITLE)
        repo_path = clean_text(repo_path, "repo_path", 1024)
        summary = clean_text(summary, "summary", MAX_TEXT)
        assert_no_secrets({"name": name, "summary": summary, "repo_path": repo_path})
        now = utcnow()
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone()
            if row:
                if name or repo_path or summary:
                    conn.execute(
                        "UPDATE projects SET name=COALESCE(NULLIF(?,''),name), repo_path=COALESCE(NULLIF(?,''),repo_path), "
                        "summary=COALESCE(NULLIF(?,''),summary), updated_at=? WHERE id=? AND workspace_id=?",
                        (name, repo_path, summary, now, pid, self.workspace_id),
                    )
                    self._audit(conn, "project.updated", "project", pid, {})
            else:
                conn.execute(
                    "INSERT INTO projects(id,workspace_id,name,repo_path,summary,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (pid, self.workspace_id, name or pid, repo_path, summary, now, now),
                )
                self._audit(conn, "project.created", "project", pid, {})
            return dict(conn.execute("SELECT * FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone())

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        pid = self._pid(project_id)
        with self._tx(write=False) as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone()
            return dict(row) if row else None

    def list_projects(self) -> list[dict[str, Any]]:
        with self._tx(write=False) as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT id,name,repo_path,updated_at FROM projects WHERE workspace_id=? ORDER BY updated_at DESC",
                    (self.workspace_id,),
                )
            ]

    def resolve_project_id(self, repo_path: str) -> dict[str, Any]:
        """Derive a stable project_id from a repository path (git remote > folder name)."""
        raw = clean_text(repo_path, "repo_path", 1024, required=True)
        path = Path(raw).expanduser()
        key = str(path).replace("\\", "/").rstrip("/").lower()
        with self._tx(write=False) as conn:
            for r in conn.execute("SELECT id, repo_path FROM projects WHERE workspace_id=? AND repo_path<>''", (self.workspace_id,)):
                if (r["repo_path"] or "").replace("\\", "/").rstrip("/").lower() == key:
                    return {"project_id": r["id"], "source": "existing_project", "exists": True}
        candidate, source = None, "folder_name"
        probe = path
        for _ in range(12):
            cfg = probe / ".git" / "config"
            if cfg.is_file():
                try:
                    text = cfg.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    text = ""
                m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', text, re.S)
                if m:
                    candidate = re.split(r"[/:]", m.group(1).rstrip("/"))[-1].removesuffix(".git")
                    source = "git_remote"
                else:
                    candidate, source = probe.name, "git_root_folder"
                break
            if probe.parent == probe:
                break
            probe = probe.parent
        pid = normalize_project_id(candidate or path.name)
        return {"project_id": pid, "source": source, "exists": self.get_project(pid) is not None}

