"""Keep the published benchmark commands runnable (reduced size)."""
import argparse
import importlib.util
from pathlib import Path

from ai_dlc_mcp import cli
from ai_dlc_mcp.store import MemoryStore

ROOT = Path(__file__).resolve().parents[1]


def test_memory_benchmark_runs(tmp_path, monkeypatch, capsys):
    store = MemoryStore(tmp_path / "bench.db", "bench", "Bench")
    monkeypatch.setattr(cli, "_store", lambda: store)
    output = tmp_path / "memory.json"
    assert cli.benchmark_command(argparse.Namespace(operations=20, searches=5, output=str(output))) == 0
    assert output.is_file()
    assert '"successful_searches": 5' in capsys.readouterr().out


def test_reliability_benchmark_is_exactly_once():
    spec = importlib.util.spec_from_file_location("run_reliability", ROOT / "benchmarks" / "run_reliability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.run(60, 4)
    assert report["passed"], report["results"]
    assert report["results"]["duplicate_completions"] == 0
    assert report["results"]["lost_tasks"] == 0


def test_cross_session_demo_recalls_decision_and_refuses_secret():
    import asyncio
    spec = importlib.util.spec_from_file_location("demo_cross_session", ROOT / "scripts" / "demo_cross_session.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lines = dict((value, kind) for kind, value in asyncio.run(module.record()))
    assert lines["stored as accepted decision"] == "ok"
    assert lines["refused: looks like a credential"] == "deny"
    assert lines["recalled: Idempotency-Key required on payment writes"] == "ok"
    assert lines["no credential in context"] == "ok"
