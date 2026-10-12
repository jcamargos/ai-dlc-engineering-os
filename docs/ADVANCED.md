# Advanced capabilities

Swarms, Mission Control, hooks, SDKs and opt-in federation. None of these are needed
for the core memory workflow described in the README.

## Capability map

| Capability | Implementation | Safety boundary |
|---|---|---|
| Native plugin | Portable `plugin.json`, Codex and Claude compatibility manifests, MCP, skill and hooks | Hooks have 5–10 second bounds and fail open |
| Init and doctor | `ai-dlc init`, `ai-dlc doctor` | Writes repository-local config; network diagnostic is opt-in |
| Automatic hooks | Session, prompt, post-tool and stop events | Redacted allowlist output; no raw prompt/content persistence |
| Swarms | SQLite/PostgreSQL DAG, atomic leases, lifecycle controls | Bounded parallelism, lease ownership, expiry recovery, audit log |
| Worktrees | `create_swarm_worktree` | Validated repository and target root; no automatic deletion |
| SDKs | `agentshield_sdk` and `@agentshield/sdk` | Request timeout; bearer token only in header; sanitized errors |
| Memory bridge | Explicit Claude/Codex import, local vectors, caller-supplied embeddings | Idempotent external IDs; candidate governance; no secret storage |
| Mission Control | Local HTTP dashboard and JSON telemetry | Loopback default; token required outside loopback; CSP/no-store |
| Federation | HTTPS peers, HMAC-SHA256 envelope, nonce/replay ledger | Environment-held secret, authenticated inbox, unknown peers denied |
| Marketplace | Versioned checksummed plugin/agent/workflow manifests | Verified flag is explicit; workspace-scoped; controlled publish path |
| Benchmarks | Memory latency and concurrent lease reliability workloads | Raw CI artifacts, environment metadata, no production extrapolation |

## Operational commands

The `agentshield` command remains as a deprecated alias of `ai-dlc`. Repositories initialized
before 3.2.0 keep working: `.agentshield/config.json` is still read when `.ai-dlc/config.json` is absent.

```bash
ai-dlc init . --project-id example
ai-dlc doctor . --network
ai-dlc mission-control --host 127.0.0.1 --port 8788
ai-dlc swarm create example "Ship feature" tasks.json --max-parallel 4
ai-dlc swarm pause SWARM_ID --reason "operator inspection"
ai-dlc swarm resume SWARM_ID
ai-dlc swarm cancel SWARM_ID --reason "unsafe dependency"
```

Federation receivers run through Mission Control. Set both
`AI_DLC_CONTROL_TOKEN` (the legacy `AGENTSHIELD_CONTROL_TOKEN` is still read) and a random 32+ character
`AGENTSHIELD_FEDERATION_SECRET` before binding beyond loopback. Peers must agree
out of band on the secret or replace HMAC with an externally reviewed asymmetric
key-management deployment profile.

## Release gates

1. Python, TypeScript SDK and plugin validation green on Linux, Windows and macOS.
2. Dependency and secret scans green.
3. Benchmark artifacts recorded with the runner class.
