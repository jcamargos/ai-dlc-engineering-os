from __future__ import annotations

import copy
import json
import subprocess
import sys
import time

import pytest

from ai_dlc_mcp import behavioral_evals as ev
from ai_dlc_mcp import cli, verification as verify
from ai_dlc_mcp.store import MemoryStore


REMOTE = "https://github.com/example/target.git"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", REMOTE], check=True)
    (root / "file.txt").write_text("baseline", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture"], check=True)
    return root


def test_wrong_repository_prevents_command_execution(repo, tmp_path):
    marker = tmp_path / "should-not-exist"
    with pytest.raises(ValueError, match="identity mismatch"):
        verify.run_check(str(repo), "https://github.com/example/other", [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
    assert not marker.exists()


def test_receipt_success_and_changed_worktree_invalidation(repo):
    receipt = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "print(2**20)"])
    assert verify.validate_evidence(receipt, str(repo), REMOTE)["passed"]
    (repo / "file.txt").write_text("changed", encoding="utf-8")
    assert not verify.validate_evidence(receipt, str(repo), REMOTE)["passed"]
    assert "1048576" not in json.dumps(receipt)


def test_receipt_failure_timeout_and_source_mutation(repo):
    failure = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "raise SystemExit(3)"])
    assert not verify.validate_evidence(failure, str(repo), REMOTE)["passed"]
    timeout = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "import time; time.sleep(10)"], timeout=1)
    assert timeout["timed_out"] and not timeout["passed"]
    mutation = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "open('file.txt', 'w').write('changed')"])
    assert mutation["exit_code"] == 0 and not mutation["passed"]


def test_receipt_tracks_untracked_deleted_and_commit_changes(repo):
    before = verify.snapshot(repo, REMOTE)
    (repo / "untracked.txt").write_text("new", encoding="utf-8")
    assert verify.snapshot(repo, REMOTE) != before
    (repo / "untracked.txt").unlink()
    (repo / "file.txt").unlink()
    assert verify.snapshot(repo, REMOTE) != before


def test_receipt_invalidated_by_new_commit_even_when_files_match(repo):
    receipt = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "pass"])
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "--quiet", "--allow-empty", "-m", "new revision"], check=True)
    assert not verify.validate_evidence(receipt, str(repo), REMOTE)["passed"]


def test_receipt_stale_future_and_malformed_rejected(repo):
    receipt = verify.run_check(str(repo), REMOTE, [sys.executable, "-c", "pass"])
    for delta in (-90000, 60):
        changed = {**receipt, "finished_at": time.time() + delta}
        assert not verify.validate_evidence(changed, str(repo), REMOTE)["passed"]
    with pytest.raises(ValueError, match="Malformed"):
        verify.validate_evidence({}, str(repo), REMOTE)
    assert not verify.validate_evidence({**receipt, "exit_code": False}, str(repo), REMOTE)["passed"]


def test_remote_protocol_equivalence_and_credential_refusal():
    assert verify.repository_identity(REMOTE) == verify.repository_identity("git@github.com:example/target.git")
    for value in ("https://user:password@github.com/example/target", "file:///tmp/repo", "https://github.com/x?token=value"):
        with pytest.raises(ValueError):
            verify.repository_identity(value)


def test_verification_cli_round_trip_and_inside_output_rejected(repo, tmp_path, capsys):
    path = tmp_path / "receipt.json"
    parser = cli.build_parser()
    args = parser.parse_args(["verify", "run", "--directory", str(repo), "--expected-remote", REMOTE,
                              "--output", str(path), "--", sys.executable, "-c", "pass"])
    assert args.func(args) == 0
    args = parser.parse_args(["verify", "check", str(path), "--directory", str(repo), "--expected-remote", REMOTE])
    assert args.func(args) == 0
    args = parser.parse_args(["verify", "run", "--directory", str(repo), "--expected-remote", REMOTE,
                              "--output", str(repo / "bad.json"), "--", sys.executable, "-c", "pass"])
    with pytest.raises(ValueError, match="outside"):
        args.func(args)


def trace():
    return {"schema_version": 1, "kind": "fixture",
            "provenance": {"model": "fixture-only", "candidate": "test", "commit": "a" * 40,
                           "observer": "test-harness", "configuration": "synthetic", "repetition": "1"},
            "cases": [{"case_id": name, "events": copy.deepcopy(case["required"])} for name, case in ev.SUITE.items()]}


