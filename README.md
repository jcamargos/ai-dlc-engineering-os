# AI-DLC Engineering OS

**Governed engineering memory and 26 specialist agents for Claude Code, Codex and VS Code — over MCP.**

[![CI](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jcamargos/ai-dlc-engineering-os)](https://github.com/jcamargos/ai-dlc-engineering-os/releases)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Local-first](https://img.shields.io/badge/runs-100%25%20local-success.svg)

By [AgentShield](https://agentshield.com.br) · [🇧🇷 Português](#português)

Coding agents forget. Every session starts from zero: the decision you made last month, the incident
that taught you to bound every retry, the convention your team agreed on. **AI-DLC Engineering OS**
gives your agents a durable, *governed* memory and a bench of specialist agents — and nothing becomes
a "rule" without evidence and human approval.

```text
Claude Code ─┐                            ┌─ memory: decisions · lessons · incidents · outcomes
Codex ───────┼── MCP (stdio) ── ai_dlc_os ─┼─ 26 specialist agents (contracts + evaluation gates)
VS Code ─────┘                            └─ governance: candidate → verified → human-approved
```

**Free and open source (Apache-2.0). Runs entirely on your machine — no account, no telemetry, no
hosted service.**

---

## Contents

[Quick start](#quick-start) · [What you get](#what-you-get) · [How it works](#how-it-works) ·
[Agents](#the-26-agents) · [Commands](#commands) · [Security](#security-model) · [FAQ](#faq) ·
[Uninstall](#uninstall) · [Contributing](#contributing)

## Quick start

**Requirements:** Python 3.10+ and Git. At least one of Claude Code, Codex or VS Code (GitHub Copilot
agent mode).

```bash
git clone https://github.com/jcamargos/ai-dlc-engineering-os
cd ai-dlc-engineering-os
./install/install.sh                                        # macOS / Linux
```

```powershell
git clone https://github.com/jcamargos/ai-dlc-engineering-os
cd ai-dlc-engineering-os
powershell -ExecutionPolicy Bypass -File .\install\install-windows.ps1   # Windows
```

The installer:

1. creates a private virtualenv in `~/.codex/ai-dlc-mcp` (nothing is installed system-wide);
2. backs up any existing memory database before touching it;
3. registers the `ai_dlc_os` MCP server **globally** in every host it finds:
   - **Codex:** `~/.codex/config.toml` + `AGENTS.md`
   - **Claude Code:** user-scope MCP, `CLAUDE.md` and 26 `ai-dlc-*` subagents
   - **VS Code / Insiders:** user-profile `mcp.json`
4. runs `doctor` to verify everything.

It is idempotent, keeps timestamped backups of every file it edits, and accepts
`--only codex|claude|vscode` and `--dry-run`. Restart your editor or agent, then ask:

> *"Resolve this project's id and give me its engineering context."*

## What you get

| | |
|---|---|
| **Memory that stays true** | FTS5/BM25 + local vector search over decisions, lessons, incidents and outcomes. Superseding instead of silent overwrite. The repository and its tests always win over memory. |
| **Safe by default** | Credentials are refused on every write. Instruction-like content is flagged and withheld from context. Hard purge for data that should not be there. |
| **Human governance** | Agents propose; only a human approves rules and releases (`ai-dlc-admin`, interactive terminal only). |
| **26 specialists** | Each with a contract, procedure, checklist, output format and escalation rules. |
| **Measured agent evolution** | Golden cases, quality/safety/non-regression gates, shadow → canary → active, hash-chained receipts, drift detection. |
| **Swarms** | Persistent, dependency-aware task graphs with atomic leases and isolated git worktrees. |
| **Mission Control** | Local visual control plane (`agentshield mission-control`), loopback-only. |

## How it works

A typical session, driven by your agent through its MCP tools (45, a few of them opt-in):

1. `resolve_project_id` → `get_project_context(project_id, task)`: relevant decisions, lessons and open incidents.
2. `list_agents` → `get_agent_context("principal-architect", project_id)`: the right specialist, with the project's approved rules.
3. Do the work. Persist only what is durable: `save_decision`, `record_learning`, `record_incident`.
4. `record_task_outcome` with evidence. Learnings stay **candidates** until verified; rules need **human approval**.

Memory lives in a single SQLite file (`~/.codex/ai-dlc-memory/memory.db`, WAL mode), shared by every
host on the machine. Schema migrations are versioned and run in place with a backup first.
Deeper dives: [Architecture](docs/ARCHITECTURE.md) · [Learning model](docs/LEARNING_MODEL.md) ·
[Agent evolution](docs/AGENT_EVOLUTION.md) · [Platform v3](docs/PLATFORM_V3.md).

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

## Commands

Installed into the virtualenv (`~/.codex/ai-dlc-mcp/.venv/bin/` or `…\.venv\Scripts\` on Windows):

| Command | Purpose |
|---|---|
| `ai-dlc-install install \| uninstall \| doctor` | register, remove or check the MCP server in Codex, Claude Code and VS Code |
| `ai-dlc-admin` | human governance: `candidates`, `rules approve/reject`, `learnings verify`, `releases`, `purge`, `merge-projects`, `export`, `backup`, `audit` |
| `agentshield init` | add a per-repository config (`--project-mcp` also writes `.mcp.json`) |
| `agentshield swarm …` | create, inspect and control persistent swarms |
| `agentshield mission-control` | local visual control plane on `127.0.0.1` |

Optional, off by default: federation (`AI_DLC_ENABLE_FEDERATION=1`) and marketplace
(`AI_DLC_ENABLE_MARKETPLACE=1`). The [Python and TypeScript SDK clients](sdk/typescript/README.md)
talk to any MCP Streamable HTTP server you point them at (`AI_DLC_REMOTE_URL`); nothing is contacted
unless you configure it.

## Security model

- **Write path:** secrets (API keys, tokens, private keys, connection strings) are rejected before storage.
- **Read path:** prompt-injection-like content is flagged and withheld from context packs; context is
  delivered as *data, not instructions*.
- **Human-only gates:** approvals and purges need an interactive terminal and a typed confirmation,
  which agents running non-interactive shells cannot satisfy.
- **Network:** none by default. Mission Control binds to loopback and rejects non-loopback hosts.

Report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## FAQ

**Does my code or memory leave my machine?** No. Everything is local SQLite; there is no telemetry.

**Do Claude Code and Codex share the same memory?** Yes. Every host on the machine uses the same
database, so a decision recorded in one is available in the others.

**Will it overwrite my existing `AGENTS.md`, `CLAUDE.md` or MCP config?** It edits only its own
marked block or server entry and keeps a timestamped backup of every file it touches.

**Can an agent approve its own rules?** No. Agents can only propose; approval requires `ai-dlc-admin`
in an interactive terminal.

## Uninstall

```bash
~/.codex/ai-dlc-mcp/.venv/bin/ai-dlc-install uninstall            # macOS / Linux
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install\uninstall-windows.ps1   # Windows
```

This removes the registrations from every host. Your memory stays in `~/.codex/ai-dlc-memory`;
delete that folder (and `~/.codex/ai-dlc-mcp`) to remove everything.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off:
`git commit -s`) and the [changelog](CHANGELOG.md). Not affiliated with Anthropic, OpenAI,
Microsoft or GitHub.

---

## Português

**AI-DLC Engineering OS** é memória de engenharia governada + 26 agentes especialistas para
Claude Code, Codex e VS Code, via MCP. Seus agentes passam a lembrar decisões, incidentes e padrões
do projeto — e nada vira "regra" sem evidência e aprovação humana.

**100% gratuito e open source (Apache-2.0).** Roda inteiro na sua máquina: sem conta, sem
telemetria, sem serviço hospedado.

### Instalação

Requisitos: Python 3.10+ e Git.

```powershell
git clone https://github.com/jcamargos/ai-dlc-engineering-os
cd ai-dlc-engineering-os
powershell -ExecutionPolicy Bypass -File .\install\install-windows.ps1   # Windows
# macOS / Linux: ./install/install.sh
```

O instalador cria um ambiente isolado, faz backup da memória existente e registra o servidor
`ai_dlc_os` globalmente no Codex, no Claude Code (com os 26 subagentes) e no VS Code. Depois, é só
reiniciar o editor e pedir: *"Resolva o id deste projeto e me dê o contexto de engenharia."*

### Por que usar

- **Memória que continua verdadeira:** decisões, lições, incidentes e resultados, com busca textual e
  vetorial local. O repositório e os testes sempre prevalecem sobre a memória.
- **Seguro por padrão:** segredos são recusados, conteúdo com cara de prompt injection é isolado, e há
  exclusão definitiva (LGPD).
- **Governança humana:** agentes propõem; só humanos aprovam (`ai-dlc-admin`, em terminal interativo).
- **Mesma memória no Claude Code, Codex e VS Code** da sua máquina.

Desinstalação: `.\install\uninstall-windows.ps1` (Windows) ou `~/.codex/ai-dlc-mcp/.venv/bin/ai-dlc-install uninstall`.
A memória é preservada.

Criado por José Camargo · [@jcamarguiho](https://www.instagram.com/jcamarguiho) · [agentshield.com.br](https://agentshield.com.br)
