"""End-to-end over the real MCP stdio transport, as Codex / Claude Code use it."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
EXPECTED_TOOLS = set(MANIFEST["mcp_tools"])
OPTIONAL_TOOLS = {t for group in MANIFEST["optional_mcp_tools"].values() for t in group}


def _text(res) -> str:
    return "".join(getattr(c, "text", "") for c in res.content)


class ServerE2E(unittest.TestCase):
    def test_full_session(self):
        asyncio.run(self._session())

    async def _session(self):
        with tempfile.TemporaryDirectory() as data:
            env = {k: v for k, v in os.environ.items() if not k.startswith("AI_DLC_ENABLE_")}
            env["AI_DLC_DATA_DIR"] = data
            params = StdioServerParameters(command=sys.executable, args=["-m", "ai_dlc_mcp.server"], env=env)
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    init = await s.initialize()
                    self.assertIn("resolve_project_id", init.instructions or "")
                    tools = {t.name: t for t in (await s.list_tools()).tools}
                    self.assertEqual(set(tools), EXPECTED_TOOLS)
                    self.assertTrue(tools["search_memory"].annotations.read_only_hint)
                    self.assertTrue(tools["purge_entry"].annotations.destructive_hint)

                    async def call(tool, **args):
                        res = await s.call_tool(tool, args)
                        return res, _text(res)

                    _, out = await call("bootstrap_project", project_id="Demo App", name="Demo")
                    self.assertEqual(json.loads(out)["id"], "demo-app")
                    await call("save_memory", kind="constraint", title="Tenancy", content="Every query filters tenant_id", project_id="demo-app")
                    res, out = await call("save_memory", kind="fact", title="CI", content="token ghp_" + "x" * 36, project_id="demo-app")
                    self.assertTrue(res.is_error)
                    self.assertIn("credential", out)
                    _, out = await call("get_project_context", project_id="demo-app", task="tenant filtering")
                    self.assertIn("tenant_id", out)
                    res, _ = await call("list_agents")
                    agents = res.structured_content["result"]
                    self.assertEqual(len(agents), 26)
                    self.assertTrue(all(a["description"] for a in agents))
                    _, out = await call("get_agent_context", agent_name="security")
                    self.assertIn("Shared invariants", out)
                    res, _ = await call("get_agent_context", agent_name="../../etc/passwd")
                    self.assertTrue(res.is_error)
                    _, out = await call("propose_agent_rule", agent_name="backend", rule_text="Bound outbound calls", rationale="hangs")
                    rule_id = json.loads(out)["id"]
                    res, out = await call("review_agent_rule", rule_id=rule_id, action="approve", reviewer="human")
                    self.assertTrue(res.is_error)
                    self.assertIn("ai-dlc-admin", out)
                    _, out = await call("memory_stats")
                    self.assertIn(json.loads(out)["search"], {"fts5-bm25", "scan"})


class OptInToolsE2E(unittest.TestCase):
    def test_federation_and_marketplace_only_when_enabled(self):
        async def run():
            with tempfile.TemporaryDirectory() as data:
                env = {**os.environ, "AI_DLC_DATA_DIR": data, "AI_DLC_ENABLE_FEDERATION": "1", "AI_DLC_ENABLE_MARKETPLACE": "1"}
                params = StdioServerParameters(command=sys.executable, args=["-m", "ai_dlc_mcp.server"], env=env)
                async with stdio_client(params) as (r, w):
                    async with ClientSession(r, w) as s:
                        await s.initialize()
                        names = {t.name for t in (await s.list_tools()).tools}
                        self.assertEqual(names, EXPECTED_TOOLS | OPTIONAL_TOOLS)
                        tools = {t.name: t for t in (await s.list_tools()).tools}
                        self.assertTrue(tools["dispatch_federation_message"].annotations.open_world_hint)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
