from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ai_dlc_mcp.store import MemoryStore


class PlatformV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "platform.db", "workspace-v3", "Platform V3")
        self.store.ensure_project("project-v3", "Project V3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_vector_bridge_is_idempotent_and_searchable(self):
        records = [{"id": "codex-1", "title": "Lease discipline", "content": "Workers must hold a live lease before completing swarm tasks."}]
        first = self.store.bridge_native_memories("codex", records, "project-v3")
        second = self.store.bridge_native_memories("codex", records, "project-v3")
        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["imported"], 0)
        hits = self.store.semantic_search("live lease worker", "project-v3")
        self.assertEqual(hits[0].title, "Lease discipline")

    def test_swarm_dependencies_pause_resume_and_completion(self):
        swarm = self.store.create_swarm("project-v3", "Ship safely", [
            {"id": "spec", "agent": "principal-architect", "title": "Specify"},
            {"id": "build", "agent": "backend", "title": "Build", "depends_on": ["spec"]},
        ], 2)
        first = self.store.claim_swarm_task(swarm["id"], "worker-a")
        self.assertEqual(first["id"], "spec")
        self.assertIsNone(self.store.claim_swarm_task(swarm["id"], "worker-b"))
        self.store.complete_swarm_task("spec", "worker-a", {"approved": True})
        self.store.set_swarm_state(swarm["id"], "pause", "operator check")
        self.assertEqual(self.store.get_swarm(swarm["id"])["status"], "paused")
        self.store.set_swarm_state(swarm["id"], "resume")
        second = self.store.claim_swarm_task(swarm["id"], "worker-b")
        self.assertEqual(second["id"], "build")
        self.store.complete_swarm_task("build", "worker-b", {"tests": "passed"})
        self.assertEqual(self.store.get_swarm(swarm["id"])["status"], "completed")

    def test_swarm_rejects_cycles(self):
        with self.assertRaisesRegex(ValueError, "acyclic"):
            self.store.create_swarm("project-v3", "No deadlock", [
                {"id": "a", "agent": "backend", "title": "A", "depends_on": ["b"]},
                {"id": "b", "agent": "qa-verification", "title": "B", "depends_on": ["a"]},
            ])

    def test_federation_signature_and_replay_protection(self):
        secret = "a" * 32
        self.store.register_federation_node("node-a", "A", "https://a.example", "key-a-000", ["swarm"])
        self.store.register_federation_node("node-b", "B", "https://b.example", "key-b-000", ["swarm"])
        message = self.store.create_federation_message("node-a", "node-b", "swarm.offer", {"task": "spec"}, secret)
        self.assertTrue(self.store.verify_federation_message(message, secret))
        # Simulate an independently received envelope; remove the sender's local outbox row.
        with self.store._connect() as conn:
            conn.execute("DELETE FROM federation_messages WHERE id=?", (message["id"],))
        self.assertEqual(self.store.accept_federation_message(message, secret)["status"], "delivered")
        with self.assertRaisesRegex(PermissionError, "replay"):
            self.store.accept_federation_message(message, secret)

    def test_federation_node_id_cannot_cross_workspaces(self):
        other = MemoryStore(self.store.db_path, "workspace-other", "Other")
        original = self.store.register_federation_node("shared-node", "Original", "https://original.example", "key-a")
        with self.assertRaises(PermissionError):
            other.register_federation_node("shared-node", "Hijacked", "https://other.example", "key-b")
        with self.store._connect() as conn:
            row = conn.execute("SELECT workspace_id,name,endpoint,public_key_id FROM federation_nodes WHERE id=?", ("shared-node",)).fetchone()
        self.assertEqual(dict(row), {
            "workspace_id": self.store.workspace_id,
            "name": original["name"],
            "endpoint": original["endpoint"],
            "public_key_id": original["public_key_id"],
        })
        rotated = self.store.register_federation_node("shared-node", "Rotated", "https://rotated.example", "key-c")
        self.assertEqual(rotated["name"], "Rotated")

    def test_federation_endpoint_validates_exact_host(self):
        for endpoint in (
            "http://localhost.evil.example",
            "http://localhost@evil.example",
            "http://127.0.0.1.evil.example",
            "https://user:password@secure.example",
            "https://secure.example/path?token=secret",
            "https://secure.example/#fragment",
            "https://secure.example:invalid",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                self.store.register_federation_node("bad-node", "Bad", endpoint, "key")
        with self.store._connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM federation_nodes WHERE id='bad-node'").fetchone()[0], 0)
        for index, endpoint in enumerate(("https://secure.example", "http://localhost:8080", "http://127.0.0.1:8080", "http://[::1]:8080")):
            with self.subTest(endpoint=endpoint):
                self.store.register_federation_node(f"good-node-{index}", "Good", endpoint, "key")

    def test_marketplace_checksum_is_stable(self):
        first = self.store.publish_marketplace_item("plugin", "agentshield", "3.0.0", "Native plugin", {"name": "agentshield"}, "AgentShield", True)
        second = self.store.publish_marketplace_item("plugin", "agentshield", "3.0.0", "Native plugin", {"name": "agentshield"}, "AgentShield", True)
        self.assertEqual(first["checksum"], second["checksum"])
        self.assertEqual(len(self.store.list_marketplace_items("plugin")), 1)

    def test_marketplace_identity_is_scoped_and_legacy_id_is_preserved(self):
        other = MemoryStore(self.store.db_path, "workspace-other", "Other")
        first = self.store.publish_marketplace_item("plugin", "shared", "1.0.0", "First", {"owner": "first"}, "First")
        second = other.publish_marketplace_item("plugin", "shared", "1.0.0", "Second", {"owner": "second"}, "Second")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.store.list_marketplace_items("plugin")[0]["description"], "First")
        self.assertEqual(other.list_marketplace_items("plugin")[0]["description"], "Second")
        updated = self.store.publish_marketplace_item("plugin", "shared", "1.0.0", "Updated", {"owner": "first"}, "First")
        self.assertEqual(updated["id"], first["id"])
        self.assertEqual(other.list_marketplace_items("plugin")[0]["description"], "Second")

        with self.store._connect() as conn:
            conn.execute("""INSERT INTO marketplace_items(id,workspace_id,kind,name,version,description,manifest_json,checksum,publisher,verified,created_at,updated_at)
                            VALUES('plugin:legacy:1.0.0',?,'plugin','legacy','1.0.0','Legacy','{}','old','Owner',0,'2026-01-01','2026-01-01')""", (self.store.workspace_id,))
        legacy = self.store.publish_marketplace_item("plugin", "legacy", "1.0.0", "Updated", {}, "Owner")
        self.assertEqual(legacy["id"], "plugin:legacy:1.0.0")


if __name__ == "__main__":
    unittest.main()
