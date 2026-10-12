# Changelog

## 3.2.0 - one command name and evidence-led README (2026-10-12)

- **One command name.** `ai-dlc` replaces `agentshield`; the old name stays as a deprecated alias
  that prints a notice. Repository config moves to `.ai-dlc/config.json`; an existing
  `.agentshield/config.json` is still read. Swarm worktrees and branches use the `ai-dlc` prefix.
  `AI_DLC_CONTROL_TOKEN` is accepted alongside `AGENTSHIELD_CONTROL_TOKEN`.
- **Editor-neutral memory location.** New installations store memory in `~/.ai-dlc/memory`.
  Existing databases in `~/.codex/ai-dlc-memory` keep being used automatically; nothing is moved.
- **Benchmarks fixed.** `ai-dlc benchmark` failed on an invalid memory kind, and the documented
  reliability run exceeded the 500-task swarm limit. Both now run, and CI exercises them.
- **Reproducible demo.** `scripts/demo_cross_session.py` shows recall across two server processes
  and credential refusal, and renders the README animation.
- README: problem-first hook, comparison with instruction files, measured results, advanced
  features collapsed, PyPI badges. `docs/PLATFORM_V3.md` is now `docs/ADVANCED.md`.

## 3.1.0 - one-command setup

- Add `ai-dlc-engineering-os setup`: editor selection, preview and confirmation,
  persistent uv tool installation, configuration and memory backups, and checks
  limited to the selected editors. No read-tool permissions are pre-approved.
- Add a GitHub-source one-command installation path and prepare PyPI trusted publishing.
- Document installation, updates, verification and uninstall in a dedicated guide.

## 3.0.2 - MIT license and refreshed documentation (2026-10-12)

- Change the project license to MIT, including Python, SDK and plugin metadata.
  Previously published releases retain their original license notices.
- Refresh the README with a workflow diagram, navigation, collapsible FAQ and
  documentation index; remove website links and clarify local memory behavior.

## 3.0.1 - free and local by default

- **No implicit remote endpoint.** The Python and TypeScript SDK clients and `agentshield init` no
  longer default to any hosted server. Pass an endpoint explicitly or set `AI_DLC_REMOTE_URL`;
  without one, `init` configures a local-only project. Breaking only for callers that relied on
  the implicit default.
- 100% free and open source: removed references to hosted offerings and the remote example config;
  contributions now use the DCO sign-off instead of a CLA.
- README rewritten: badges, requirements, what the installer changes, agents, commands, security
  model, FAQ and uninstall.
- Test fixtures no longer reference private repository names.

## 3.0.0 - first open-source release (Apache-2.0)

Initial public release of AI-DLC Engineering OS, the local edition of AgentShield.

- Governed engineering memory (SQLite/WAL): FTS5/BM25 and local vector search, decisions,
  lessons, incidents, outcomes, versioned in-place migrations, hard purge, project merge.
- 26 specialist agents with contracts, evaluation gates, staged releases, receipts and drift.
- Human-only governance through `ai-dlc-admin`; credentials refused on every write.
- Persistent swarms with leases and worktrees; Mission Control; opt-in federation/marketplace.
- `ai-dlc-install`: one-command global setup for Codex, Claude Code (MCP, CLAUDE.md, 26 subagents)
  and VS Code (GitHub Copilot agent mode); doctor and clean uninstall.
- Native plugin for Codex and Claude Code; Python and TypeScript SDK clients.
