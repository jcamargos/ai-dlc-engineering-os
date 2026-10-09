# Architecture (local edition)

```text
MCP host (Claude Code · Codex · VS Code)
   │  stdio, one process per host session
   ▼
ai_dlc_mcp.server  ── tool layer: annotations, validation, ToolError messages
   │
   ├── security.py      credential refusal, injection flags, limits, id normalisation
   ├── store (mixins)   memory · decisions · lessons · incidents · outcomes · rules
   │                    evolution (eval → release → receipts → drift) · swarms · vectors
   ├── agents/          26 guides + contract blocks (contracts/agent_contracts.json)
   └── SQLite (WAL)     ~/.codex/ai-dlc-memory/memory.db, shared by every host
```

**One database, many hosts.** Every host spawns its own server process against the same file.
WAL, `busy_timeout`, short-lived connections and `BEGIN IMMEDIATE` writes keep concurrent sessions
safe. Migrations are versioned with `PRAGMA user_version` and run once, transactionally, with a
foreign-key check before commit.

**Retrieval.** BM25 over an FTS5 index containing only retrievable state (active memories,
non-rejected lessons, approved rules, decisions, incidents, outcomes), plus optional vector search
(`agentshield-local-v1` feature hashing, or caller-supplied embeddings). Context packs are budgeted and
labelled as data, never instructions; flagged items are withheld.

**Governance boundary.** The MCP surface can propose, reject and record, but cannot approve. Rule
approval, human verification, release approval, purge-project and merge-projects live in
`ai-dlc-admin`, which requires an interactive terminal and a typed confirmation.

**Opt-in surfaces.** Federation (`AI_DLC_ENABLE_FEDERATION=1`) sends signed data to other machines and
the marketplace (`AI_DLC_ENABLE_MARKETPLACE=1`) has no external trust root; both are off by default.
Mission Control binds to loopback and rejects non-loopback Host headers.

**Cloud.** AI-DLC OS Cloud (commercial) exposes the same concepts over Streamable HTTP with OAuth,
PostgreSQL row-level tenant isolation and a hosted evaluation/release pipeline. The local edition does
not depend on it.
