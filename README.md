<div align="center">

# AI-DLC Engineering OS

<img src="docs/assets/ai-dlc-social-preview.jpg" alt="AI-DLC Engineering OS" width="860" />

**[English](README.md) | [Português (Brasil)](README.pt-BR.md) | [Español](README.es.md)**

### Your coding agents forget everything between sessions. This fixes that.

**Local memory for decisions, incidents and conventions. You approve what becomes a rule.**

[![CI](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-dlc-engineering-os)](https://pypi.org/project/ai-dlc-engineering-os/)
[![Downloads](https://img.shields.io/pypi/dm/ai-dlc-engineering-os)](https://pypistats.org/packages/ai-dlc-engineering-os)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Local-first](https://img.shields.io/badge/memory-local--first-success.svg)

**[Quick start](#quick-start) · [Why not CLAUDE.md?](#why-not-just-claudemd-or-agentsmd) · [Proof](#proof-not-promises) · [How it works](#how-it-works) · [FAQ](#faq)**

<img src="docs/assets/cross-session-demo.svg" alt="Recorded demo: session 1 saves a decision and the server refuses a credential; session 2, a new process, recalls the decision with no credential in context." width="860" />

**For Claude Code, Codex and VS Code — through MCP. Free and open source (Apache 2.0).**

</div>

---

On Monday your agent learns that payment writes need idempotency keys. On Tuesday, in a new
session or a different editor, it starts from zero. **AI-DLC Engineering OS** gives every
MCP-capable agent on your machine the same persistent project memory, plus 26 specialist
contracts, and nothing becomes a rule without evidence and your approval.

The memory server runs locally with SQLite: no account, telemetry or hosted service. Your AI
client controls which retrieved context it sends to its model provider.

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run this single
command on Windows, macOS or Linux:

```bash
uvx ai-dlc-engineering-os setup
```

Choose Codex, Claude Code or VS Code, review the proposed changes, then confirm. Setup installs
a persistent runtime, backs up existing configuration and memory, registers MCP and verifies
the selected editors. Restart your editor afterward. VS Code must have been opened once to
create its default profile.

Then just work. Open your project and ask:

```text
What do we already know about this codebase before I change the payment flow?
```

For Claude Code and Codex, setup adds instructions to `CLAUDE.md` and `AGENTS.md` that tell the agent to load
the project's decisions, lessons and open incidents before significant work. When you decide
something worth keeping, say so ("remember that we use idempotency keys on payment writes")
and it is available in the next session, in any configured editor.

Add `--editors codex,claude --dry-run` to preview without applying changes; for unattended setup
choose `--editors` explicitly and add `--yes`. The [installation guide](docs/INSTALLATION.md)
covers requirements, updates, pinned versions, backups and uninstall.

## Why not just CLAUDE.md or AGENTS.md?

Keep them. They are the right place for instructions you write by hand. This adds what a static
file cannot do well:

| | Instruction file | AI-DLC Engineering OS |
|---|---|---|
| Who writes it | You, by hand | Agents propose; you approve rules |
| Shared across editors | One file per tool | One local database for every configured editor |
| Grows without bloating context | Whole file loaded every time | Only what is relevant to the task is retrieved |
| Stale knowledge | Edited silently | Superseded with history; the repository and tests win over memory |
| Secrets pasted by accident | Saved as written | Refused on write |

## Proof, not promises

Every number below comes from a command in this repository, so you can rerun it.

| Check | Result | Reproduce |
|---|---|---|
| Cross-session recall (animation above) | Decision recalled by a new process; credential refused and absent from context | `python scripts/demo_cross_session.py` |
| Swarm lease reliability, 500 tasks, 8 workers | 500/500 completed, 0 duplicates, 0 lost | `python benchmarks/run_reliability.py --tasks 500 --workers 8` |
| Retrieval over 1,000 memories | 200/200 searches returned results, 104 ms mean | `ai-dlc benchmark --operations 1000 --searches 200` |
| Test suite | Current suite, including real MCP stdio sessions and graph migration | `pytest` |

Measured on a 2-vCPU Linux container with Python 3.13. These are reference numbers for one
machine, not capacity claims; see the [benchmark protocol](benchmarks/README.md). CI keeps the
demo and both benchmarks runnable.

## What you get

| Capability | What it does |
|---|---|
| **Memory that stays true** | FTS5/BM25 + local vector search over decisions, lessons, incidents and outcomes. Superseding instead of silent overwrite. The repository and its tests always win over memory. |
| **Safe by default** | Credentials are refused on every write. Instruction-like content is flagged and withheld from context. Hard purge for data that should not be there. |
| **Human governance** | Agents propose; only a human approves rules (`ai-dlc-admin`, interactive terminal only). |
| **26 specialists** | Each with a contract, procedure, checklist, output format and escalation rules. |
| **Measured agent evolution** | Golden cases, quality/safety/non-regression gates, shadow → canary → active, hash-chained receipts, drift detection. |

## How it works

<img src="docs/assets/engineering-workflow.svg" alt="Engineering workflow: load project context, select specialist contracts, verify results, and retain durable knowledge." width="1100" />

A typical session, driven by your agent through its MCP tools:

1. `resolve_project_id` → `get_project_context(project_id, task)`: relevant decisions, lessons and open incidents.
2. `list_agents` → `get_agent_context("principal-architect", project_id)`: the right specialist, with the project's approved rules.
3. Do the work. Persist only what is durable: `save_decision`, `record_learning`, `record_incident`.
4. `record_task_outcome` with evidence. Learnings stay **candidates** until verified; rules need **human approval**.

Memory lives in a single SQLite file (`~/.ai-dlc/memory/memory.db`, WAL mode), shared by every
host on the machine. Installations created before 3.2.0 keep using `~/.codex/ai-dlc-memory`
automatically. Schema migrations are versioned and run in place with a backup first.
Deeper dives: [Architecture](docs/ARCHITECTURE.md) · [Learning model](docs/LEARNING_MODEL.md) ·
[Agent evolution](docs/AGENT_EVOLUTION.md).

## Repository import graph (optional)

Available in this source checkout; install this revision to use the graph. The PyPI release may lag behind main.

Before editing a shared module, ask which files import it. The local graph returns
dependencies or transitive dependents with source lines, bounded depth and coverage.
Python uses AST parsing; JavaScript/TypeScript uses a lexical approximation.
Every query checks freshness and refuses stale results until you refresh the index.

Enable `AI_DLC_GRAPH_ROOTS` for the exact local Git roots the server may read, then
use `index_repository_graph`, `repository_graph_status` and `query_repository_graph`.
It is off by default, stores no source bodies, and requires no external service.
This is a file-import graph, not a complete call graph or a measured token-saving claim.
See the [setup, limitations and rollback guide](docs/REPOSITORY_GRAPH.md).

```shell
python scripts/demo_repository_graph.py
```

## The 26 agents

| Area | Agents |
|---|---|
| Coordination | `orchestrator`, `planner-requirements`, `product`, `research`, `knowledge-curator` |
| Architecture & build | `principal-architect`, `backend`, `frontend`, `data-database`, `integration-api`, `migration`, `ai-llm`, `ux-product-design`, `developer-experience` |
| Quality | `code-review`, `qa-verification`, `performance` |
| Security | `security`, `threat-model`, `red-team`, `governance-compliance` |
| Operations | `platform-sre`, `observability`, `incident-response`, `release`, `cloud-finops` |

Contracts live in [`contracts/agent_contracts.json`](contracts/agent_contracts.json) and guides in
[`src/ai_dlc_mcp/agents/`](src/ai_dlc_mcp/agents/). In Claude Code they are also available as
`ai-dlc-*` subagents.

Native subagent installation for Codex, VS Code/Copilot and Cursor is available in
this source branch; see [native agents](docs/NATIVE_AGENTS.md) for formats, installation
and live-editor verification. These definitions inherit your host model and permissions.

## Commands

Setup installs these commands into the persistent uv tool environment (`uv tool dir`):

| Command | Purpose |
|---|---|
| `ai-dlc-admin` | human governance: `candidates`, `rules approve/reject`, `learnings verify`, `releases`, `purge`, `merge-projects`, `export`, `backup`, `audit` |
| `ai-dlc-install install \| uninstall \| doctor` | register, remove or check the MCP server in Codex, Claude Code and VS Code |
| `ai-dlc init` | add a per-repository config (`--project-mcp` also writes `.mcp.json`) |
| `ai-dlc doctor` | check the local installation |

<details>
<summary><strong>Advanced: swarms, Mission Control, hooks and SDKs</strong></summary>

None of these are needed for the memory workflow above.

- **Swarms** (`ai-dlc swarm …`): persistent, dependency-aware task graphs with atomic leases and isolated git worktrees.
- **Mission Control** (`ai-dlc mission-control`): local visual control plane, loopback-only by default.
- **Hooks**: session, prompt, post-tool and stop events through the bundled plugin; they fail open.
- **SDK clients** for [Python and TypeScript](sdk/typescript/README.md) talk to an MCP Streamable HTTP
  server only when you point them at one (`AI_DLC_REMOTE_URL`).
- **Federation** is off unless `AI_DLC_ENABLE_FEDERATION=1`.

See [Advanced capabilities](docs/ADVANCED.md), including legacy compatibility identifiers.

</details>

## Security model

- **Write path:** secrets (API keys, tokens, private keys, connection strings) are rejected before storage.
- **Read path:** prompt-injection-like content is flagged and withheld from context packs; context is
  delivered as *data, not instructions*.
- **Human-only gates:** approvals and purges need an interactive terminal and a typed confirmation,
  which agents running non-interactive shells cannot satisfy.
- **Network:** none by default. Mission Control binds to loopback and rejects non-loopback hosts.

Report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## FAQ

<details>
<summary><strong>Does my code or memory leave my machine?</strong></summary>

The MCP server stores memory locally in SQLite and has no telemetry. Your AI
client may send retrieved context to its model provider under that client's
configuration. Federation and remote SDK connections are opt-in.

</details>

<details>
<summary><strong>Do Claude Code and Codex share the same memory?</strong></summary>

Yes. Hosts configured with the default data directory use the same database, so
a decision recorded in one is available in the others.

</details>

<details>
<summary><strong>I installed an earlier version. Where is my memory?</strong></summary>

Still in `~/.codex/ai-dlc-memory`, and it keeps being used; nothing is moved. To adopt the new
location, close your editors and move that folder to `~/.ai-dlc/memory`.

</details>

<details>
<summary><strong>Will it overwrite my existing agent or MCP configuration?</strong></summary>

The installer edits its own marked block or server entry in `AGENTS.md`,
`CLAUDE.md` and MCP configuration, and keeps timestamped backups.

</details>

<details>
<summary><strong>Can an agent approve its own rules?</strong></summary>

No. Agents can propose rules; approval requires `ai-dlc-admin` in an interactive
terminal. Specialist contracts guide the host agent; they do not train or replace
its model.

</details>

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/INSTALLATION.md) | Setup, updates, backups and uninstall |
| [Architecture](docs/ARCHITECTURE.md) | MCP hosts, SQLite, retrieval and trust boundaries |
| [Learning model](docs/LEARNING_MODEL.md) | Evidence, verification and knowledge lifecycle |
| [Agent evolution](docs/AGENT_EVOLUTION.md) | Evaluation gates, releases and drift |
| [Advanced capabilities](docs/ADVANCED.md) | Swarms, Mission Control, hooks and opt-in features |
| [Benchmarks](benchmarks/README.md) | Reproducible measurement protocol |
| [Security policy](SECURITY.md) | Security controls and vulnerability reporting |
| [Changelog](CHANGELOG.md) | Release history |

## Uninstall

Run the installed `ai-dlc-install uninstall --no-cli` command before
`uv tool uninstall ai-dlc-engineering-os`. Memory is preserved.
See [uninstall details](docs/INSTALLATION.md#uninstall), including source-script installs.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off:
`git commit -s`) and the [changelog](CHANGELOG.md). Not affiliated with Anthropic, OpenAI,
Microsoft or GitHub.

---

Created by José Camargo · [LinkedIn](https://www.linkedin.com/in/joseacamargo) · [Instagram @jcamarguinho](https://www.instagram.com/jcamarguinho)
