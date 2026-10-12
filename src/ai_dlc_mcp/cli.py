from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any

from .config import DB_PATH, WORKSPACE_ID, WORKSPACE_NAME
from .control_plane import serve_control_plane
from .installer import SERVER_NAME
from .store import MemoryStore


def _store() -> MemoryStore:
    return MemoryStore(DB_PATH, WORKSPACE_ID, WORKSPACE_NAME)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_command(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    project_id = args.project_id or _store().resolve_project_id(str(root))["project_id"]
    endpoint = args.endpoint or os.environ.get("AI_DLC_REMOTE_URL", "").strip() or None  # local-only unless explicitly configured
    max_parallel = args.max_parallel
    if sys.stdin.isatty() and not args.yes:
        print("AgentShield initialization wizard (Enter accepts the default)")
        project_id = input(f"Project id [{project_id}]: ").strip() or project_id
        endpoint = input(f"Remote MCP endpoint, optional (blank = local only) [{endpoint or ''}]: ").strip() or endpoint
        parallel_text = input(f"Maximum parallel swarm tasks [{max_parallel}]: ").strip()
        if parallel_text:
            max_parallel = max(1, min(int(parallel_text), 64))
    config_path = root / ".agentshield" / "config.json"
    if config_path.exists() and not args.force:
        print(f"Already initialized: {config_path}")
        return 0
    config = {"schema_version": 1, "project_id": project_id, "endpoint": endpoint, "memory": {"bridge": ["codex", "claude"], "vector_search": True}, "hooks": {"routing": True, "memory": True, "evaluation": True}, "swarm": {"max_parallel": max_parallel}}
    _write_json(config_path, config)
    if getattr(args, "project_mcp", False):
        # Optional project-scoped registration. The global install (ai-dlc-install) is the default; this shares the
        # same workspace and database so global memory stays visible (no per-repository workspace split).
        mcp_path = root / ".mcp.json"
        mcp_config: dict[str, Any] = {}
        if mcp_path.exists():
            try:
                mcp_config = json.loads(mcp_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"existing {mcp_path} is not valid JSON") from exc
        servers = mcp_config.setdefault("mcpServers", {})
        servers.setdefault(SERVER_NAME, {"command": sys.executable, "args": ["-m", "ai_dlc_mcp.server"]})
        _write_json(mcp_path, mcp_config)
    store = _store()
    store.ensure_project(project_id, root.name, str(root), "Initialized by AgentShield CLI")
    print(f"Initialized AgentShield in {root}")
    print("Next: agentshield doctor")
    return 0


def doctor_command(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("python", sys.version_info >= (3, 10), platform.python_version()))
    checks.append(("git", shutil.which("git") is not None, shutil.which("git") or "not found"))
    checks.append(("config", (root / ".agentshield" / "config.json").is_file(), str(root / ".agentshield" / "config.json")))
    checks.append(("mcp", (root / ".mcp.json").is_file(), str(root / ".mcp.json")))
    try:
        store = _store()
        with store._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        checks.append(("database", True, str(DB_PATH)))
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary
        checks.append(("database", False, type(exc).__name__))
    if args.network:
        try:
            socket.getaddrinfo("agentshield.com.br", 443)
            checks.append(("dns", True, "agentshield.com.br"))
        except OSError as exc:
            checks.append(("dns", False, str(exc)))
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    failed = sum(not passed for _, passed, _ in checks)
    print(f"Doctor: {len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


def swarm_command(args: argparse.Namespace) -> int:
    store = _store()
    if args.swarm_action == "create":
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
        result = store.create_swarm(args.project_id, args.objective, tasks, args.max_parallel)
    elif args.swarm_action == "show":
        result = store.get_swarm(args.swarm_id)
    else:
        result = store.set_swarm_state(args.swarm_id, args.swarm_action, args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def benchmark_command(args: argparse.Namespace) -> int:
    store = _store()
    project = "benchmark-local"
    store.ensure_project(project, "Local benchmark")
    started = time.perf_counter()
    for index in range(args.operations):
        memory = store.save_memory(project, "benchmark", f"case-{index}", f"reliable distributed agent memory sample {index}", ["benchmark"])
        store.index_memory(memory["id"])
    write_seconds = time.perf_counter() - started
    started = time.perf_counter()
    searches = [store.semantic_search("reliable agent memory", project, 5) for _ in range(args.searches)]
    search_seconds = time.perf_counter() - started
    report = {"schema_version": 1, "environment": {"python": platform.python_version(), "platform": platform.platform()}, "workload": {"writes": args.operations, "searches": args.searches}, "results": {"writes_per_second": round(args.operations / max(write_seconds, 1e-9), 2), "search_mean_ms": round(search_seconds * 1000 / max(args.searches, 1), 3), "successful_searches": sum(bool(value) for value in searches)}, "disclaimer": "Local single-process benchmark; not a production scale claim."}
    if args.output:
        _write_json(Path(args.output), report)
    print(json.dumps(report, indent=2))
    return 0


def hook_command(args: argparse.Namespace) -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        event = {}
    try:
        cwd = Path(str(event.get("cwd") or Path.cwd())).resolve()
        config_path = next((parent / ".agentshield" / "config.json" for parent in (cwd, *cwd.parents) if (parent / ".agentshield" / "config.json").is_file()), None)
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path else {}
        store = _store()
        project_id = str(config.get("project_id") or store.resolve_project_id(str(cwd))["project_id"])
        known_project = store.get_project(project_id) is not None
        session_hash = hashlib.sha256(str(event.get("session_id") or "anonymous").encode()).hexdigest()[:16]
        if args.event == "session-start":
            if not known_project and not config_path:
                print(json.dumps({"continue": True}))
                return 0
            context = store.project_context(project_id, max_chars=4000)
            response = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
        elif args.event == "route":
            prompt = str(event.get("prompt") or event.get("user_prompt") or "")[:20000]
            normalized = prompt.lower()
            routes = [
                ("security", ("security", "auth", "secret", "threat", "vulnerability")),
                ("data-database", ("database", "sql", "schema", "migration", "rls")),
                ("platform-sre", ("deploy", "production", "slo", "incident", "cloud")),
                ("qa-verification", ("test", "verify", "regression", "quality")),
                ("frontend", ("ui", "frontend", "browser", "accessibility")),
                ("backend", ("api", "backend", "service", "worker")),
            ]
            words = set(re.findall(r"[a-z0-9]+", normalized))
            selected = [agent for agent, keywords in routes if words.intersection(keywords)] or ["orchestrator"]
            with store._connect() as conn:
                store._audit(conn, "hook.route", "session", session_hash, {"project_id": project_id, "agents": selected, "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(), "prompt_chars": len(prompt)})
            response = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "AgentShield route: " + ", ".join(selected) + ". Retrieve project context before material work and attach verification evidence."}}
        elif args.event == "memory":
            tool_name = str(event.get("tool_name") or "unknown")[:200]
            with store._connect() as conn:
                store._audit(conn, "hook.tool_completed", "session", session_hash, {"project_id": project_id, "tool_name": tool_name, "explicit_memory_tool": tool_name in {"save_memory", "record_learning", "save_decision", "record_task_outcome"}})
            response = {"continue": True}
        else:
            gates = {
                "tests": event.get("tests_passed") is True,
                "security": event.get("security_reviewed") is True,
                "evidence": event.get("evidence_attached") is True,
            }
            gate_status = "passed" if all(gates.values()) else "evidence_required"
            with store._connect() as conn:
                store._audit(conn, "hook.evaluate", "session", session_hash, {"project_id": project_id, "event": "stop", "gates": gates, "status": gate_status})
            response = {"continue": True, "systemMessage": f"AgentShield evaluation: {gate_status}. Report test, security, and evidence status before claiming completion."}
        print(json.dumps(response, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - hooks must fail open
        print(json.dumps({"continue": True, "systemMessage": "AgentShield hook degraded safely; continue without hook automation."}))
    return 0


def mission_control_command(args: argparse.Namespace) -> int:
    dashboard = Path(__file__).resolve().parent / "assets" / "mission-control.html"
    if not dashboard.exists():
        source_dashboard = Path(__file__).resolve().parents[2] / "apps" / "mission-control" / "index.html"
        dashboard = Path(args.dashboard).resolve() if args.dashboard else source_dashboard
    if not dashboard.exists():
        raise FileNotFoundError("Mission Control dashboard asset is missing")
    serve_control_plane(_store(), args.host, args.port, dashboard, os.getenv("AGENTSHIELD_CONTROL_TOKEN"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentshield", description="AI-DLC Engineering OS (by AgentShield) control plane")
    parser.add_argument("--version", action="version", version="AI-DLC Engineering OS 3.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="initialize a repository")
    init.add_argument("directory", nargs="?", default="."); init.add_argument("--project-id"); init.add_argument("--endpoint"); init.add_argument("--max-parallel", type=int, default=4); init.add_argument("--force", action="store_true"); init.add_argument("--project-mcp", action="store_true", help="also register the server in this repository's .mcp.json"); init.add_argument("--yes", action="store_true", help="accept defaults without the interactive wizard"); init.set_defaults(func=init_command)
    doctor = commands.add_parser("doctor", help="validate local installation")
    doctor.add_argument("directory", nargs="?", default="."); doctor.add_argument("--network", action="store_true"); doctor.set_defaults(func=doctor_command)
    swarm = commands.add_parser("swarm", help="control persistent swarms"); swarm_sub = swarm.add_subparsers(dest="swarm_action", required=True)
    create = swarm_sub.add_parser("create"); create.add_argument("project_id"); create.add_argument("objective"); create.add_argument("tasks"); create.add_argument("--max-parallel", type=int, default=4)
    show = swarm_sub.add_parser("show"); show.add_argument("swarm_id")
    for action in ("pause", "resume", "cancel"):
        sub = swarm_sub.add_parser(action); sub.add_argument("swarm_id"); sub.add_argument("--reason", default="operator request")
    swarm.set_defaults(func=swarm_command)
    benchmark = commands.add_parser("benchmark", help="run a reproducible local benchmark"); benchmark.add_argument("--operations", type=int, default=250); benchmark.add_argument("--searches", type=int, default=50); benchmark.add_argument("--output"); benchmark.set_defaults(func=benchmark_command)
    hook = commands.add_parser("hook", help=argparse.SUPPRESS); hook.add_argument("event"); hook.set_defaults(func=hook_command)
    mission = commands.add_parser("mission-control", help="run the visual control plane"); mission.add_argument("--host", default="127.0.0.1"); mission.add_argument("--port", type=int, default=8788); mission.add_argument("--dashboard"); mission.set_defaults(func=mission_control_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
