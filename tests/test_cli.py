from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_dlc_mcp import cli
from ai_dlc_mcp.store import MemoryStore


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        config = self.root / ".agentshield" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"project_id": "cli-project"}), encoding="utf-8")
        self.store = MemoryStore(self.root / "cli.db", "cli-workspace", "CLI")

    def tearDown(self):
        self.tmp.cleanup()

    def test_route_hook_recommends_specialist_without_persisting_prompt(self):
        raw_prompt = "Review authentication threat TOPSECRET"
        event = io.StringIO(json.dumps({"cwd": str(self.root), "session_id": "session-1", "prompt": raw_prompt}))
        output = io.StringIO()
        with patch.object(cli, "_store", return_value=self.store), patch("sys.stdin", event), redirect_stdout(output):
            self.assertEqual(cli.hook_command(argparse.Namespace(event="route")), 0)
        response = output.getvalue()
        self.assertIn("security", response)
        self.assertNotIn("TOPSECRET", response)
        with self.store._connect() as conn:
            audit = conn.execute("SELECT payload_json FROM audit_log WHERE event_type='hook.route'").fetchone()[0]
        self.assertNotIn("TOPSECRET", audit)
        self.assertIn("prompt_hash", audit)

    def test_init_preserves_existing_mcp_servers(self):
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"existing": {"command": "existing"}}}), encoding="utf-8")
        args = argparse.Namespace(directory=str(self.root), project_id="cli-project", endpoint=None, max_parallel=4, force=True, yes=True, project_mcp=True)
        with patch.object(cli, "_store", return_value=self.store):
            self.assertEqual(cli.init_command(args), 0)
        config = json.loads((self.root / ".mcp.json").read_text(encoding="utf-8"))
        self.assertIn("existing", config["mcpServers"])
        self.assertIn("ai_dlc_os", config["mcpServers"])
        self.assertNotIn("env", config["mcpServers"]["ai_dlc_os"], "must share the global workspace")

    def test_init_without_project_mcp_leaves_mcp_json_alone(self):
        args = argparse.Namespace(directory=str(self.root), project_id="cli-project", endpoint=None, max_parallel=4, force=True, yes=True, project_mcp=False)
        with patch.object(cli, "_store", return_value=self.store):
            self.assertEqual(cli.init_command(args), 0)
        self.assertFalse((self.root / ".mcp.json").exists())

    def test_route_matches_whole_words_only(self):
        event = io.StringIO(json.dumps({"cwd": str(self.root), "prompt": "rebuild the guide"}))
        output = io.StringIO()
        with patch.object(cli, "_store", return_value=self.store), patch("sys.stdin", event), redirect_stdout(output):
            cli.hook_command(argparse.Namespace(event="route"))
        self.assertIn("orchestrator", output.getvalue())
        self.assertNotIn("frontend", output.getvalue())

    def test_session_hook_does_not_create_projects_for_unknown_directories(self):
        stray = self.root / "random-folder"
        stray.mkdir()
        event = io.StringIO(json.dumps({"cwd": str(stray)}))
        with patch.object(cli, "_store", return_value=self.store), patch("sys.stdin", event), redirect_stdout(io.StringIO()):
            cli.hook_command(argparse.Namespace(event="session-start"))
        self.assertEqual(self.store.list_projects(), [])


if __name__ == "__main__":
    unittest.main()
