# AI-DLC Engineering OS

**Governed engineering memory and 26 specialist agents for Claude Code, Codex and VS Code — over MCP.**
By [AgentShield](https://agentshield.com.br) · Apache-2.0 · [🇧🇷 Português](#português)

Coding agents forget. Every session starts from zero: the decision you made last month, the incident
that taught you to bound every retry, the convention your team agreed on. AI-DLC Engineering OS gives
your agents a durable, **governed** memory and a bench of specialist agents — and nothing becomes a
"rule" without evidence and human approval.

```text
Claude Code ─┐                          ┌─ memory: decisions · lessons · incidents · outcomes
Codex ───────┼── MCP (stdio) ── ai_dlc_os ┼─ 26 specialist agents (contracts + evaluation gates)
VS Code ─────┘                          └─ governance: candidate → verified → human-approved
```

## Install (one command)

```bash
git clone https://github.com/jcamargos/ai-dlc-engineering-os && cd ai-dlc-engineering-os
./install/install.sh                                   # macOS / Linux
powershell -ExecutionPolicy Bypass -File .\install\install-windows.ps1   # Windows
```

The installer creates a private virtualenv, backs up any existing memory database, and registers the
`ai_dlc_os` MCP server **globally**: Codex (`~/.codex/config.toml` + `AGENTS.md`), Claude Code
(user-scope MCP, `CLAUDE.md`, 26 subagents) and VS Code / Insiders (user-profile `mcp.json`). It is
idempotent, keeps timestamped backups and uninstalls cleanly. Then run `ai-dlc-install doctor`.

## What you get

| | |
|---|---|
| **Memory that stays true** | FTS5/BM25 + local vector search over decisions, lessons, incidents and outcomes; superseding instead of silent overwrite; repository and tests always win over memory |
| **Safe by default** | credentials are refused on every write; instruction-like content is flagged and withheld from context; hard purge for data that should not be there |
| **Human governance** | agents propose; only a human approves rules and releases (`ai-dlc-admin`, interactive TTY only) |
| **26 specialists** | orchestrator, architect, backend, frontend, data, security, threat-model, red-team, QA, SRE, release, AI/LLM… each with a contract, procedure, checklist, output format and escalation rules |
| **Measured agent evolution** | golden cases, quality/safety/non-regression gates, shadow → canary → active, hash-chained receipts, drift detection |
| **Swarms** | persistent dependency-aware task graphs with atomic leases and isolated git worktrees |

## Typical flow

1. `resolve_project_id` → `get_project_context(project_id, task)`
2. `list_agents` → `get_agent_context("principal-architect", project_id)`
3. do the work; persist only what is durable (`save_decision`, `record_learning`, `record_incident`)
4. `record_task_outcome` with evidence

## Open core

| Edition | What | License |
|---|---|---|
| **AI-DLC Engineering OS** (this repo) | local runtime, agents, installer, plugin, SDK clients | Apache-2.0, free |
| **AI-DLC OS Cloud** (AgentShield) | shared team memory, SSO/RBAC, audit, hosted evaluation & release pipeline, backups, retention | commercial — talk to us |

## Contributing & security
See [CONTRIBUTING.md](CONTRIBUTING.md) (CLA via sign-off) and [SECURITY.md](SECURITY.md).
Not affiliated with Anthropic, OpenAI, Microsoft or GitHub.

---

## Português

**AI-DLC Engineering OS** é memória de engenharia governada + 26 agentes especialistas para Claude Code,
Codex e VS Code, via MCP. Seus agentes passam a lembrar decisões, incidentes e padrões do projeto —
e nada vira "regra" sem evidência e aprovação humana.

- **Instalação:** um comando (acima). Registra o servidor `ai_dlc_os` globalmente no Codex, Claude Code e VS Code.
- **Seguro por padrão:** segredos são recusados, conteúdo com cara de prompt injection é isolado, exclusão definitiva (LGPD).
- **Governança humana:** agentes propõem; só humanos aprovam (`ai-dlc-admin`).
- **Licença:** Apache-2.0, gratuito. A versão para times (memória compartilhada, SSO, auditoria) é o **AI-DLC OS Cloud**, comercial.

Criado por José Camargo · [@jcamarguiho](https://www.instagram.com/jcamarguiho) · [agentshield.com.br](https://agentshield.com.br)
