# Architecture (local edition)

**Native procedures.** `ai_dlc_mcp.workflows` owns six bundled phase resources shared
by CLI and the optional `get_agent_context(..., workflow=...)` parameter. A short
router reaches every native agent through shared invariants. Only an allowlisted
phase is read; no external plugin, executor or database mutation is involved.
See [workflow contracts and limits](NATIVE_WORKFLOWS.md).

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
   └── SQLite (WAL)     ~/.ai-dlc/memory/memory.db, shared by every host
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

**Remote clients.** The Python and TypeScript SDK clients speak MCP Streamable HTTP to any compatible
server you choose (`AI_DLC_REMOTE_URL`); nothing is contacted unless you configure it.

**Optional repository graph.** Three tools index and query file imports in Git roots
authorized through `AI_DLC_GRAPH_ROOTS`. The source scanner has file/byte/time budgets;
Python uses AST and JS/TS uses a labeled lexical approximation. Schema v3 adds a disposable
workspace/project-owned snapshot with a cascading foreign key. Every query validates its
fingerprint; stale snapshots return no edges. Project merges discard both indexes; purges
cascade. Graphs are not injected into durable memory or exported as lessons. See
[configuration, threat boundaries and rollback](REPOSITORY_GRAPH.md).

**Verified execution.** Optional local CLI helpers bind command evidence to origin,
HEAD and file fingerprints and grade six host-observed behavioral scenarios. Explicit
imports reuse existing evaluation tables; recovery uses existing swarm leases without
changing state. No model calls, automatic approvals or schema migration are added.
See [trust limits and acceptance criteria](VERIFIED_EXECUTION.md).
