# Native specialist agents

The source installer generates all 26 specialists from the catalog in
`src/ai_dlc_mcp/agents/`, including the generated contracts and shared invariants.
This feature is unreleased: use a wheel built from this branch until a new PyPI
release includes it. Installing an older PyPI version does not install these additions.

| Client | Personal definitions | MCP registration |
| --- | --- | --- |
| Codex | `~/.codex/agents/ai-dlc-*.toml` | `~/.codex/config.toml` |
| Claude Code | `~/.claude/agents/ai-dlc-*.md` | `~/.claude.json` |
| VS Code / Copilot | `~/.copilot/agents/ai-dlc-*.agent.md` | Default profile `mcp.json` |
| Cursor | `~/.cursor/agents/ai-dlc-*.md` | `~/.cursor/mcp.json` |

Use a current client supporting these native formats. VS Code means its local
Copilot agent experience; the Codex extension follows Codex configuration instead.
Cursor introduced subagents in 2.4; older clients must be updated first.
Remote hosts need installation on that host. VS Code custom profiles and old
profile-based agent storage are not automatically migrated.

## Install the candidate

From a checkout with Python and build installed:

```bash
python -m build --wheel
```

Use the actual wheel path printed by the build:

```text
uvx --from /path/to/package.whl ai-dlc-engineering-os setup --editors codex,claude,vscode,cursor
```

Add `--dry-run` to preview. Setup requests confirmation before writing. For scripted
installation, explicitly add `--yes`. Open VS Code once before selecting it.
Restart the selected clients or start fresh sessions after installation.

The installer preserves unrelated agents and configuration. A colliding unmanaged
`ai-dlc-*` file stops installation; rename that file intentionally before retrying.
Managed files are regenerated from the catalog, with timestamped backups before
updates or removal. Keep personal variants under a different name. Existing
Claude-compatible definitions might also be discovered by other clients; the
client's precedence rules apply. Do not run two installers concurrently.

Model choices, tool approvals, sandbox settings and concurrency limits remain
under client/user control. Files do not grant permission to delegate or approve
rules. Memory access remains subject to each contract and the host's enabled MCP
tools. The parent records evidence when a specialist has read-only memory access.

## Verify

Run `ai-dlc-install doctor --only codex` (or `claude`, `vscode`, `cursor`) using
the installed tool. Doctor checks catalog parity, exact generated file contents,
registration and a real server handshake. It does **not** prove live editor
discovery, model routing or delegation.

In a fresh client session, ask:

> Use the ai-dlc-code-review subagent to review this branch without editing files.
> Report its findings, evidence and whether project memory was available.

Check that the client shows a separate subagent invocation with the expected name,
that it returns findings to the parent and that it can access the configured MCP
tools. Merely adopting a role in the parent conversation is not a passing result.
In Copilot, ensure the Run Subagent tool is enabled; if missing, use the client
configuration UI. Cursor also supports `/ai-dlc-code-review` invocation.
Use a normal persisted Codex session for this test: Codex CLI 0.162.1 discovered
the custom role with `exec --ephemeral`, but delegation failed because its parent
thread had no stored rollout. A discovered role alone does not prove execution.

## Uninstall / rollback

```bash
ai-dlc-install uninstall --only cursor --no-cli
```

Replace `cursor` with the selected client. Only marked native agent files are
removed, with backups. Memory is retained. Restore configuration and agent backups
with editors closed if rollback is needed; restoring files does not downgrade the
database schema. Keep the shared runtime if other clients still use it.

## Format references

- [Codex custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)
- [VS Code custom agents](https://code.visualstudio.com/docs/agent-customization/custom-agents)
- [VS Code subagent execution](https://code.visualstudio.com/docs/agents/run/subagents)
- [Cursor subagents](https://cursor.com/docs/subagents)
- [Cursor 2.4 release](https://cursor.com/changelog/2-4)
- [Cursor MCP](https://cursor.com/docs/mcp)

Formats checked on 2026-10-12. Host discovery must be checked again when a client
changes its configuration format.
