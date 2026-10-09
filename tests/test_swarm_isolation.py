from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from ai_dlc_mcp.store import MemoryStore


class SwarmIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / "isolation.db"
        self.owner = MemoryStore(db, "owner-workspace")
        self.other = MemoryStore(db, "other-workspace")
        self.swarm = self.owner.create_swarm(
            "owner-project", "Verify lease boundaries", [{"id": "task-a"}]
        )
        self.claim = self.owner.claim_swarm_task(self.swarm["id"], "worker-a")

    def tearDown(self):
        self.tmp.cleanup()

    def test_other_workspace_cannot_complete_known_task(self):
        with self.assertRaises(PermissionError):
            self.other.complete_swarm_task("task-a", "worker-a", {"forged": True})
        self.assertEqual(self.owner.get_swarm(self.swarm["id"])["tasks"][0]["status"], "leased")

    def test_other_workspace_cannot_create_task_worktree(self):
        repository = Path(self.tmp.name) / "repo"
        repository.mkdir()
        (repository / ".git").mkdir()
        target = Path(self.tmp.name) / "created-worktrees"
        with patch("ai_dlc_mcp.swarm.subprocess.run") as git:
            with self.assertRaises(KeyError):
                self.other.create_task_worktree("task-a", str(repository), root=str(target))
            git.assert_not_called()
        self.assertFalse(target.exists())
        self.assertIsNone(self.owner.get_swarm(self.swarm["id"])["tasks"][0]["worktree_path"])

    def test_expired_missing_and_boundary_leases_cannot_complete(self):
        for expiry in ("2000-01-01T00:00:00+00:00", None, "2030-01-01T00:00:00+00:00"):
            with self.subTest(expiry=expiry):
                with self.owner._connect() as conn:
                    conn.execute("UPDATE swarm_tasks SET lease_expires_at=? WHERE id='task-a'", (expiry,))
                with patch("ai_dlc_mcp.swarm.utcnow", return_value="2030-01-01T00:00:00+00:00"):
                    with self.assertRaises(PermissionError):
                        self.owner.complete_swarm_task("task-a", "worker-a")
                self.assertEqual(self.owner.get_swarm(self.swarm["id"])["tasks"][0]["status"], "leased")

    def test_non_running_parent_cannot_complete(self):
        with self.owner._connect() as conn:
            conn.execute("UPDATE swarm_runs SET status='paused' WHERE id=?", (self.swarm["id"],))
        with self.assertRaises(PermissionError):
            self.owner.complete_swarm_task("task-a", "worker-a")

    def test_reclaimed_task_rejects_previous_worker(self):
        with self.owner._connect() as conn:
            conn.execute("UPDATE swarm_tasks SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id='task-a'")
        reclaimed = self.owner.claim_swarm_task(self.swarm["id"], "worker-b")
        self.assertEqual(reclaimed["attempt"], 2)
        with self.assertRaises(PermissionError):
            self.owner.complete_swarm_task("task-a", "worker-a")
        self.owner.complete_swarm_task("task-a", "worker-b")
        self.assertEqual(self.owner.get_swarm(self.swarm["id"])["status"], "completed")

    def test_cancel_remains_terminal(self):
        self.owner.set_swarm_state(self.swarm["id"], "cancel", "operator stop")
        with self.assertRaises(PermissionError):
            self.owner.complete_swarm_task("task-a", "worker-a")
        self.assertEqual(self.owner.get_swarm(self.swarm["id"])["status"], "cancelled")

    def test_concurrent_completion_commits_once(self):
        barrier = threading.Barrier(2)

        def complete():
            barrier.wait(timeout=5)
            try:
                self.owner.complete_swarm_task("task-a", "worker-a")
                return "completed"
            except PermissionError:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: complete(), range(2)))
        self.assertCountEqual(results, ["completed", "denied"])
        with self.owner._connect() as conn:
            count = conn.execute(
                "SELECT count(*) FROM audit_log WHERE event_type='swarm.task_completed' AND entity_id='task-a'"
            ).fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
