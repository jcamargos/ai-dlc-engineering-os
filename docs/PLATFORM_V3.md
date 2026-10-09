# Platform v3 (local edition)

## Capability map

| Capability | Implementation | Safety boundary |
|---|---|---|
| Native plugin | Portable `plugin.json`, Codex and Claude compatibility manifests, MCP, skill and hooks | Hooks have 5–10 second bounds and fail open |
| Init and doctor | `agentshield init`, `agentshield doctor` | Writes repository-local config; network diagnostic is opt-in |
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

```bash
agentshield init . --project-id example
agentshield doctor . --network
agentshield mission-control --host 127.0.0.1 --port 8788
agentshield swarm create example "Ship feature" tasks.json --max-parallel 4
agentshield swarm pause SWARM_ID --reason "operator inspection"
agentshield swarm resume SWARM_ID
agentshield swarm cancel SWARM_ID --reason "unsafe dependency"
```

Federation receivers run through Mission Control. Set both
`AGENTSHIELD_CONTROL_TOKEN` and a random 32+ character
`AGENTSHIELD_FEDERATION_SECRET` before binding beyond loopback. Peers must agree
out of band on the secret or replace HMAC with an externally reviewed asymmetric
key-management deployment profile.

## Release gates

1. Python, TypeScript SDK and plugin validation green on Linux, Windows and macOS.
2. Dependency and secret scans green.
3. Benchmark artifacts recorded with the runner class.
