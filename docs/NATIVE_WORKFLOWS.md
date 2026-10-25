# Native engineering workflows

AI-DLC ships six on-demand procedures in its Python package. The CLI and MCP read
the same resources. All 26 generated agents receive a short routing instruction;
full procedures are loaded only when needed. There is no Superpowers dependency,
remote loader, new database schema or automatic agent delegation.

```sh
ai-dlc workflow list
ai-dlc workflow show debug
```

MCP clients can call the existing tool with an optional argument:

```json
{"agent_name": "backend", "project_id": "my-project", "workflow": "implement"}
```

Calls without `workflow` retain the specialist context and approved rules. Unknown
nonempty phase names fail explicitly. Loading a procedure reads bundled text; it
does not execute commands, write memory or advance a task automatically.

| Phase | Output expected from the agent |
| --- | --- |
| discover | Outcome, constraints, acceptance checks and resolved design choices |
| plan | Bounded tasks, dependencies, verification and durable handoffs |
| implement | Demonstrated behavior change and appropriate regression checks |
| debug | Reproducer, tested hypothesis, correction and supporting evidence |
| review | Requirement coverage, technical findings and verified resolutions |
| finish | Final-state checks, authorized delivery and recovery record |

Plans use the existing swarm ledger when coordination is warranted; procedures do
not introduce a second scheduler. Inline work remains available. Repository conventions
and the user's scope govern plan location, delegation and publication. Existing human
approval boundaries remain in force.

## Acceptance and verification

- All six resources are available from both an installed wheel and the CLI.
- MCP returns one requested phase alongside the specialist context, and none by default.
- Invalid names cannot select arbitrary resource paths.
- Existing callers, tool inventory and all native host formats remain compatible.
- Full tests and registry/platform/documentation checks cover regressions.

These checks verify distribution and interfaces. Procedures are model instructions,
not an enforced state machine: they cannot guarantee that a model follows each step.
The existing `ai-dlc eval` harness can grade host-observed runs; fixtures alone do not
measure behavior. Comparative evaluation must use matched tasks, model/configuration,
tool access and repetitions, retaining failures and reporting quality, total tokens,
cost, latency and human interventions. No superiority or savings claim is established
by this implementation.

## Provenance and rollback

Original AI-DLC procedures informed by public engineering practices and a review of
[Superpowers](https://github.com/obra/superpowers), particularly its planning, debugging,
test-driven development, review and completion workflows. No upstream skill files or
code are bundled. This is native implementation, not an integration or endorsement.

To stop loading procedures, omit `workflow` and use the existing agent context. To
roll back the package, reinstall the previous pinned revision and regenerate managed
native agents with the installer. Preserve local customizations/backups. No database
migration or data rollback is required. Restart host sessions to load changed agents.
