# Public benchmark protocol

AI-DLC Engineering OS publishes reproducible workloads, raw JSON artifacts, runner
versions and explicit limitations. A result is evidence for the measured
environment only; it is not a claim about production capacity.

## Workloads

- `ai-dlc benchmark` measures local governed-memory writes and vector
  retrieval latency with a fixed data shape.
- `run_reliability.py` starts a dependency-free swarm, runs concurrent workers,
  and fails if any task is lost or completed more than once.
- PostgreSQL migration replay and pgTAP exercise tenant isolation, atomic leases,
  state transitions, cycle rejection and authorization boundaries in CI.

Run locally:

```bash
python -m pip install -e .
ai-dlc benchmark --operations 1000 --searches 200 --output benchmarks/results/memory.json
python benchmarks/run_reliability.py --tasks 500 --workers 8 --output benchmarks/results/reliability.json
```

`tests/test_benchmarks.py` runs both workloads at reduced size in CI so the commands
stay working. Compare results only when the OS, Python version,
runner class, workload and commit are identical. Network/remote benchmarks must
run against an isolated load-test environment, never the production tenant.
