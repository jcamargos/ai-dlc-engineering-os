# Changelog

## Unreleased

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
