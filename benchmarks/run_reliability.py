from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import tempfile
import time

from ai_dlc_mcp.store import MemoryStore


def run(task_count: int, workers: int) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        store = MemoryStore(Path(directory) / "benchmark.db", "benchmark", "Benchmark")
        store.ensure_project("scale", "Scale benchmark")
        tasks = [{"id": f"task-{index:05d}", "agent": "performance", "title": f"Task {index}"} for index in range(task_count)]
        swarm = store.create_swarm("scale", "Exactly-once lease benchmark", tasks, workers)
        completed: list[str] = []

        def worker(worker_index: int) -> None:
            worker_id = f"worker-{worker_index}"
            while True:
                task = store.claim_swarm_task(swarm["id"], worker_id, 60)
                if task is None:
                    state = store.get_swarm(swarm["id"])["status"]
                    if state in {"completed", "failed", "cancelled"}:
                        return
                    time.sleep(0.002)
                    continue
                store.complete_swarm_task(task["id"], worker_id, {"worker": worker_id})
                completed.append(task["id"])

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(worker, range(workers)))
        elapsed = time.perf_counter() - started
        final = store.get_swarm(swarm["id"])
        unique = len(set(completed))
        return {
            "schema_version": 1,
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "workload": {"tasks": task_count, "workers": workers, "storage": "SQLite/WAL"},
            "results": {
                "status": final["status"],
                "elapsed_seconds": round(elapsed, 4),
                "tasks_per_second": round(task_count / max(elapsed, 1e-9), 2),
                "completed": len(completed),
                "unique_completed": unique,
                "duplicate_completions": len(completed) - unique,
                "lost_tasks": task_count - unique,
            },
            "passed": final["status"] == "completed" and unique == task_count and len(completed) == unique,
            "disclaimer": "Single-machine reference workload. Publish environment and raw artifact; do not extrapolate to production capacity.",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run(max(1, args.tasks), max(1, min(args.workers, 64)))
    text = json.dumps(report, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
