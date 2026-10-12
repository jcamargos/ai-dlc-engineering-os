"""Render one specialist catalog into each host's native agent format."""
from __future__ import annotations

import json
from pathlib import Path

from . import agents as catalog

MARK = "managed-by: agentshield-ai-dlc"
HOSTS = ("codex", "claude", "vscode", "cursor")
SUFFIX = {"codex": ".toml", "claude": ".md", "vscode": ".agent.md", "cursor": ".md"}


def directory(home: Path, host: str) -> Path:
    return home / {"codex": ".codex", "claude": ".claude", "vscode": ".copilot", "cursor": ".cursor"}[host] / "agents"


def instructions(spec: catalog.AgentSpec) -> str:
    return (
        f"{spec.body.strip()}\n{catalog.SHARED_INVARIANTS}\n"
        "## Delegation boundaries\n"
        "- Follow the parent's bounded task and the user's authorization; do not expand scope.\n"
        "- Use only host-enabled tools and permissions. Never bypass an approval or enable tools yourself.\n"
        "- Delegate only when authorized and supported; do not launch all specialists or recursively fan out.\n"
        "- Return findings, file references, checks performed and remaining uncertainty to the parent.\n"
        "## Memory protocol\n"
        "- Start: `resolve_project_id` then `get_project_context(project_id, task)` on MCP server `ai_dlc_os`.\n"
        f"- Load approved rules with `get_agent_context('{spec.name}', project_id)`.\n"
        "- If memory is unavailable, report it; never invent prior decisions or evidence.\n"
        "- Honor the contract's memory permissions. Return evidence to the parent for `record_task_outcome`\n"
        "  when you cannot write memory; persist only authorized, durable knowledge.\n"
        "- Approvals of rules and agent releases remain human-only.\n"
    )


def render(spec: catalog.AgentSpec, host: str) -> str:
    name = f"ai-dlc-{spec.name}"
    description = f"AI-DLC Engineering OS {spec.name}: {spec.description}"
    body = instructions(spec)
    if host == "codex":
        # JSON basic strings are also TOML basic strings (ensure_ascii avoids surrogate escapes).
        return (f"# {MARK}\nname = {json.dumps(name)}\n"
                f"description = {json.dumps(description, ensure_ascii=False)}\n"
                f"developer_instructions = {json.dumps(body, ensure_ascii=False)}\n")
    if host not in HOSTS:
        raise ValueError(f"Unsupported agent host: {host}")
    extra = "user-invocable: true\ndisable-model-invocation: false\n" if host == "vscode" else ""
    return (f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n"
            f"{extra}---\n<!-- {MARK} -->\n{body}")


def files(host: str) -> dict[str, str]:
    return {f"ai-dlc-{s.name}{SUFFIX[host]}": render(s, host) for s in catalog.all_specs()}
