# Installation

## One-command setup

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/).
uv can provision a compatible Python automatically. No administrator privileges
are required. Supported editors in this source version: Codex, Claude Code, Cursor and VS Code / Insiders
(default profiles). Open VS Code once before selecting it.

The native Codex, Copilot and Cursor additions are not yet on PyPI. To test them,
use the [candidate wheel instructions](NATIVE_AGENTS.md#install-the-candidate).
The published-package commands below only provide the features of that release.

```bash
uvx ai-dlc-engineering-os setup
```

Choose one or more editors, inspect the paths and confirm. Restart those editors.
Setup does not grant blanket permissions or pre-approve read-only tools.

Append `--editors codex,claude --dry-run` to preview without installation or edits.
Append `--editors codex --yes` for unattended installation with explicit consent.
Running the setup command again repairs registrations with the selected version.

The package is available on [PyPI](https://pypi.org/project/ai-dlc-engineering-os/).
To pin this release, use `uvx --from ai-dlc-engineering-os==3.2.0 ai-dlc-engineering-os setup`.
For installation directly from GitHub (requires Git), use:

```bash
uvx --from git+https://github.com/jcamargos/ai-dlc-engineering-os@v3.2.0 ai-dlc-engineering-os setup
```

## What changes

- A persistent `ai-dlc-engineering-os` environment under `uv tool dir`; MCP
  configuration points to its Python, never the temporary uvx environment.
- Codex: `~/.codex/config.toml`, a managed block in `~/.codex/AGENTS.md`, and
  26 native `~/.codex/agents/ai-dlc-*.toml` definitions.
- Claude Code: `~/.claude.json`, a managed block in `~/.claude/CLAUDE.md`, and
  26 managed `ai-dlc-*` subagent files. Existing permissions remain unchanged.
- VS Code / Insiders: `mcp.json` in detected default user profiles and
  26 personal `~/.copilot/agents/ai-dlc-*.agent.md` definitions.
- Cursor (select explicitly): `~/.cursor/mcp.json` and 26 `~/.cursor/agents/ai-dlc-*.md` definitions.
- See [native agent setup and verification](NATIVE_AGENTS.md).
- Existing edited configuration files receive timestamped `.backup.*` copies.
  Existing memory receives a SQLite online backup under its adjacent `backups/`
  directory before verification opens or migrates it.

Memory lives in `~/.ai-dlc/memory/memory.db`. Installations created before 3.2.0 keep using
`~/.codex/ai-dlc-memory/memory.db` automatically; nothing is moved. To adopt the new location,
close your editors and move that folder to `~/.ai-dlc/memory`. `AI_DLC_DATA_DIR` or `AI_DLC_DB_PATH`
override both. AI model-provider data handling is controlled
by your editor. Stop other setup/update processes before making configuration changes.

## Verify and recover

Setup runs `doctor` for each selected editor and checks a real MCP handshake.
A failed download does not edit registrations. A later error can leave completed
edits in place; the command reports failure and retains backups. Fix the error and
rerun setup, or restore the printed configuration backups with your editors closed.
VS Code JSONC files are left untouched: convert to plain JSON or register MCP
manually following the printed instructions, then rerun verification.

Installed commands are in the uv tool binary directory (`uv tool dir --bin`).
If they are not on PATH, follow uv's printed PATH instructions or invoke the
executable by its full path. For example, once on PATH:

```bash
ai-dlc-install doctor --only codex
```

## Update

Use the setup command from the newer release's README. Its pinned source installs
that version into the persistent tool environment and refreshes registrations.
Restart editors afterward. Previous source-script environments are left in place.
Do not run a previous source installer afterward unless intentionally reverting
registrations. Before a downgrade, check database-schema compatibility; a retained
backup is not an automatic database rollback.

## Install from source

Python 3.10+ and Git are required for the original source installers:

```bash
git clone https://github.com/jcamargos/ai-dlc-engineering-os
cd ai-dlc-engineering-os
./install/install.sh
```

On Windows, replace the final command with:

```powershell
powershell -ExecutionPolicy Bypass -File .\install\install-windows.ps1
```

These scripts install under `~/.codex/ai-dlc-mcp/.venv`; they retain their existing
behavior, including registering all hosts and pre-approving selected read tools
in Claude Code. The interactive setup above is the recommended path.

## Uninstall

For uv setup, use the installed commands (add the uv tool binary directory to
PATH if needed):

```bash
ai-dlc-install uninstall --no-cli
# If Cursor was configured:
ai-dlc-install uninstall --only cursor --no-cli
uv tool uninstall ai-dlc-engineering-os
```

To unregister only one editor, add `--only codex`, `--only claude`, or `--only vscode`
(or `--only cursor` for Cursor)
to the first command and keep the shared runtime installed for remaining editors.

For source-script installations, run
`~/.codex/ai-dlc-mcp/.venv/bin/ai-dlc-install uninstall` on macOS/Linux, or
`powershell -ExecutionPolicy Bypass -File .\install\uninstall-windows.ps1` on Windows.
Memory is preserved by all uninstall paths.

## Publish a new version (maintainer)

Publishing uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
with these configured values:

| Field | Value |
| --- | --- |
| PyPI project | `ai-dlc-engineering-os` |
| GitHub owner | `jcamargos` |
| Repository | `ai-dlc-engineering-os` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Then run **Publish to PyPI** from GitHub Actions on `main`. The workflow builds,
validates and smoke-tests the package before publishing through short-lived OIDC
credentials. No API token is stored in the repository. Each published version is
immutable; use a new version for subsequent package changes. After publication,
verify the short uvx command in an isolated home.
