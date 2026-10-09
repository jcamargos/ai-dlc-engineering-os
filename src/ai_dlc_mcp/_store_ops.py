from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ._store_base import ENTITY_TABLES, EVOLUTION_TABLES, GLOBAL, PLATFORM_PROJECT_TABLES, PROJECT_CHILD_TABLES, SCHEMA_VERSION, _sha, uid, utcnow, _flags
from .security import (
    DECISION_STATUSES, INCIDENT_SEVERITIES, INCIDENT_STATUSES, MAX_SHORT, MAX_TEXT, MAX_TITLE, MEMORY_KINDS,
    ValidationError, assert_no_secrets, clamp_confidence, clean_choice, clean_tags, clean_text, injection_flags,
)

class MemoryStoreOps:
    # ------------------------------------------------------------------ writes
    def save_memory(
        self,
        project_id: str | None,
        kind: str,
        title: str,
        content: str,
        tags: Iterable[str] = (),
        confidence: float = 0.8,
        evidence: str = "",
        source: str = "agent",
    ) -> dict[str, Any]:
        pid = self._pid(project_id, required=False)
        kind = clean_choice(kind, "kind", MEMORY_KINDS, "fact")
        title = clean_text(title, "title", MAX_TITLE, required=True)
        content = clean_text(content, "content", MAX_TEXT, required=True)
        evidence = clean_text(evidence, "evidence", MAX_TEXT)
        tag_list = clean_tags(list(tags))
        assert_no_secrets({"title": title, "content": content, "evidence": evidence, "tags": " ".join(tag_list)})
        flags = injection_flags(title, content, evidence)
        chash = _sha(pid or GLOBAL, kind, title.lower(), content)
        conf = clamp_confidence(confidence, 0.8)
        with self._tx() as conn:
            dup = conn.execute(
                "SELECT * FROM memories WHERE workspace_id=? AND content_hash=? AND status='active' AND project_id IS ?",
                (self.workspace_id, chash, pid),
            ).fetchone()
            if dup:
                out = dict(dup)
                out["deduplicated"] = True
                return out
            if pid:
                self._ensure_project_conn(conn, pid)
            mid, now = uid("mem"), utcnow()
            conn.execute(
                "INSERT INTO memories(id,workspace_id,project_id,scope,kind,title,content,tags_json,confidence,status,source,evidence,"
                "content_hash,flags_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'active',?,?,?,?,?,?)",
                (mid, self.workspace_id, pid, "project" if pid else "global", kind, title, content,
                 json.dumps(tag_list, ensure_ascii=False), conf, clean_text(source, "source", 64) or "agent", evidence,
                 chash, json.dumps(flags), now, now),
            )
            self._index(conn, "memory", mid)
            self._audit(conn, "memory.created", "memory", mid, {"project_id": pid, "kind": kind, "flags": flags})
            return dict(conn.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone())

    def supersede_memory(self, memory_id: str, reason: str) -> dict[str, Any]:
        reason = clean_text(reason, "reason", MAX_SHORT, required=True)
        assert_no_secrets({"reason": reason})
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE memories SET status='superseded', superseded_reason=?, updated_at=? WHERE id=? AND workspace_id=?",
                (reason, utcnow(), memory_id, self.workspace_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Memory not found: {memory_id}")
            self._index(conn, "memory", memory_id)
            self._audit(conn, "memory.superseded", "memory", memory_id, {})
            return dict(conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone())

    def save_decision(self, project_id, title, context, decision, alternatives="", consequences="", status="accepted") -> dict[str, Any]:
        pid = self._pid(project_id)
        f = {
            "title": clean_text(title, "title", MAX_TITLE, required=True),
            "context": clean_text(context, "context", MAX_TEXT, required=True),
            "decision": clean_text(decision, "decision", MAX_TEXT, required=True),
            "alternatives": clean_text(alternatives, "alternatives", MAX_TEXT),
            "consequences": clean_text(consequences, "consequences", MAX_TEXT),
        }
        status = clean_choice(status, "status", DECISION_STATUSES, "accepted")
        assert_no_secrets(f)
        flags = injection_flags(*f.values())
        with self._tx() as conn:
            self._ensure_project_conn(conn, pid)
            did, now = uid("adr"), utcnow()
            conn.execute(
                "INSERT INTO decisions(id,workspace_id,project_id,title,context,decision,alternatives,consequences,status,flags_json,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (did, self.workspace_id, pid, f["title"], f["context"], f["decision"], f["alternatives"], f["consequences"],
                 status, json.dumps(flags), now, now),
            )
            self._index(conn, "decision", did)
            self._audit(conn, "decision.created", "decision", did, {"project_id": pid, "status": status, "flags": flags})
            return dict(conn.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone())

    def supersede_decision(self, decision_id: str, reason: str, replaced_by: str = "") -> dict[str, Any]:
        reason = clean_text(reason, "reason", MAX_SHORT, required=True)
        assert_no_secrets({"reason": reason})
        with self._tx() as conn:
            if replaced_by and not conn.execute("SELECT 1 FROM decisions WHERE id=?", (replaced_by,)).fetchone():
                raise KeyError(f"Decision not found: {replaced_by}")
            cur = conn.execute(
                "UPDATE decisions SET status='superseded', superseded_by=NULLIF(?,''), "
                "consequences=TRIM(COALESCE(consequences,'') || char(10) || 'Superseded: ' || ?), updated_at=? "
                "WHERE id=? AND workspace_id=?",
                (replaced_by, reason, utcnow(), decision_id, self.workspace_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Decision not found: {decision_id}")
            self._index(conn, "decision", decision_id)
            self._audit(conn, "decision.superseded", "decision", decision_id, {"replaced_by": replaced_by or None})
            return dict(conn.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone())

    def record_learning(self, project_id, category, problem, root_cause, solution, rule_candidate="", evidence="", confidence=0.7) -> dict[str, Any]:
        pid = self._pid(project_id)
        f = {
            "category": clean_text(category, "category", 64, required=True).lower(),
            "problem": clean_text(problem, "problem", MAX_TEXT, required=True),
            "root_cause": clean_text(root_cause, "root_cause", MAX_TEXT),
            "solution": clean_text(solution, "solution", MAX_TEXT, required=True),
            "rule_candidate": clean_text(rule_candidate, "rule_candidate", MAX_SHORT),
            "evidence": clean_text(evidence, "evidence", MAX_TEXT),
        }
        assert_no_secrets(f)
        flags = injection_flags(*f.values())
        with self._tx() as conn:
            self._ensure_project_conn(conn, pid)
            lid, now = uid("learn"), utcnow()
            conn.execute(
                "INSERT INTO learnings(id,workspace_id,project_id,category,problem,root_cause,solution,rule_candidate,evidence,confidence,"
                "status,flags_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'candidate',?,?,?)",
                (lid, self.workspace_id, pid, f["category"], f["problem"], f["root_cause"], f["solution"], f["rule_candidate"],
                 f["evidence"], clamp_confidence(confidence, 0.7), json.dumps(flags), now, now),
            )
            self._index(conn, "learning", lid)
            self._audit(conn, "learning.created", "learning", lid, {"project_id": pid, "flags": flags})
            return dict(conn.execute("SELECT * FROM learnings WHERE id=?", (lid,)).fetchone())

    def verify_learning(self, learning_id: str, reviewer: str, evidence: str = "", via: str = "agent") -> dict[str, Any]:
        """Agents may verify with reproducible evidence; humans verify via the admin CLI (via='human')."""
        reviewer = clean_text(reviewer, "reviewer", 120, required=True)
        evidence = clean_text(evidence, "evidence", MAX_TEXT)
        if via != "human" and len(evidence) < 20:
            raise ValidationError(
                "Agent verification requires concrete evidence (>= 20 chars): the test, command or observation that proves it."
            )
        assert_no_secrets({"evidence": evidence, "reviewer": reviewer})
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM learnings WHERE id=? AND workspace_id=?", (learning_id, self.workspace_id)).fetchone()
            if not row:
                raise KeyError(f"Learning not found: {learning_id}")
            if row["status"] == "rejected":
                raise ValidationError("A rejected learning cannot be verified.")
            if "possible_prompt_injection" in _flags(row) and via != "human":
                raise PermissionError("This learning is flagged as possible prompt injection; only a human can verify it.")
            merged = "\n".join(x for x in [row["evidence"], evidence] if x)
            conn.execute(
                "UPDATE learnings SET status='verified', evidence=?, verified_by=?, updated_at=? WHERE id=?",
                (merged, via, utcnow(), learning_id),
            )
            self._index(conn, "learning", learning_id)
            self._audit(conn, "learning.verified", "learning", learning_id, {"via": via})
            return dict(conn.execute("SELECT * FROM learnings WHERE id=?", (learning_id,)).fetchone())

    def reject_learning(self, learning_id: str, reviewer: str) -> dict[str, Any]:
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE learnings SET status='rejected', updated_at=? WHERE id=? AND workspace_id=?",
                (utcnow(), learning_id, self.workspace_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Learning not found: {learning_id}")
            self._index(conn, "learning", learning_id)
            self._audit(conn, "learning.rejected", "learning", learning_id, {})
            return dict(conn.execute("SELECT * FROM learnings WHERE id=?", (learning_id,)).fetchone())

    def propose_rule(self, agent_name, rule_text, rationale, project_id=None, source_learning_id=None) -> dict[str, Any]:
        pid = self._pid(project_id, required=False)
        agent = re.sub(r"[^a-z0-9_-]", "", (agent_name or "").lower())
        if not agent:
            raise ValidationError("agent_name is required.")
        rule_text = clean_text(rule_text, "rule_text", MAX_SHORT, required=True)
        rationale = clean_text(rationale, "rationale", MAX_TEXT, required=True)
        assert_no_secrets({"rule_text": rule_text, "rationale": rationale})
        flags = injection_flags(rule_text, rationale)
        with self._tx() as conn:
            if pid:
                self._ensure_project_conn(conn, pid)
            if source_learning_id and not conn.execute("SELECT 1 FROM learnings WHERE id=?", (source_learning_id,)).fetchone():
                raise KeyError(f"Learning not found: {source_learning_id}")
            rid, now = uid("rule"), utcnow()
            conn.execute(
                "INSERT INTO rules(id,workspace_id,project_id,agent_name,rule_text,rationale,source_learning_id,status,flags_json,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,'candidate',?,?,?)",
                (rid, self.workspace_id, pid, agent, rule_text, rationale, source_learning_id or None, json.dumps(flags), now, now),
            )
            self._audit(conn, "rule.proposed", "rule", rid, {"agent_name": agent, "project_id": pid, "flags": flags})
            return dict(conn.execute("SELECT * FROM rules WHERE id=?", (rid,)).fetchone())

    def review_rule(self, rule_id: str, action: str, reviewer: str, notes: str = "", allow_approval: bool = False) -> dict[str, Any]:
        """Approval only through the human admin CLI (allow_approval=True). MCP callers may only reject."""
        action = (action or "").lower().strip()
        via = "human" if allow_approval else "agent"
        if action not in {"approve", "reject"}:
            raise ValidationError("action must be approve or reject")
        if action == "approve" and not allow_approval:
            raise PermissionError(
                "Rule approval is human-only. Ask the user to run:  ai-dlc-admin rules approve " + rule_id
            )
        reviewer = clean_text(reviewer, "reviewer", 120, required=True)
        notes = clean_text(notes, "notes", MAX_SHORT)
        assert_no_secrets({"notes": notes})
        status = "approved" if action == "approve" else "rejected"
        with self._tx() as conn:
            row = conn.execute("SELECT status FROM rules WHERE id=? AND workspace_id=?", (rule_id, self.workspace_id)).fetchone()
            if not row:
                raise KeyError(f"Rule not found: {rule_id}")
            conn.execute(
                "UPDATE rules SET status=?, reviewer=?, review_notes=?, approved_via=?, updated_at=? WHERE id=?",
                (status, reviewer, notes, via if status == "approved" else None, utcnow(), rule_id),
            )
            self._index(conn, "rule", rule_id)
            self._audit(conn, f"rule.{status}", "rule", rule_id, {"via": via})
            return dict(conn.execute("SELECT * FROM rules WHERE id=?", (rule_id,)).fetchone())

    def record_incident(self, project_id, severity, summary, impact="", root_cause="", remediation="", prevention="", status="open") -> dict[str, Any]:
        pid = self._pid(project_id)
        sev = clean_choice(severity, "severity", INCIDENT_SEVERITIES, "medium")
        status = clean_choice(status, "status", INCIDENT_STATUSES, "open")
        f = {
            "summary": clean_text(summary, "summary", MAX_SHORT, required=True),
            "impact": clean_text(impact, "impact", MAX_TEXT),
            "root_cause": clean_text(root_cause, "root_cause", MAX_TEXT),
            "remediation": clean_text(remediation, "remediation", MAX_TEXT),
            "prevention": clean_text(prevention, "prevention", MAX_TEXT),
        }
        assert_no_secrets(f)
        flags = injection_flags(*f.values())
        with self._tx() as conn:
            self._ensure_project_conn(conn, pid)
            iid, now = uid("inc"), utcnow()
            conn.execute(
                "INSERT INTO incidents(id,workspace_id,project_id,severity,summary,impact,root_cause,remediation,prevention,status,flags_json,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (iid, self.workspace_id, pid, sev, f["summary"], f["impact"], f["root_cause"], f["remediation"], f["prevention"],
                 status, json.dumps(flags), now, now),
            )
            self._index(conn, "incident", iid)
            self._audit(conn, "incident.created", "incident", iid, {"project_id": pid, "severity": sev, "status": status})
            return dict(conn.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone())

    def update_incident(self, incident_id: str, status: str = "", root_cause: str = "", remediation: str = "", prevention: str = "") -> dict[str, Any]:
        f = {
            "root_cause": clean_text(root_cause, "root_cause", MAX_TEXT),
            "remediation": clean_text(remediation, "remediation", MAX_TEXT),
            "prevention": clean_text(prevention, "prevention", MAX_TEXT),
        }
        st = clean_choice(status, "status", INCIDENT_STATUSES, "open") if status else ""
        assert_no_secrets(f)
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE incidents SET status=COALESCE(NULLIF(?,''),status), root_cause=COALESCE(NULLIF(?,''),root_cause), "
                "remediation=COALESCE(NULLIF(?,''),remediation), prevention=COALESCE(NULLIF(?,''),prevention), updated_at=? "
                "WHERE id=? AND workspace_id=?",
                (st, f["root_cause"], f["remediation"], f["prevention"], utcnow(), incident_id, self.workspace_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Incident not found: {incident_id}")
            self._index(conn, "incident", incident_id)
            self._audit(conn, "incident.updated", "incident", incident_id, {"status": st or None})
            return dict(conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone())

    def record_task_outcome(self, project_id, task, outcome, what_worked="", what_failed="", reusable_lessons="", evidence="") -> dict[str, Any]:
        pid = self._pid(project_id)
        f = {
            "task": clean_text(task, "task", MAX_SHORT, required=True),
            "outcome": clean_text(outcome, "outcome", MAX_TEXT, required=True),
            "what_worked": clean_text(what_worked, "what_worked", MAX_TEXT),
            "what_failed": clean_text(what_failed, "what_failed", MAX_TEXT),
            "reusable_lessons": clean_text(reusable_lessons, "reusable_lessons", MAX_TEXT),
            "evidence": clean_text(evidence, "evidence", MAX_TEXT),
        }
        assert_no_secrets(f)
        flags = injection_flags(*f.values())
        with self._tx() as conn:
            self._ensure_project_conn(conn, pid)
            oid, now = uid("outcome"), utcnow()
            conn.execute(
                "INSERT INTO task_outcomes(id,workspace_id,project_id,task,outcome,what_worked,what_failed,reusable_lessons,evidence,"
                "flags_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (oid, self.workspace_id, pid, f["task"], f["outcome"], f["what_worked"], f["what_failed"], f["reusable_lessons"],
                 f["evidence"], json.dumps(flags), now),
            )
            self._index(conn, "outcome", oid)
            self._audit(conn, "task.outcome", "task_outcome", oid, {"project_id": pid})
            return dict(conn.execute("SELECT * FROM task_outcomes WHERE id=?", (oid,)).fetchone())

    # ------------------------------------------------------------------ purge (hard delete, LGPD/GDPR)
    def purge(self, entity_type: str, entity_id: str, reason: str, via: str = "agent") -> dict[str, Any]:
        """Irreversibly delete one entity, its search entry, and scrub its audit payloads."""
        etype = (entity_type or "").strip().lower()
        if etype not in ENTITY_TABLES:
            raise ValidationError(f"entity_type must be one of: {', '.join(ENTITY_TABLES)}")
        reason = clean_text(reason, "reason", MAX_SHORT, required=True)
        table = ENTITY_TABLES[etype]
        with self._tx() as conn:
            if not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND workspace_id=?", (entity_id, self.workspace_id)).fetchone():
                raise KeyError(f"{etype} not found: {entity_id}")
            if etype == "learning":
                conn.execute("UPDATE rules SET source_learning_id=NULL WHERE source_learning_id=?", (entity_id,))
            conn.execute(f"DELETE FROM {table} WHERE id=?", (entity_id,))
            if self.fts:
                conn.execute("DELETE FROM search_index WHERE entity_id=?", (entity_id,))
            conn.execute("UPDATE audit_log SET payload_json='{\"scrubbed\":true}' WHERE entity_id=?", (entity_id,))
            self._audit(conn, f"{etype}.purged", etype, entity_id, {"via": via, "reason_sha256": _sha(reason)[:16]})
        return {"purged": True, "entity_type": etype, "id": entity_id}

    def merge_projects(self, source_id: str, target_id: str, via: str = "human") -> dict[str, Any]:
        """Move every entry of `source_id` into `target_id` and delete the source project (fixes id fragmentation)."""
        src, dst = self._pid(source_id), self._pid(target_id)
        if src == dst:
            raise ValidationError("source and target must differ")
        moved: dict[str, int] = {}
        with self._tx() as conn:
            for pid in (src, dst):
                if not conn.execute("SELECT 1 FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone():
                    raise KeyError(f"Project not found: {pid}")
            for table in PROJECT_CHILD_TABLES + EVOLUTION_TABLES + PLATFORM_PROJECT_TABLES:
                moved[table] = conn.execute(f"UPDATE {table} SET project_id=? WHERE project_id=?", (dst, src)).rowcount
            if self.fts:
                conn.execute("UPDATE search_index SET project_id=? WHERE project_id=?", (dst, src))
            conn.execute(
                "UPDATE projects SET repo_path=COALESCE(NULLIF(repo_path,''),(SELECT repo_path FROM projects WHERE id=?)), "
                "updated_at=? WHERE id=?", (src, utcnow(), dst))
            conn.execute("DELETE FROM projects WHERE id=?", (src,))
            self._audit(conn, "project.merged", "project", dst, {"source": src, "via": via, "moved": moved})
        return {"merged": True, "source": src, "target": dst, "moved": moved}

    def purge_project(self, project_id: str, via: str = "human") -> dict[str, Any]:
        pid = self._pid(project_id)
        counts: dict[str, int] = {}
        with self._tx() as conn:
            if not conn.execute("SELECT 1 FROM projects WHERE id=? AND workspace_id=?", (pid, self.workspace_id)).fetchone():
                raise KeyError(f"Project not found: {pid}")
            ids = []
            for table in PROJECT_CHILD_TABLES:
                ids += [r[0] for r in conn.execute(f"SELECT id FROM {table} WHERE project_id=?", (pid,))]
            conn.execute(
                "UPDATE rules SET source_learning_id=NULL WHERE source_learning_id IN (SELECT id FROM learnings WHERE project_id=?)", (pid,)
            )
            conn.execute("UPDATE agent_releases SET previous_release_id=NULL WHERE project_id=?", (pid,))
            conn.execute("DELETE FROM agent_eval_results WHERE run_id IN (SELECT id FROM agent_eval_runs WHERE project_id=?)", (pid,))
            for table in ["swarm_runs", "agent_releases", "agent_eval_runs", "agent_eval_cases", "agent_execution_receipts",
                          "rules", "task_outcomes", "incidents", "learnings", "decisions", "memories"]:
                counts[table] = conn.execute(f"DELETE FROM {table} WHERE project_id=?", (pid,)).rowcount
            if self.fts:
                conn.execute("DELETE FROM search_index WHERE project_id=?", (pid,))
            for i in ids + [pid]:
                conn.execute("UPDATE audit_log SET payload_json='{\"scrubbed\":true}' WHERE entity_id=?", (i,))
            conn.execute("DELETE FROM projects WHERE id=?", (pid,))
            self._audit(conn, "project.purged", "project", pid, {"via": via, "counts": counts})
        return {"purged": True, "project_id": pid, "deleted": counts}

    # ------------------------------------------------------------------ admin
    def export(self, project_id: str | None = None) -> dict[str, Any]:
        pid = self._pid(project_id, required=False)
        out: dict[str, Any] = {"exported_at": utcnow(), "workspace_id": self.workspace_id, "schema_version": SCHEMA_VERSION}
        with self._tx(write=False) as conn:
            if pid:
                out["projects"] = [dict(r) for r in conn.execute("SELECT * FROM projects WHERE id=?", (pid,))]
            else:
                out["projects"] = [dict(r) for r in conn.execute("SELECT * FROM projects WHERE workspace_id=?", (self.workspace_id,))]
            for table in PROJECT_CHILD_TABLES + EVOLUTION_TABLES + PLATFORM_PROJECT_TABLES:
                if pid:
                    rows = conn.execute(f"SELECT * FROM {table} WHERE project_id=?", (pid,))
                else:
                    rows = conn.execute(f"SELECT * FROM {table} WHERE workspace_id=?", (self.workspace_id,))
                out[table] = [dict(r) for r in rows]
        return out

    def backup(self, dest: Path) -> Path:
        dest = Path(dest).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = self._open()
        try:
            target = sqlite3.connect(dest)
            try:
                src.backup(target)
            finally:
                target.close()
        finally:
            src.close()
        return dest

    def audit_tail(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._tx(write=False) as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM audit_log WHERE workspace_id=? ORDER BY id DESC LIMIT ?", (self.workspace_id, max(1, min(limit, 1000))))]

