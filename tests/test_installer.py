"""Installer must be idempotent, preserve user content and uninstall cleanly."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ai_dlc_mcp import agents as catalog
from ai_dlc_mcp import installer

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

USER_CONFIG = """model = "gpt-x"

[mcp_servers.other]
command = "node"

[mcp_servers.ai_dlc_memory]
command = "C:\\\\old\\\\python.exe"
args = ["-m", "ai_dlc_mcp.server"]
cwd = "C:\\\\old"

[mcp_servers.ai_dlc_memory.env]
X = "1"

[projects.'c:\\\\work']
trust_level = "trusted"
"""


@unittest.skipIf(tomllib is None, "tomllib requires Python 3.11+")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "config.toml").write_bytes(b"\xef\xbb\xbf" + USER_CONFIG.encode())
        legacy = "# My OS\nkeep me\n\n<!-- AI-DLC-MCP:BEGIN -->\nold â†’ text\n<!-- AI-DLC-MCP:END -->\n"
        (self.home / ".codex" / "AGENTS.md").write_text(legacy, encoding="utf-8")
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "CLAUDE.md").write_text("# Personal rules\nBe concise.\n", encoding="utf-8")
        (self.home / ".claude" / "agents").mkdir()
        (self.home / ".claude" / "agents" / "agentshield-mine.md").write_text("user-owned, not managed", encoding="utf-8")
        legacy_server = {"type": "stdio", "command": "C:/old/python.exe", "args": ["-m", "ai_dlc_mcp.server"]}
        (self.home / ".claude.json").write_text(json.dumps(
            {"numStartups": 3, "mcpServers": {"x": {"command": "y"}, "ai_dlc_memory": legacy_server}}), encoding="utf-8")
        (self.home / ".claude" / "settings.json").write_text(json.dumps(
            {"permissions": {"allow": ["Bash(git status)", "mcp__ai_dlc_memory__search_memory"]}}), encoding="utf-8")
        (self.home / ".claude" / "agents" / "agentshield-security.md").write_text(
            "---\nname: agentshield-security\n---\n" + installer.MANAGED_MARK + "\nold", encoding="utf-8")
        self.python = str(self.home / "venv" / "python.exe")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()):
            return installer.main([*args, "--home", str(self.home), "--python", self.python, "--no-cli"])

    def test_install_is_idempotent_and_preserves_user_content(self):
        self.assertEqual(self.run_cli("install"), 0)
        snapshot = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file() and ".backup." not in p.name}
        self.assertEqual(self.run_cli("install"), 0)
        after = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file() and ".backup." not in p.name}
        self.assertEqual(snapshot, after, "second install must be a no-op")

        cfg_bytes = (self.home / ".codex" / "config.toml").read_bytes()
        self.assertFalse(cfg_bytes.startswith(b"\xef\xbb\xbf"))
        cfg = tomllib.loads(cfg_bytes.decode())
        self.assertEqual(cfg["mcp_servers"]["ai_dlc_os"]["command"], self.python)
        self.assertNotIn("ai_dlc_memory", cfg["mcp_servers"], "legacy server key must be migrated away")
        self.assertEqual(cfg["mcp_servers"]["other"]["command"], "node")
        self.assertEqual(cfg["model"], "gpt-x")
        self.assertIn("c:\\\\work", cfg["projects"])

        agents_md = (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("keep me", agents_md)
        self.assertNotIn("â†", agents_md)
        self.assertEqual(agents_md.count(installer.BEGIN), 1)

        claude_md = (self.home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Be concise.", claude_md)
        self.assertIn("@~/.codex/AGENTS.md", claude_md)

        cj = json.loads((self.home / ".claude.json").read_text(encoding="utf-8"))
        self.assertEqual(cj["numStartups"], 3)
        self.assertEqual(cj["mcpServers"]["ai_dlc_os"]["command"], self.python)
        self.assertNotIn("ai_dlc_memory", cj["mcpServers"])
        self.assertIn("x", cj["mcpServers"])

        agents_dir = self.home / ".claude" / "agents"
        self.assertEqual(len(list(agents_dir.glob("ai-dlc-*.md"))), len(catalog.all_specs()))
        self.assertEqual([p.name for p in agents_dir.glob("agentshield-*.md")], ["agentshield-mine.md"],
                         "managed legacy subagents are removed, user-owned files are kept")
        sample = (agents_dir / "ai-dlc-security.md").read_text(encoding="utf-8")
        self.assertTrue(sample.startswith("---\nname: ai-dlc-security\ndescription: \"AI-DLC Engineering OS security: "))
        self.assertIn("Shared invariants", sample)

        allow = json.loads((self.home / ".claude" / "settings.json").read_text())["permissions"]["allow"]
        self.assertIn("mcp__ai_dlc_os__get_project_context", allow)
        self.assertNotIn("mcp__ai_dlc_os__purge_entry", allow)
        self.assertIn("Bash(git status)", allow)
        self.assertFalse([a for a in allow if a.startswith("mcp__ai_dlc_memory__")])

    def test_uninstall_removes_only_managed_content(self):
        self.run_cli("install")
        self.assertEqual(self.run_cli("uninstall"), 0)
        cfg = tomllib.loads((self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertNotIn("ai_dlc_os", cfg["mcp_servers"])
        self.assertNotIn("ai_dlc_memory", cfg["mcp_servers"])
        self.assertIn("other", cfg["mcp_servers"])
        self.assertNotIn(installer.BEGIN, (self.home / ".codex" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("Be concise.", (self.home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertNotIn("ai_dlc_os", json.loads((self.home / ".claude.json").read_text())["mcpServers"])
        left = sorted(p.name for p in (self.home / ".claude" / "agents").glob("*.md"))
        self.assertEqual(left, ["agentshield-mine.md"])
        allow = json.loads((self.home / ".claude" / "settings.json").read_text())["permissions"]["allow"]
        self.assertEqual(allow, ["Bash(git status)"])

    def test_dry_run_changes_nothing(self):
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(self.run_cli("install", "--dry-run"), 0)
        after = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_fresh_machine_without_codex_gets_self_contained_claude_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                installer.main(["install", "--only", "claude", "--home", tmp, "--python", self.python, "--no-cli"])
            text = (Path(tmp) / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("resolve_project_id", text)
            self.assertNotIn("@~/.codex", text)


if __name__ == "__main__":
    unittest.main()


class SnippetSyncTests(unittest.TestCase):
    def test_repository_snippet_matches_installer(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "AGENTS-MCP-SNIPPET.md").read_text(encoding="utf-8")
        self.assertEqual(text, f"{installer.BEGIN}\n{installer.SNIPPET.strip()}\n{installer.END}\n")


def _vscode_user_dir(home: Path, flavour: str = "Code") -> Path:
    import sys as _sys
    if _sys.platform.startswith("win"):
        base = home / "AppData" / "Roaming"
    elif _sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = home / ".config"
    path = base / flavour / "User"
    path.mkdir(parents=True)
    return path


class VSCodeInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.python = str(self.home / "venv" / "python")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()) as out:
            code = installer.main([*args, "--only", "vscode", "--home", str(self.home), "--python", self.python, "--no-cli"])
        return code, out.getvalue()

    def test_registers_migrates_and_preserves_other_servers(self):
        user = _vscode_user_dir(self.home)
        insiders = _vscode_user_dir(self.home, "Code - Insiders")
        (user / "mcp.json").write_text(json.dumps({"servers": {"github": {"type": "http", "url": "https://x"},
                                                              "ai_dlc_memory": {"command": "old"}}, "inputs": []}), encoding="utf-8")
        self.assertEqual(self.run_cli("install")[0], 0)
        data = json.loads((user / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(data["servers"]["ai_dlc_os"], {"type": "stdio", "command": self.python, "args": ["-m", "ai_dlc_mcp.server"]})
        self.assertIn("github", data["servers"])
        self.assertNotIn("ai_dlc_memory", data["servers"])
        self.assertEqual(data["inputs"], [])
        self.assertIn("ai_dlc_os", json.loads((insiders / "mcp.json").read_text(encoding="utf-8"))["servers"])
        before = (user / "mcp.json").read_bytes()
        self.run_cli("install")
        self.assertEqual(before, (user / "mcp.json").read_bytes(), "second install must be a no-op")
        self.run_cli("uninstall")
        data = json.loads((user / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(list(data["servers"]), ["github"])

    def test_jsonc_files_are_left_untouched(self):
        user = _vscode_user_dir(self.home)
        jsonc = '{\n  // my servers\n  "servers": {}\n}\n'
        (user / "mcp.json").write_text(jsonc, encoding="utf-8")
        code, out = self.run_cli("install")
        self.assertEqual(code, 0)
        self.assertEqual((user / "mcp.json").read_text(encoding="utf-8"), jsonc)
        self.assertIn("code --add-mcp", out)

    def test_skips_when_vscode_not_installed(self):
        code, out = self.run_cli("install")
        self.assertEqual(code, 0)
        self.assertIn("VS Code not detected", out)