@pytest.mark.parametrize("case_id", list(ev.SUITE))
def test_every_behavioral_case_detects_missing_and_forbidden_actions(case_id):
    case = ev.SUITE[case_id]
    assert ev.evaluate_case(case_id, copy.deepcopy(case["required"]))["passed"]
    assert not ev.evaluate_case(case_id, [])["passed"]
    for index in range(len(case["required"])):
        missing = copy.deepcopy(case["required"])
        missing.pop(index)
        assert not ev.evaluate_case(case_id, missing)["passed"]
    for forbidden in case["forbidden"]:
        events = copy.deepcopy(case["required"]) + [forbidden]
        assert not ev.evaluate_case(case_id, events)["passed"]


def test_trace_coverage_order_provenance_and_metrics():
    good = trace()
    assert ev.evaluate_trace(good)["passed"]
    assert ev.evaluate_trace(good)["kind"] == "fixture"
    assert ev.evaluate_trace(good)["metrics"]["tokens"] is None
    incomplete = trace()
    incomplete["cases"].pop()
    assert not ev.evaluate_trace(incomplete)["passed"]
    wrong_order = trace()
    wrong_order["cases"][0]["events"].reverse()
    assert not ev.evaluate_trace(wrong_order)["passed"]
    for value in (float("nan"), float("inf"), -1, True):
        with pytest.raises(ValueError, match="metric"):
            ev.evaluate_trace({**good, "metrics": {"tokens": value}})
    duplicate = trace()
    duplicate["cases"][1] = duplicate["cases"][0]
    with pytest.raises(ValueError, match="duplicate"):
        ev.evaluate_trace(duplicate)
    with pytest.raises(ValueError, match="provenance"):
        ev.evaluate_trace({**good, "provenance": {}})


def test_observed_report_uses_existing_evaluation_store_without_approval(tmp_path):
    store = MemoryStore(tmp_path / "memory.db", "test")
    report = ev.evaluate_trace(trace())
    with pytest.raises(ValueError, match="fixtures"):
        ev.persist_report(store, "p", "orchestrator", report, "a" * 64, "b" * 64)
    # Synthetic observation exercises persistence only, not an actual agent evaluation.
    observed = trace()
    observed["kind"] = "observed"
    result = ev.persist_report(store, "p", "orchestrator", ev.evaluate_trace(observed), "a" * 64, "b" * 64)
    assert result["status"] == "passed"
    observed["cases"][0]["events"].append({"action": "edit"})
    failed = ev.persist_report(store, "p", "orchestrator", ev.evaluate_trace(observed), "a" * 64, "b" * 64)
    assert failed["status"] == "failed"
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM agent_releases").fetchone()[0] == 0


def test_recovery_survives_restart_and_preserves_completed_work(tmp_path):
    db = tmp_path / "memory.db"
    store = MemoryStore(db, "owner")
    run = store.create_swarm("p", "Resume safely", [
        {"id": "a"}, {"id": "b", "depends_on": ["a"]}, {"id": "c", "depends_on": ["b"]}], 1)
    task = store.claim_swarm_task(run["id"], "worker")
    store.complete_swarm_task(task["id"], "worker", {"evidence_ref": "test/run-a"})
    restarted = MemoryStore(db, "owner")
    recovery = restarted.get_swarm_recovery(run["id"])
    assert [x["id"] for x in recovery["completed"]] == ["a"]
    assert recovery["completed"][0]["output"] == {"evidence_ref": "test/run-a"}
    assert [x["id"] for x in recovery["ready"]] == ["b"]
    assert [x["id"] for x in recovery["blocked"]] == ["c"]
    assert restarted.claim_swarm_task(run["id"], "new-worker")["id"] == "b"
    assert restarted.get_swarm_recovery(run["id"])["available_slots"] == 0
    with pytest.raises(KeyError):
        MemoryStore(db, "other").get_swarm_recovery(run["id"])
    restarted.set_swarm_state(run["id"], "pause")
    before = restarted.get_swarm(run["id"])
    assert restarted.get_swarm_recovery(run["id"])["ready"] == []
    assert restarted.get_swarm(run["id"]) == before


def test_recovery_expired_lease_is_advisory_not_a_claim(tmp_path):
    store = MemoryStore(tmp_path / "memory.db", "owner")
    run = store.create_swarm("p", "Resume expired task", [{"id": "a"}])
    store.claim_swarm_task(run["id"], "worker")
    with store._connect() as conn:
        conn.execute("UPDATE swarm_tasks SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id='a'")
    assert store.get_swarm_recovery(run["id"])["ready"][0]["id"] == "a"
    assert store.get_swarm(run["id"])["tasks"][0]["status"] == "leased"
