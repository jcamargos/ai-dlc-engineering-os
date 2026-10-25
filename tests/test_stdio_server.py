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
                    assert initialized.server_info.name == "AI-DLC Engineering OS"
                    actual = await session.list_tools()
                    expected = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
                    assert {tool.name for tool in actual.tools} == set(expected["mcp_tools"])
                    agent_tool = next(tool for tool in actual.tools if tool.name == "get_agent_context")
                    assert "workflow" in agent_tool.input_schema["properties"]
                    baseline = await session.call_tool("get_agent_context", {"agent_name": "backend"})
                    assert not baseline.is_error
                    base_text = "".join(item.text for item in baseline.content if item.type == "text")
                    assert "# Native workflow:" not in base_text
                    for phase in ("discover", "plan", "implement", "debug", "review", "finish"):
                        loaded = await session.call_tool("get_agent_context", {
                            "agent_name": "backend", "workflow": phase,
                        })
                        assert not loaded.is_error
                        text = "".join(item.text for item in loaded.content if item.type == "text")
                        assert base_text in text
                        assert text.count("# Native workflow:") == 1
                        assert f"# Native workflow: {phase}" in text
                    invalid = await session.call_tool("get_agent_context", {
                        "agent_name": "backend", "workflow": "../agents/backend",
                    })
                    assert invalid.is_error
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
                    created_swarm = await session.call_tool("create_swarm", {
                        "project_id": "isolated-probe", "objective": "Resume fixture",
                        "tasks": [{"id": "stdio-task"}],
                    })
                    assert not created_swarm.is_error
                    run = created_swarm.structured_content or json.loads(created_swarm.content[0].text)
                    recovered = await session.call_tool("get_swarm", {"swarm_id": run["id"], "recovery": True})
                    assert not recovered.is_error
                    view = recovered.structured_content or json.loads(recovered.content[0].text)
                    assert view["ready"][0]["id"] == "stdio-task"
                    assert view["completed"] == []

    anyio.run(probe)
