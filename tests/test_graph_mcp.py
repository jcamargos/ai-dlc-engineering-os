"""Exercise the actual stdio protocol, not just Python store calls."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Install the declared MCP SDK for transport tests")
class GraphMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_work_over_stdio(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        with tempfile.TemporaryDirectory(prefix="ai-dlc-mcp-test-") as directory:
            root = Path(directory).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "api.py").write_text("import model\n", encoding="utf-8")
            (repo / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
            source = Path(__file__).resolve().parents[1] / "src"
            env = {**os.environ, "PYTHONPATH": str(source), "AI_DLC_DB_PATH": str(root / "memory.db"),
                   "AI_DLC_WORKSPACE_ID": "transport-test", "AI_DLC_GRAPH_ROOTS": str(repo)}
            server = StdioServerParameters(command=sys.executable,
                                           args=["-m", "ai_dlc_mcp.server"], env=env)
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    inventory = await session.list_tools()
                    self.assertTrue({"index_repository_graph", "query_repository_graph",
                                     "repository_graph_status"}.issubset({t.name for t in inventory.tools}))

                    async def call(name, args):
                        result = await session.call_tool(name, args, read_timeout_seconds=30)
                        self.assertFalse(result.is_error, f"{name} failed: {result.content}")
                        return result.structured_content or json.loads(result.content[0].text)

                    await call("bootstrap_project", {"project_id": "p", "name": "Fixture", "repo_path": str(repo)})
                    indexed = await call("index_repository_graph", {"project_id": "p"})
                    self.assertEqual(indexed["status"], "indexed")
                    result = await call("query_repository_graph", {"project_id": "p", "path": "model.py"})
                    self.assertEqual(result["edges"][0]["source"], "api.py")
                    (repo / "model.py").write_text("VALUE = 2\n", encoding="utf-8")
                    status = await call("repository_graph_status", {"project_id": "p"})
                    self.assertEqual(status["status"], "stale")
                    stale = await call("query_repository_graph", {"project_id": "p", "path": "model.py"})
                    self.assertEqual(stale["edges"], [])


if __name__ == "__main__":
    unittest.main()
