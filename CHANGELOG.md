# Changelog

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
