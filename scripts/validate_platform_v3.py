from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.2.0"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_json(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def main() -> None:
    manifest = load_json("manifest.json")
    plugin = load_json("plugins/ai-dlc-os/plugin.json")
    codex = load_json("plugins/ai-dlc-os/.codex-plugin/plugin.json")
    claude = load_json("plugins/ai-dlc-os/.claude-plugin/plugin.json")
    hooks = load_json("plugins/ai-dlc-os/hooks/hooks.json")
    marketplace = load_json(".agents/plugins/marketplace.json")
    claude_marketplace = load_json(".claude-plugin/marketplace.json")
    typescript = load_json("sdk/typescript/package.json")
    for name, value in (("manifest", manifest), ("portable plugin", plugin), ("Codex plugin", codex), ("Claude plugin", claude), ("TypeScript SDK", typescript)):
        require(value.get("version") == VERSION, f"{name} version must be {VERSION}")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    require(f'version = "{VERSION}"' in pyproject, "Python package version is not aligned")
    require(plugin.get("hooks") == "./hooks/hooks.json", "portable plugin must declare hooks")
    require(plugin.get("mcpServers") == "./.mcp.json", "portable plugin must declare its MCP server")
    require(set(hooks.get("hooks", {})) == {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}, "routing, memory and evaluation hook events are required")
    require(any(item.get("name") == "ai-dlc-os" for item in marketplace.get("plugins", [])), "repo marketplace must publish the AgentShield plugin")
    require(any(item.get("name") == "ai-dlc-os" and item.get("version") == VERSION for item in claude_marketplace.get("plugins", [])), "Claude marketplace must publish the versioned AgentShield plugin")
    tools = manifest.get("mcp_tools", [])
    optional = [t for group in manifest.get("optional_mcp_tools", {}).values() for t in group]
    require(len(tools) == 40 and len(set(tools)) == 40, "local manifest must expose 40 unique default tools")
    require(len(optional) == 5 and not set(optional) & set(tools), "local manifest must list 5 distinct opt-in tools")
    server = (ROOT / "src/ai_dlc_mcp/server.py").read_text(encoding="utf-8")
    declared = re.findall(r"^\s*@tool\(.*\)\s*\n\s*def (\w+)", server, re.MULTILINE)
    require(sorted(declared) == sorted(tools + optional), "local MCP implementation/tool manifest mismatch")
    for path in (
        "apps/mission-control/index.html",
        "src/agentshield_sdk/client.py",
        "sdk/typescript/src/index.ts",
        "benchmarks/run_reliability.py",
    ):
        require((ROOT / path).is_file(), f"required Platform v3 artifact missing: {path}")
    combined = json.dumps({"plugin": plugin, "hooks": hooks, "marketplace": marketplace}).lower()
    require(not any(key in combined for key in ("service_role", "anon_key", "bearer eyj")), "plugin manifests must not embed credentials")
    print("Platform v3 valid: portable plugin, 40+5 local tools, SDKs, swarms, federation, marketplace and benchmarks")


if __name__ == "__main__":
    main()
