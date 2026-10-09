"""Platform v3 code under the 2.4 guarantees: secrets, validation, purge, migrations, rebinding."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from ai_dlc_mcp.control_plane import ControlPlaneHandler
from ai_dlc_mcp.security import ValidationError
from ai_dlc_mcp.store import SCHEMA_VERSION, MemoryStore

FAKE_GH = "ghp_" + "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i2"


class PlatformHardening(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "m.db"
        self.store = MemoryStore(self.db, "ws", "WS")

    def tearDown(self):
        self.tmp.cleanup()

    def test_swarm_refuses_secrets_and_normalises_project(self):
        with self.assertRaises(ValidationError):
            self.store.create_swarm("p", "deploy", [{"id": "a", "input": {"token": FAKE_GH}}])
        swarm = self.store.create_swarm("Fleet OS", "ship", [{"id": "a"}, {"id": "b", "depends_on": ["a"]}])
        self.assertEqual(swarm["project_id"], "fleet-os")
        task = self.store.claim_swarm_task(swarm["id"], "w1")
        self.assertEqual(task["id"], "a")
        self.assertIsNone(self.store.claim_swarm_task(swarm["id"], "w2"), "b must wait for its dependency")

    def test_worktree_rejects_option_like_refs(self):
        swarm = self.store.create_swarm("p", "x", [{"id": "t"}])
        for ref in ("--upload-pack=evil", "main..HEAD", ""):
            with self.assertRaises(ValidationError):
                self.store.create_task_worktree(swarm["tasks"][0]["id"], self.tmp.name, ref)

    def test_bridge_skips_secret_records_and_maps_unknown_kinds(self):
        out = self.store.bridge_native_memories("claude", [
            {"id": "1", "content": "Team prefers trunk-based development", "kind": "native_memory"},
            {"id": "2", "content": f"CI token {FAKE_GH}"},
        ], "p")
        self.assertEqual(out["imported"], 1)
        self.assertEqual(out["refused"][0]["external_id"], "2")
        hit = self.store.semantic_search("trunk based development", "p")[0]
        self.assertEqual(hit.metadata["kind"], "other")
        again = self.store.bridge_native_memories("claude", [{"id": "1", "content": "Team prefers trunk-based development"}], "p")
        self.assertEqual(again["imported"], 0)

    def test_federation_payload_secret_refused(self):
        with self.assertRaises(ValidationError):
            self.store.create_federation_message("a", "b", "sync.memory", {"k": FAKE_GH}, "s" * 32)

    def test_purge_project_removes_swarms_and_embeddings(self):
        self.store.create_swarm("p", "x", [{"id": "t1"}])
        mem = self.store.save_memory("p", "fact", "A", "alpha beta")
        self.store.index_memory(mem["id"])
        self.store.purge_project("p")
        with closing(sqlite3.connect(self.db)) as conn:
            for table in ("swarm_runs", "swarm_tasks", "memory_embeddings"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)

    def test_v1_database_upgrades_to_v2(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE swarm_tasks")
            conn.execute("DROP TABLE swarm_runs")
            conn.execute("DROP TABLE memory_embeddings")
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        upgraded = MemoryStore(self.db, "ws", "WS")
        self.assertEqual(upgraded.stats()["schema_version"], SCHEMA_VERSION)
        self.assertEqual(upgraded.create_swarm("p", "x", [{"id": "t"}])["status"], "running")


class MissionControlRebinding(unittest.TestCase):
    def _handler(self, host_header: str, loopback: bool = True):
        h = ControlPlaneHandler.__new__(ControlPlaneHandler)
        h.server = SimpleNamespace(loopback_only=loopback)
        h.headers = {"Host": host_header}
        return h

    def test_only_loopback_hosts_on_loopback_bind(self):
        self.assertTrue(self._handler("127.0.0.1:8788")._host_allowed())
        self.assertTrue(self._handler("localhost:8788")._host_allowed())
        self.assertTrue(self._handler("[::1]:8788")._host_allowed())
        self.assertFalse(self._handler("attacker.example:8788")._host_allowed())
        self.assertTrue(self._handler("anything", loopback=False)._host_allowed())


if __name__ == "__main__":
    unittest.main()
