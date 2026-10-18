from __future__ import annotations

import ast
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai_dlc_mcp.graph_extract import extract, js_imports
from ai_dlc_mcp.graph_source import GraphError, scan
from ai_dlc_mcp.store import MemoryStore


class RepositoryGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        self.env = patch.dict(os.environ, {"AI_DLC_GRAPH_ROOTS": str(self.root)})
        self.env.start()
        self.store = MemoryStore(Path(self.tmp.name) / "test.db", "ws")
        self.store.ensure_project("p", "Project", str(self.root))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def fixture(self):
        self.write("src/pkg/__init__.py", "")
        self.write("src/pkg/service.py", "from . import db\n")
        self.write("src/pkg/db.py", "def query(): pass\n")
        self.write("app.py", "from pkg.service import start\n")
        self.write("web/app.ts", "import { api } from './api.js';\n")
        self.write("web/api.ts", "export const api = 1;\n")

    def test_index_and_transitive_queries_have_line_evidence(self):
        self.fixture()
        result = self.store.index_repository_graph("p")
        self.assertEqual(result["status"], "indexed")
        self.assertEqual(result["node_count"], 6)
        graph = self.store.query_repository_graph("p", "src/pkg/db.py")
        self.assertEqual(graph["status"], "current")
        self.assertEqual({e["source"] for e in graph["edges"]}, {"src/pkg/service.py", "app.py"})
        self.assertEqual({e["line"] for e in graph["edges"]}, {1})
        js = self.store.query_repository_graph("p", "web/app.ts", "dependencies")
        self.assertEqual(js["edges"][0]["target"], "web/api.ts")
        self.assertEqual(js["edges"][0]["method"], "js_ts_lexical")

    def test_uncommitted_edits_additions_deletions_and_refresh(self):
        self.fixture()
        self.store.index_repository_graph("p")
        self.write("web/api.ts", "export const api = 2;\n")
        self.assertEqual(self.store.repository_graph_status("p")["status"], "stale")
        self.assertEqual(self.store.query_repository_graph("p", "web/api.ts")["edges"], [])
        self.store.index_repository_graph("p")
        self.write("new.py", "import app\n")
        self.assertEqual(self.store.repository_graph_status("p")["status"], "stale")
        self.store.index_repository_graph("p")
        (self.root / "new.py").unlink()
        self.assertEqual(self.store.repository_graph_status("p")["status"], "stale")

    def test_workspace_and_project_isolation(self):
        self.fixture()
        self.store.index_repository_graph("p")
        other = MemoryStore(self.store.db_path, "other")
        for operation in (other.index_repository_graph, other.repository_graph_status):
            with self.assertRaisesRegex(GraphError, "Project not found"):
                operation("p")
        with self.assertRaises(GraphError):
            other.query_repository_graph("p", "app.py")
        self.store.ensure_project("p2", "Second", str(self.root))
        self.assertEqual(self.store.repository_graph_status("p2")["status"], "missing")

    def test_default_deny_and_root_binding(self):
        with patch.dict(os.environ, {"AI_DLC_GRAPH_ROOTS": ""}):
            with self.assertRaisesRegex(GraphError, "not allowed"):
                self.store.index_repository_graph("p")
        outside = Path(self.tmp.name) / "other"
        outside.mkdir()
        self.store.ensure_project("p", repo_path=str(outside))
        with self.assertRaisesRegex(GraphError, "not allowed"):
            self.store.index_repository_graph("p")
        self.write("nested/a.py", "")
        self.store.ensure_project("p", repo_path=str(self.root / "nested"))
        with self.assertRaisesRegex(GraphError, "repository root"):
            self.store.index_repository_graph("p")

    def test_exclusions_and_no_source_storage(self):
        self.write("safe.py", 'secret_value = "DO-NOT-PERSIST-THIS-LITERAL"\n')
        self.write(".env.py", 'credential = "PRIVATE"')
        self.write("node_modules/dep/index.js", "")
        self.write("output/scratch.py", "")
        self.write("ignored/private.py", "")
        self.write(".gitignore", "ignored/\n")
        result = self.store.index_repository_graph("p")
        self.assertEqual(result["node_count"], 1)
        with self.store._connect() as conn:
            stored = conn.execute("SELECT graph_json FROM repository_graphs").fetchone()[0]
            audit = conn.execute("SELECT payload_json FROM audit_log WHERE event_type='graph.indexed'").fetchone()[0]
        self.assertNotIn("DO-NOT-PERSIST", stored + audit)
        self.assertNotIn("PRIVATE", stored + audit)

    def test_symlink_is_not_followed(self):
        outside = Path(self.tmp.name) / "outside.py"
        outside.write_text("import private_module\n")
        try:
            (self.root / "link.py").symlink_to(outside)
        except OSError:
            self.skipTest("Host does not grant symlink creation; exercised in Linux CI")
        result = self.store.index_repository_graph("p")
        self.assertEqual(result["node_count"], 0)
        self.assertEqual(result["coverage"]["issue_count"], 1)

    def test_cycles_limits_and_input_validation(self):
        self.write("a.py", "import b\nimport c\n")
        self.write("b.py", "import a\n")
        self.write("c.py", "import b\n")
        self.store.index_repository_graph("p")
        result = self.store.query_repository_graph("p", "a.py", "dependencies", 5, 1)
        self.assertEqual(len(result["edges"]), 1)
        self.assertTrue(result["truncated"])
        all_edges = self.store.query_repository_graph("p", "a.py", "dependencies", 5)
        self.assertEqual(len(all_edges["edges"]), 4)
        for kwargs in ({"path": "../outside.py"}, {"path": "C:/outside.py"},
                       {"path": "a.py", "depth": 6}, {"path": "a.py", "limit": 0},
                       {"path": "a.py", "direction": "invalid"}):
            with self.assertRaises(GraphError):
                self.store.query_repository_graph("p", **kwargs)

    def test_parse_failures_and_unresolved_imports_are_explicit(self):
        self.write("bad.py", "def invalid(:\n")
        self.write("ok.py", "import external_package\n")
        result = self.store.index_repository_graph("p")
        self.assertEqual(result["coverage"]["unresolved_imports"], 1)
        self.assertEqual(result["coverage"]["issue_sample"][0]["reason"], "python_parse_error")

    def test_failed_refresh_preserves_previous_snapshot(self):
        self.write("a.py", "")
        first = self.store.index_repository_graph("p")
        with patch("ai_dlc_mcp._store_graph.scan", side_effect=GraphError("budget exceeded")):
            with self.assertRaises(GraphError):
                self.store.index_repository_graph("p")
        self.assertEqual(self.store.repository_graph_status("p")["fingerprint"], first["fingerprint"])

    def test_concurrent_change_rejected(self):
        self.write("a.py", "")
        original = scan(self.root)
        changed = {**original, "fingerprint": "changed"}
        with patch("ai_dlc_mcp._store_graph.scan", side_effect=[original, changed]):
            with self.assertRaisesRegex(GraphError, "changed while indexing"):
                self.store.index_repository_graph("p")
        self.assertEqual(self.store.repository_graph_status("p")["status"], "missing")

    def test_file_and_total_budgets(self):
        self.write("large.py", "x" * 40)
        with patch("ai_dlc_mcp.graph_source.MAX_FILE_BYTES", 20):
            result = self.store.index_repository_graph("p")
            self.assertEqual(result["coverage"]["issue_sample"][0]["reason"], "file_size_limit")
        with patch("ai_dlc_mcp.graph_source.MAX_TOTAL_BYTES", 10):
            with self.assertRaisesRegex(GraphError, "budget"):
                self.store.index_repository_graph("p")

    def test_js_comments_templates_multiline_and_ambiguity(self):
        text = '''// import x from './fake.js';
const s = "import x from './fake.js'";
const t = `import './fake.js'`;
import {
  x
} from './real.js';
export { y } from './other.js';
const z = require('./cjs.js');
import('./lazy.js');
'''
        self.assertEqual(list(js_imports(text)), [("./real.js", 4), ("./other.js", 7),
                                                 ("./cjs.js", 8), ("./lazy.js", 9)])
        self.write("app.ts", "import './mod';\n")
        self.write("mod.ts", "")
        self.write("mod.js", "")
        graph = extract(scan(self.root))
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["coverage"]["unresolved_imports"], 1)

    def test_idempotent_snapshot_and_manifest_tool_parity(self):
        self.fixture()
        first = self.store.index_repository_graph("p")
        second = self.store.index_repository_graph("p")
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "src/ai_dlc_mcp/server.py").read_text(encoding="utf-8"))
        tools = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                 and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                         and d.func.id == "tool" for d in node.decorator_list)}
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["mcp_tools"]), tools)

    def test_database_rejects_cross_workspace_ownership(self):
        MemoryStore(self.store.db_path, "other")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store._connect() as conn:
                conn.execute("INSERT INTO repository_graphs VALUES(?,?,?,?)",
                             ("other", "p", str(self.root), "{}"))

    def test_commit_only_change_invalidates_snapshot(self):
        self.write("a.py", "")
        self.store.index_repository_graph("p")
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Graph Test",
                        "-c", "user.email=graph@example.invalid", "-c", "commit.gpgsign=false",
                        "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "fixture"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertEqual(self.store.repository_graph_status("p")["status"], "stale")

    def test_python_module_resolution_does_not_choose_ambiguous_targets(self):
        self.write("app.py", "import pkg\n")
        self.write("pkg.py", "")
        self.write("src/pkg.py", "")
        graph = extract(scan(self.root))
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["coverage"]["unresolved_imports"], 1)

    def test_git_timeout_preserves_index(self):
        self.write("a.py", "")
        self.store.index_repository_graph("p")
        with patch("ai_dlc_mcp.graph_source.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            with self.assertRaisesRegex(GraphError, "timed out"):
                self.store.index_repository_graph("p")
        self.assertEqual(self.store.repository_graph_status("p")["status"], "current")

    def test_file_and_edge_count_limits(self):
        self.write("a.py", "import b\n")
        self.write("b.py", "")
        with patch("ai_dlc_mcp.graph_source.MAX_FILES", 1):
            with self.assertRaises(GraphError):
                self.store.index_repository_graph("p")
        with patch("ai_dlc_mcp.graph_extract.MAX_EDGES", 0):
            with self.assertRaises(GraphError):
                self.store.index_repository_graph("p")

    def test_v2_migration_preserves_memory_and_can_be_reopened(self):
        self.store.save_memory("p", "fact", "Existing fact", "Keep this decision context")
        with self.store._connect() as conn:
            conn.execute("DROP TABLE repository_graphs")
            conn.execute("DROP INDEX idx_projects_workspace_id")
            conn.execute("PRAGMA user_version=2")
        upgraded = MemoryStore(self.store.db_path, "ws")
        self.assertEqual(upgraded.stats("p")["memories"], 1)
        self.write("a.py", "")
        self.assertEqual(upgraded.index_repository_graph("p")["node_count"], 1)
        reopened = MemoryStore(self.store.db_path, "ws")
        self.assertEqual(reopened.repository_graph_status("p")["status"], "current")

    def test_project_merge_invalidates_both_indexes_and_purge_cascades(self):
        self.fixture()
        self.store.ensure_project("other", "Other", str(self.root))
        self.store.index_repository_graph("p")
        self.store.index_repository_graph("other")
        self.store.merge_projects("p", "other")
        self.assertEqual(self.store.repository_graph_status("other")["status"], "missing")
        self.store.index_repository_graph("other")
        self.store.purge_project("other")
        with self.store._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM repository_graphs").fetchone()[0], 0)

    def test_normalized_project_id_uses_one_snapshot(self):
        self.write("a.py", "")
        self.store.index_repository_graph("P")
        self.assertEqual(self.store.repository_graph_status("P")["status"], "current")
        self.assertEqual(self.store.query_repository_graph("P", "a.py")["status"], "current")


if __name__ == "__main__":
    unittest.main()
