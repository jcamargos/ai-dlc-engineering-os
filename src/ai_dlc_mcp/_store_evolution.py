from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ._store_base import uid, utcnow


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    payload = value if isinstance(value, str) else _json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MemoryStoreEvolution:
    def create_agent_eval_case(self, project_id, agent_name, name, task, assertions=None, risk_tier="R1"):
        project_id = self.ensure_project(project_id)["id"]
        risk_tier = risk_tier.upper()
        if risk_tier not in {"R0", "R1", "R2", "R3"}: raise ValueError("risk_tier must be R0, R1, R2 or R3")
        if not all(str(x).strip() for x in (agent_name, name, task)): raise ValueError("agent_name, name and task are required")
        if not assertions: raise ValueError("at least one evaluation assertion is required")
        cid, now = uid("evalcase"), utcnow()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_eval_cases(id,workspace_id,project_id,agent_name,name,task,assertions_json,risk_tier,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(workspace_id,project_id,agent_name,name) DO UPDATE SET task=excluded.task,assertions_json=excluded.assertions_json,risk_tier=excluded.risk_tier,active=1,updated_at=excluded.updated_at",
                (cid,self.workspace_id,project_id,agent_name,name,task,_json(assertions or []),risk_tier,now,now),
            )
            row = conn.execute("SELECT * FROM agent_eval_cases WHERE workspace_id=? AND project_id=? AND agent_name=? AND name=?",(self.workspace_id,project_id,agent_name,name)).fetchone()
            self._audit(conn,"agent.eval_case.upserted","agent_eval_case",row["id"],{"project_id":project_id,"agent":agent_name,"risk_tier":risk_tier})
            return dict(row)

    def start_agent_evaluation(self, project_id, agent_name, candidate_version, contract_checksum, prompt_checksum, model_id, commit_sha, baseline_version="", baseline_score=None, threshold=0.85):
        project_id = self.ensure_project(project_id)["id"]
        threshold = float(threshold)
        if not 0 <= threshold <= 1: raise ValueError("threshold must be between 0 and 1")
        if not all(str(x).strip() for x in (agent_name,candidate_version,contract_checksum,prompt_checksum,model_id,commit_sha)):
            raise ValueError("complete evaluation provenance is required")
        if not re.fullmatch(r"[0-9a-f]{64}", contract_checksum) or not re.fullmatch(r"[0-9a-f]{64}", prompt_checksum):
            raise ValueError("contract_checksum and prompt_checksum must be SHA-256 hex digests")
        if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha): raise ValueError("commit_sha must be a lowercase hexadecimal revision")
        rid, now = uid("evalrun"), utcnow()
        with self._connect() as conn:
            cases = conn.execute("SELECT count(*) FROM agent_eval_cases WHERE workspace_id=? AND project_id=? AND agent_name=? AND active=1",(self.workspace_id,project_id,agent_name)).fetchone()[0]
            if cases == 0: raise ValueError("at least one active evaluation case is required")
            conn.execute(
                "INSERT INTO agent_eval_runs(id,workspace_id,project_id,agent_name,candidate_version,baseline_version,contract_checksum,prompt_checksum,model_id,commit_sha,status,threshold,baseline_score,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,'running',?,?,?)",
                (rid,self.workspace_id,project_id,agent_name,candidate_version,baseline_version or None,contract_checksum,prompt_checksum,model_id,commit_sha,threshold,baseline_score,now),
            )
            self._audit(conn,"agent.evaluation.started","agent_eval_run",rid,{"agent":agent_name,"candidate_version":candidate_version,"case_count":cases})
            return dict(conn.execute("SELECT * FROM agent_eval_runs WHERE id=?",(rid,)).fetchone())

    def record_agent_eval_result(self, run_id, case_id, score, passed, safety_violations=None, evidence=None, latency_ms=None, cost_usd=None):
        score = float(score)
        if not 0 <= score <= 1: raise ValueError("score must be between 0 and 1")
        violations, evidence = list(safety_violations or []), list(evidence or [])
        if not evidence: raise ValueError("evaluation evidence is required")
        result_id, now = uid("evalresult"), utcnow()
        with self._connect() as conn:
            run = conn.execute("SELECT * FROM agent_eval_runs WHERE id=? AND workspace_id=?",(run_id,self.workspace_id)).fetchone()
            case = conn.execute("SELECT * FROM agent_eval_cases WHERE id=? AND workspace_id=?",(case_id,self.workspace_id)).fetchone()
            if not run or run["status"] != "running": raise ValueError("evaluation run is not active")
            if not case or case["project_id"] != run["project_id"] or case["agent_name"] != run["agent_name"]: raise ValueError("evaluation case does not match run")
            conn.execute(
                "INSERT INTO agent_eval_results(id,run_id,case_id,score,passed,safety_violations_json,evidence_json,latency_ms,cost_usd,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (result_id,run_id,case_id,score,1 if passed else 0,_json(violations),_json(evidence),latency_ms,cost_usd,now),
            )
            self._audit(conn,"agent.evaluation.result","agent_eval_result",result_id,{"run_id":run_id,"case_id":case_id,"score":score,"passed":bool(passed),"safety_violations":len(violations)})
            return dict(conn.execute("SELECT * FROM agent_eval_results WHERE id=?",(result_id,)).fetchone())

    def complete_agent_evaluation(self, run_id):
        with self._connect() as conn:
            run = conn.execute("SELECT * FROM agent_eval_runs WHERE id=? AND workspace_id=?",(run_id,self.workspace_id)).fetchone()
            if not run or run["status"] != "running": raise ValueError("evaluation run is not active")
            expected = conn.execute("SELECT count(*) FROM agent_eval_cases WHERE workspace_id=? AND project_id=? AND agent_name=? AND active=1",(self.workspace_id,run["project_id"],run["agent_name"])).fetchone()[0]
            rows = conn.execute("SELECT * FROM agent_eval_results WHERE run_id=?",(run_id,)).fetchall()
            score = sum(float(r["score"]) for r in rows) / len(rows) if rows else 0.0
            violations = sum(len(json.loads(r["safety_violations_json"])) for r in rows)
            regression_delta = None if run["baseline_score"] is None else score - float(run["baseline_score"])
            gates = {
                "all_cases_executed": len(rows) == expected and expected > 0,
                "all_cases_passed": bool(rows) and all(bool(r["passed"]) for r in rows),
                "threshold_met": score >= float(run["threshold"]),
                "zero_safety_violations": violations == 0,
                "non_regression": regression_delta is None or regression_delta >= 0,
            }
            passed = all(gates.values())
            metrics = {"case_count":len(rows),"expected_case_count":expected,"average_score":round(score,6),"safety_violations":violations,"regression_delta":regression_delta}
            conn.execute("UPDATE agent_eval_runs SET status=?,score=?,metrics_json=?,gates_json=?,completed_at=? WHERE id=?",("passed" if passed else "failed",score,_json(metrics),_json(gates),utcnow(),run_id))
            self._audit(conn,"agent.evaluation.completed","agent_eval_run",run_id,{"passed":passed,"metrics":metrics,"gates":gates})
            return dict(conn.execute("SELECT * FROM agent_eval_runs WHERE id=?",(run_id,)).fetchone())

    def propose_agent_release(self, project_id, agent_name, version, contract, evaluation_run_id, risk_tier, created_by):
        project_id = self._pid(project_id)
        risk_tier = risk_tier.upper()
        if risk_tier not in {"R0","R1","R2","R3"}: raise ValueError("risk_tier must be R0, R1, R2 or R3")
        rid, now, checksum = uid("release"), utcnow(), _sha(contract)
        with self._connect() as conn:
            evaluation = conn.execute("SELECT * FROM agent_eval_runs WHERE id=? AND workspace_id=? AND project_id=? AND agent_name=?",(evaluation_run_id,self.workspace_id,project_id,agent_name)).fetchone()
            if not evaluation or evaluation["status"] != "passed": raise ValueError("a passed evaluation is required")
            if evaluation["candidate_version"] != version: raise ValueError("release version must match the evaluated candidate")
            conn.execute(
                "INSERT INTO agent_releases(id,workspace_id,project_id,agent_name,version,contract_json,contract_checksum,evaluation_run_id,risk_tier,status,traffic_percent,required_approvals,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'candidate',0,?,?,?,?)",
                (rid,self.workspace_id,project_id,agent_name,version,_json(contract),checksum,evaluation_run_id,risk_tier,2 if risk_tier == "R3" else 1,created_by,now,now),
            )
            self._audit(conn,"agent.release.proposed","agent_release",rid,{"agent":agent_name,"version":version,"risk_tier":risk_tier,"checksum":checksum})
            return dict(conn.execute("SELECT * FROM agent_releases WHERE id=?",(rid,)).fetchone())

    def review_agent_release(self, release_id, decision, reviewer, notes="", allow_approval=False):
        decision = decision.lower().strip()
        if decision not in {"approve","reject"}: raise ValueError("decision must be approve or reject")
        if decision == "approve" and not allow_approval: raise PermissionError("Agent release approval is disabled for autonomous callers")
        with self._connect() as conn:
            release = conn.execute("SELECT * FROM agent_releases WHERE id=? AND workspace_id=?",(release_id,self.workspace_id)).fetchone()
            if not release or release["status"] not in {"candidate","approved"}: raise ValueError("release is not reviewable")
            if reviewer.strip().lower() == str(release["created_by"]).strip().lower(): raise PermissionError("release creator cannot approve their own release")
            approvals = json.loads(release["approvals_json"])
            approvals = [a for a in approvals if a.get("reviewer") != reviewer]
            approvals.append({"reviewer":reviewer,"decision":decision,"notes":notes,"at":utcnow()})
            approved_count = len({a["reviewer"] for a in approvals if a["decision"] == "approve"})
            status = "rejected" if decision == "reject" else ("approved" if approved_count >= release["required_approvals"] else "candidate")
            conn.execute("UPDATE agent_releases SET approvals_json=?,status=?,updated_at=? WHERE id=?",(_json(approvals),status,utcnow(),release_id))
            self._audit(conn,"agent.release.reviewed","agent_release",release_id,{"reviewer":reviewer,"decision":decision,"status":status})
            return dict(conn.execute("SELECT * FROM agent_releases WHERE id=?",(release_id,)).fetchone())

    def advance_agent_release(self, release_id, target_status, traffic_percent=0):
        target_status = target_status.lower().strip()
        with self._connect() as conn:
            release = conn.execute("SELECT * FROM agent_releases WHERE id=? AND workspace_id=?",(release_id,self.workspace_id)).fetchone()
            if not release: raise KeyError("release not found")
            transitions = {"approved":{"shadow"},"shadow":{"canary"},"canary":{"active"}}
            if target_status not in transitions.get(release["status"],set()): raise ValueError("invalid release transition")
            if target_status == "shadow": traffic_percent = 0
            elif target_status == "canary":
                traffic_percent = int(traffic_percent)
                if not 1 <= traffic_percent <= 50: raise ValueError("canary traffic must be between 1 and 50")
            else: traffic_percent = 100
            previous_id = release["previous_release_id"]
            now = utcnow()
            if target_status == "active":
                previous = conn.execute("SELECT id FROM agent_releases WHERE workspace_id=? AND project_id=? AND agent_name=? AND status='active'",(self.workspace_id,release["project_id"],release["agent_name"])).fetchone()
                previous_id = previous["id"] if previous else previous_id
                if previous: conn.execute("UPDATE agent_releases SET status='retired',traffic_percent=0,updated_at=? WHERE id=?",(now,previous["id"]))
            conn.execute("UPDATE agent_releases SET status=?,traffic_percent=?,previous_release_id=?,updated_at=?,activated_at=CASE WHEN ?='active' THEN ? ELSE activated_at END WHERE id=?",(target_status,traffic_percent,previous_id,now,target_status,now,release_id))
            self._audit(conn,"agent.release.advanced","agent_release",release_id,{"from":release["status"],"to":target_status,"traffic_percent":traffic_percent})
            return dict(conn.execute("SELECT * FROM agent_releases WHERE id=?",(release_id,)).fetchone())

    def rollback_agent_release(self, release_id, reason):
        if not str(reason).strip(): raise ValueError("rollback reason is required")
        with self._connect() as conn:
            release = conn.execute("SELECT * FROM agent_releases WHERE id=? AND workspace_id=?",(release_id,self.workspace_id)).fetchone()
            if not release or release["status"] not in {"canary","active"}: raise ValueError("only canary or active releases can be rolled back")
            now = utcnow()
            conn.execute("UPDATE agent_releases SET status='rolled_back',traffic_percent=0,rollback_reason=?,updated_at=? WHERE id=?",(reason,now,release_id))
            if release["previous_release_id"]:
                conn.execute("UPDATE agent_releases SET status='active',traffic_percent=100,updated_at=? WHERE id=?",(now,release["previous_release_id"]))
            self._audit(conn,"agent.release.rolled_back","agent_release",release_id,{"reason":reason,"restored":release["previous_release_id"]})
            return dict(conn.execute("SELECT * FROM agent_releases WHERE id=?",(release_id,)).fetchone())

    def record_agent_execution_receipt(self, project_id, agent_name, agent_version, contract_checksum, prompt_checksum, model_id, config_hash, commit_sha, output, evidence, context_manifest=None, tool_manifest=None, metrics=None, run_id=None, step_id=None):
        project_id = self._pid(project_id)
        required = (agent_name,agent_version,contract_checksum,prompt_checksum,model_id,config_hash,commit_sha)
        if not all(str(x).strip() for x in required): raise ValueError("complete execution provenance is required")
        if not evidence: raise ValueError("execution evidence is required")
        if not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in (contract_checksum,prompt_checksum,config_hash)):
            raise ValueError("contract, prompt and config checksums must be SHA-256 hex digests")
        if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha): raise ValueError("commit_sha must be a lowercase hexadecimal revision")
        receipt_id, now, output_hash = uid("receipt"), utcnow(), _sha(output)
        with self._connect() as conn:
            previous = conn.execute("SELECT receipt_hash FROM agent_execution_receipts WHERE workspace_id=? AND project_id=? AND agent_name=? ORDER BY created_at DESC,id DESC LIMIT 1",(self.workspace_id,project_id,agent_name)).fetchone()
            previous_hash = previous["receipt_hash"] if previous else None
            payload = {"id":receipt_id,"workspace_id":self.workspace_id,"project_id":project_id,"run_id":run_id,"step_id":step_id,"agent_name":agent_name,"agent_version":agent_version,"contract_checksum":contract_checksum,"prompt_checksum":prompt_checksum,"model_id":model_id,"config_hash":config_hash,"commit_sha":commit_sha,"context_manifest":context_manifest or {},"tool_manifest":tool_manifest or [],"output_hash":output_hash,"evidence":evidence,"metrics":metrics or {},"previous_hash":previous_hash,"created_at":now}
            receipt_hash = _sha(payload)
            conn.execute("INSERT INTO agent_execution_receipts(id,workspace_id,project_id,run_id,step_id,agent_name,agent_version,contract_checksum,prompt_checksum,model_id,config_hash,commit_sha,context_manifest_json,tool_manifest_json,output_hash,evidence_json,metrics_json,previous_hash,receipt_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(receipt_id,self.workspace_id,project_id,run_id,step_id,agent_name,agent_version,contract_checksum,prompt_checksum,model_id,config_hash,commit_sha,_json(context_manifest or {}),_json(tool_manifest or []),output_hash,_json(evidence),_json(metrics or {}),previous_hash,receipt_hash,now))
            self._audit(conn,"agent.execution.receipt","agent_execution_receipt",receipt_id,{"agent":agent_name,"receipt_hash":receipt_hash,"previous_hash":previous_hash})
            return dict(conn.execute("SELECT * FROM agent_execution_receipts WHERE id=?",(receipt_id,)).fetchone())

    def get_agent_scorecard(self, project_id, agent_name):
        project_id = self._pid(project_id)
        with self._connect() as conn:
            runs = conn.execute("SELECT status,score,metrics_json,created_at FROM agent_eval_runs WHERE workspace_id=? AND project_id=? AND agent_name=? ORDER BY created_at DESC LIMIT 20",(self.workspace_id,project_id,agent_name)).fetchall()
            release = conn.execute("SELECT * FROM agent_releases WHERE workspace_id=? AND project_id=? AND agent_name=? AND status IN ('active','canary','shadow') ORDER BY updated_at DESC LIMIT 1",(self.workspace_id,project_id,agent_name)).fetchone()
            receipts = conn.execute("SELECT metrics_json FROM agent_execution_receipts WHERE workspace_id=? AND project_id=? AND agent_name=? ORDER BY created_at DESC,id DESC LIMIT 20",(self.workspace_id,project_id,agent_name)).fetchall()
            completed = [r for r in runs if r["status"] in {"passed","failed"}]
            quality_scores = []
            for receipt in receipts:
                value = json.loads(receipt["metrics_json"]).get("quality_score")
                if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
                    quality_scores.append(float(value))
            latest_score = float(runs[0]["score"]) if runs and runs[0]["score"] is not None else None
            recent_average = round(sum(quality_scores) / len(quality_scores), 6) if quality_scores else None
            baseline = round(latest_score if latest_score is not None else 0.85, 6)
            delta = round(recent_average - baseline, 6) if recent_average is not None else None
            if len(quality_scores) < 5:
                drift_status, recommendation = "insufficient_data", "Collect at least five scored execution receipts."
            elif recent_average < 0.85 or delta <= -0.10:
                drift_status, recommendation = "critical", "Hold promotion and roll back an active canary until the regression is investigated."
            elif delta <= -0.05:
                drift_status, recommendation = "warning", "Investigate the quality regression before increasing traffic."
            else:
                drift_status, recommendation = "stable", "Continue staged monitoring."
            drift = {
                "status": drift_status,
                "observation_count": len(quality_scores),
                "minimum_observations": 5,
                "baseline_score": baseline,
                "recent_average": recent_average,
                "delta": delta,
                "warning_delta": -0.05,
                "critical_delta": -0.10,
                "minimum_quality": 0.85,
                "recommendation": recommendation,
            }
            return {"agent":agent_name,"evaluation_runs":len(runs),"pass_rate":(sum(r["status"]=="passed" for r in completed)/len(completed) if completed else None),"latest_score":latest_score,"execution_receipts":len(receipts),"average_quality":recent_average,"drift":drift,"release":dict(release) if release else None}
