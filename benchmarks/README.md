# Public benchmark protocol

AgentShield publishes reproducible workloads, raw JSON artifacts, runner
versions and explicit limitations. A result is evidence for the measured
environment only; it is not a claim about production capacity.

## Workloads

- `agentshield benchmark` measures local governed-memory writes and vector
  retrieval latency with a fixed data shape.
- `run_reliability.py` starts a dependency-free swarm, runs concurrent workers,
  and fails if any task is lost or completed more than once.
- PostgreSQL migration replay and pgTAP exercise tenant isolation, atomic leases,
  state transitions, cycle rejection and authorization boundaries in CI.

Run locally:

```bash
python -m pip install -e .
agentshield benchmark --operations 1000 --searches 200 --output benchmarks/results/memory.json
python benchmarks/run_reliability.py --tasks 1000 --workers 8 --output benchmarks/results/reliability.json
```

The `Public benchmarks` GitHub Actions workflow also uploads both JSON files as
immutable run artifacts. Compare results only when the OS, Python version,
runner class, workload and commit are identical. Network/remote benchmarks must
run against an isolated load-test environment, never the production tenant.
