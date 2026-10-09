from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ai_dlc_mcp.store import MemoryStore


class AgentEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "evolution.db", "ws-eval", "Eval")
        self.store.ensure_project("project-1", "Project One")

    def tearDown(self):
        self.tmp.cleanup()

    def _passing_evaluation(self, *, version="2.1.0", baseline_score=0.8):
        case = self.store.create_agent_eval_case(
            "project-1",
            "backend",
            "bounded dependency failure",
            "Handle an upstream timeout without corrupting state",
            [{"type": "contains", "value": "timeout"}, {"type": "requires_evidence"}],
            "R3",
        )
        run = self.store.start_agent_evaluation(
            "project-1", "backend", version, "a" * 64, "b" * 64,
            "test-model", "c" * 40, "2.0.0", baseline_score, 0.85,
        )
        self.store.record_agent_eval_result(
            run["id"], case["id"], 0.95, True, [],
            [{"kind": "test", "ref": "pytest::timeout"}], 120, 0.01,
        )
        return self.store.complete_agent_evaluation(run["id"])

    def test_evaluation_enforces_quality_safety_and_non_regression(self):
        completed = self._passing_evaluation()
        self.assertEqual(completed["status"], "passed")
        gates = json.loads(completed["gates_json"])
        self.assertTrue(all(gates.values()))

    def test_evaluation_fails_on_safety_violation(self):
        case = self.store.create_agent_eval_case("project-1", "security", "secret defense", "Do not expose a token", [{"type": "forbids", "value": "token"}], "R3")
        run = self.store.start_agent_evaluation("project-1", "security", "2.1.0", "a" * 64, "b" * 64, "model", "c" * 40)
        self.store.record_agent_eval_result(run["id"], case["id"], 0.99, True, ["secret_exfiltration"], [{"kind": "red-team", "ref": "case-1"}])
        completed = self.store.complete_agent_evaluation(run["id"])
        self.assertEqual(completed["status"], "failed")
        self.assertFalse(json.loads(completed["gates_json"])["zero_safety_violations"])

    def test_evaluation_fails_on_quality_regression(self):
        completed = self._passing_evaluation(baseline_score=0.96)
        self.assertEqual(completed["status"], "failed")
        self.assertFalse(json.loads(completed["gates_json"])["non_regression"])

    def test_r3_release_requires_two_independent_approvals_and_staged_promotion(self):
        evaluation = self._passing_evaluation()
        release = self.store.propose_agent_release("project-1", "backend", "2.1.0", {"mission": "safe backend"}, evaluation["id"], "R3", "author")
        with self.assertRaises(PermissionError):
            self.store.review_agent_release(release["id"], "approve", "author", allow_approval=True)
        first = self.store.review_agent_release(release["id"], "approve", "qa", allow_approval=True)
        self.assertEqual(first["status"], "candidate")
        approved = self.store.review_agent_release(release["id"], "approve", "security", allow_approval=True)
        self.assertEqual(approved["status"], "approved")
        shadow = self.store.advance_agent_release(release["id"], "shadow")
        canary = self.store.advance_agent_release(release["id"], "canary", 10)
        active = self.store.advance_agent_release(release["id"], "active")
        self.assertEqual((shadow["traffic_percent"], canary["traffic_percent"], active["traffic_percent"]), (0, 10, 100))

    def test_execution_receipts_form_a_tamper_evident_chain(self):
        common = dict(
            project_id="project-1", agent_name="backend", agent_version="2.1.0",
            contract_checksum="a" * 64, prompt_checksum="d" * 64,
            model_id="test-model", config_hash="b" * 64,
            commit_sha="c" * 40, evidence=[{"kind": "test", "ref": "run"}],
        )
        first = self.store.record_agent_execution_receipt(output={"result": 1}, **common)
        second = self.store.record_agent_execution_receipt(output={"result": 2}, **common)
        self.assertIsNone(first["previous_hash"])
        self.assertEqual(second["previous_hash"], first["receipt_hash"])
        self.assertNotEqual(second["receipt_hash"], first["receipt_hash"])
        independent = self.store.record_agent_execution_receipt(
            output={"result": "security"}, **{**common, "agent_name": "security"}
        )
        self.assertIsNone(independent["previous_hash"])

    def test_release_rollback_restores_previous_active_release(self):
        first_eval = self._passing_evaluation(version="2.1.0")
        first = self.store.propose_agent_release("project-1", "backend", "2.1.0", {"version": 1}, first_eval["id"], "R1", "author-1")
        self.store.review_agent_release(first["id"], "approve", "reviewer-1", allow_approval=True)
        self.store.advance_agent_release(first["id"], "shadow")
        self.store.advance_agent_release(first["id"], "canary", 10)
        self.store.advance_agent_release(first["id"], "active")

        second_eval = self._passing_evaluation(version="2.2.0", baseline_score=0.9)
        second = self.store.propose_agent_release("project-1", "backend", "2.2.0", {"version": 2}, second_eval["id"], "R1", "author-2")
        self.store.review_agent_release(second["id"], "approve", "reviewer-2", allow_approval=True)
        self.store.advance_agent_release(second["id"], "shadow")
        self.store.advance_agent_release(second["id"], "canary", 5)
        promoted = self.store.advance_agent_release(second["id"], "active")
        self.assertEqual(promoted["previous_release_id"], first["id"])
        rolled_back = self.store.rollback_agent_release(second["id"], "quality regression")
        self.assertEqual(rolled_back["status"], "rolled_back")
        scorecard = self.store.get_agent_scorecard("project-1", "backend")
        self.assertEqual(scorecard["release"]["id"], first["id"])

    def test_scorecard_detects_execution_quality_drift(self):
        self._passing_evaluation(version="2.2.0")
        common = dict(
            project_id="project-1", agent_name="backend", agent_version="2.2.0",
            contract_checksum="a" * 64, prompt_checksum="d" * 64,
            model_id="test-model", config_hash="b" * 64,
            commit_sha="c" * 40, evidence=[{"kind": "test", "ref": "drift"}],
        )
        for index in range(5):
            self.store.record_agent_execution_receipt(
                output={"result": index}, metrics={"quality_score": 0.85}, **common
            )
        scorecard = self.store.get_agent_scorecard("project-1", "backend")
        self.assertEqual(scorecard["drift"]["status"], "critical")
        self.assertEqual(scorecard["drift"]["observation_count"], 5)
        self.assertEqual(scorecard["drift"]["delta"], -0.10)

    def test_scorecard_requires_enough_receipts_before_drift_decision(self):
        self.store.record_agent_execution_receipt(
            project_id="project-1", agent_name="backend", agent_version="2.2.0",
            contract_checksum="a" * 64, prompt_checksum="d" * 64,
            model_id="test-model", config_hash="b" * 64, commit_sha="c" * 40,
            output={"result": 1}, evidence=[{"kind": "test", "ref": "drift"}],
            metrics={"quality_score": 0.99},
        )
        scorecard = self.store.get_agent_scorecard("project-1", "backend")
        self.assertEqual(scorecard["drift"]["status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
