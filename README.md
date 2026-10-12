<div align="center">

# AI-DLC Engineering OS

### Engineering memory that carries across sessions.

**26 specialists. Evidence-backed knowledge. Human-governed rules.**

[![CI](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jcamargos/ai-dlc-engineering-os/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jcamargos/ai-dlc-engineering-os)](https://github.com/jcamargos/ai-dlc-engineering-os/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Local-first](https://img.shields.io/badge/memory-local--first-success.svg)

**[Quick start](#quick-start) · [How it works](#how-it-works) · [Agents](#the-26-agents) · [Documentation](#documentation) · [FAQ](#faq) · [Português](#português)**

<img src="docs/assets/engineering-workflow.svg" alt="Engineering workflow: load project context, select specialist contracts, verify results, and retain durable knowledge." width="1100" />

**For Claude Code, Codex and VS Code — through MCP.**

</div>

---

Decisions, incidents and conventions should survive a coding session.
**AI-DLC Engineering OS** gives your agents persistent project memory and
specialist contracts, with evidence and human approval governing what becomes a rule.

**Free and open source (MIT).** The memory server runs locally with SQLite:
no account, telemetry or hosted service required. Your AI client controls which
retrieved context it sends to its model provider. Remote SDK connections and
federation require explicit configuration.

## Quick start

### Set up your editor

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git, then run
this single command on Windows, macOS or Linux:

```bash
uvx --from git+https://github.com/jcamargos/ai-dlc-engineering-os@v3.1.0 ai-dlc-engineering-os setup
```

Choose Codex, Claude Code or VS Code, review the proposed changes, then confirm.
Setup installs a persistent runtime, backs up existing configuration and memory,
registers MCP and verifies the selected editors. Restart your editor afterward.
VS Code must have been opened once to create its default profile.

The short PyPI command `uvx ai-dlc-engineering-os setup` will become available
once the package is published there. Until then, use the GitHub command above.

### Ask your agent

```text
Resolve this project's id and give me its engineering context.
Identify the specialists relevant to my next change and propose a verification plan.
```

### Preview, update or uninstall

Add `--editors codex,claude --dry-run` to preview without applying changes.
For unattended setup, explicitly choose `--editors` and add `--yes`.

See the [installation guide](docs/INSTALLATION.md) for requirements, updates,
configuration paths, source installation, backups and uninstall instructions.

## What you get

| Capability | What it does |
|---|---|
| **Memory that stays true** | FTS5/BM25 + local vector search over decisions, lessons, incidents and outcomes. Superseding instead of silent overwrite. The repository and its tests always win over memory. |
| **Safe by default** | Credentials are refused on every write. Instruction-like content is flagged and withheld from context. Hard purge for data that should not be there. |
| **Human governance** | Agents propose; only a human approves rules and releases (`ai-dlc-admin`, interactive terminal only). |
| **26 specialists** | Each with a contract, procedure, checklist, output format and escalation rules. |
| **Measured agent evolution** | Golden cases, quality/safety/non-regression gates, shadow → canary → active, hash-chained receipts, drift detection. |
| **Swarms** | Persistent, dependency-aware task graphs with atomic leases and isolated git worktrees. |
| **Mission Control** | Local visual control plane (`agentshield mission-control`), loopback-only. |

## How it works

A typical session, driven by your agent through its MCP tools (40 enabled by default, plus 5 opt-in):

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

Setup installs these commands into the persistent uv tool environment (`uv tool dir`):

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
| [Platform v3](docs/PLATFORM_V3.md) | Swarms, Mission Control and opt-in capabilities |
| [SDK](sdk/typescript/README.md) | Remote MCP client configuration |
| [Benchmarks](benchmarks/README.md) | Reproducible measurement protocol |
| [Security policy](SECURITY.md) | Security controls and vulnerability reporting |
| [Changelog](CHANGELOG.md) | Release history |

## Uninstall

For the new uv setup, run the installed `ai-dlc-install uninstall --no-cli` command
before `uv tool uninstall ai-dlc-engineering-os`. Memory is preserved.
See [uninstall details](docs/INSTALLATION.md#uninstall), including source-script installs.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off:
`git commit -s`) and the [changelog](CHANGELOG.md). Not affiliated with Anthropic, OpenAI,
Microsoft or GitHub.

---

## Português

**AI-DLC Engineering OS** é memória de engenharia governada + 26 agentes especialistas para
Claude Code, Codex e VS Code, via MCP. Seus agentes passam a lembrar decisões, incidentes e padrões
do projeto — e nada vira "regra" sem evidência e aprovação humana.

**Gratuito e open source (MIT).** O servidor de memória roda localmente, sem conta,
telemetria ou serviço hospedado obrigatório. Seu cliente de IA controla o envio do contexto
recuperado ao provedor do modelo; conexões remotas são opcionais.

### Instalação

Instale [uv](https://docs.astral.sh/uv/getting-started/installation/) e Git. No Windows,
macOS ou Linux, execute:

```bash
uvx --from git+https://github.com/jcamargos/ai-dlc-engineering-os@v3.1.0 ai-dlc-engineering-os setup
```

Escolha os editores, revise as alterações e confirme. O assistente instala um
ambiente persistente, faz backups, registra o MCP e verifica os editores escolhidos.
Reinicie o editor e peça: *"Resolva o id deste projeto e me dê o contexto de engenharia."*

O comando curto via PyPI ainda depende da publicação do pacote. Veja o
[guia de instalação](docs/INSTALLATION.md) para atualização e desinstalação.

### Por que usar

- **Memória que continua verdadeira:** decisões, lições, incidentes e resultados, com busca textual e
  vetorial local. O repositório e os testes sempre prevalecem sobre a memória.
- **Seguro por padrão:** segredos são recusados, conteúdo com cara de prompt injection é isolado, e há
  exclusão definitiva (LGPD).
- **Governança humana:** agentes propõem; só humanos aprovam (`ai-dlc-admin`, em terminal interativo).
- **Mesma memória no Claude Code, Codex e VS Code** da sua máquina.

Desinstalação: siga o [guia](docs/INSTALLATION.md#uninstall). A memória é preservada.

Criado por José Camargo · [@jcamarguinho](https://www.instagram.com/jcamarguinho)
