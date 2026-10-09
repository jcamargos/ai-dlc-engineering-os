"""Exercise the installed MCP runtime rather than mocking the transport."""
import json
from pathlib import Path
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]


def test_installed_server_contract_and_project_round_trip(tmp_path):
    async def probe():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai_dlc_mcp.server"],
            cwd=tmp_path,
            env={
                "AI_DLC_DB_PATH": str(tmp_path / "ephemeral.db"),
                "AI_DLC_WORKSPACE_ID": "verification-only",
                "AI_DLC_ALLOW_RULE_APPROVAL": "0",
                "AI_DLC_ALLOW_AGENT_RELEASE_APPROVAL": "0",
            },
        )
        with anyio.fail_after(30):
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=10) as session:
                    initialized = await session.initialize()
                    assert initialized.server_info.name == "AgentShield AI-DLC Engineering OS"
                    actual = await session.list_tools()
                    expected = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
                    assert {tool.name for tool in actual.tools} == set(expected["mcp_tools"])
                    created = await session.call_tool("bootstrap_project", {
                        "project_id": "isolated-probe", "name": "Ephemeral verification project",
                    })
                    assert not created.is_error
                    context = await session.call_tool("get_project_context", {
                        "project_id": "isolated-probe", "task": "Verify MCP interoperability",
                    })
                    assert not context.is_error
                    assert "isolated-probe" in "".join(
                        item.text for item in context.content if item.type == "text"
                    )

    anyio.run(probe)
