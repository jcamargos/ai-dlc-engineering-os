"""ai-dlc-admin — human governance CLI for AI-DLC Engineering OS memory.

Approvals, human verification and purges require an interactive terminal and
typing the entity id. This is the human gate the MCP tools deliberately lack:
agents run non-interactive shells, so they cannot satisfy the confirmation.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DB_PATH, DATA_DIR, VERSION, WORKSPACE_ID, WORKSPACE_NAME
from .store import MemoryStore

Confirm = Callable[[str, str], bool]


def tty_confirm(prompt: str, expected: str) -> bool:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("Refused: this action requires an interactive terminal (human confirmation).", file=sys.stderr)
        return False
    answer = input(f"{prompt}\nType '{expected}' to confirm: ").strip()
    return answer == expected


def _print(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def run(argv: list[str] | None = None, confirm: Confirm = tty_confirm, store: MemoryStore | None = None) -> int:
    p = argparse.ArgumentParser(prog="ai-dlc-admin", description="Human governance for AI-DLC Engineering OS memory.")
    p.add_argument("--version", action="version", version=f"ai-dlc-admin {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stats"); s.add_argument("--project", default="")
    sub.add_parser("projects")
    s = sub.add_parser("candidates"); s.add_argument("--project", default=""); s.add_argument("--limit", type=int, default=50)

    rules = sub.add_parser("rules").add_subparsers(dest="action", required=True)
    for a in ("approve", "reject"):
        r = rules.add_parser(a); r.add_argument("id"); r.add_argument("--notes", default=""); r.add_argument("--reviewer", default="human")

    learn = sub.add_parser("learnings").add_subparsers(dest="action", required=True)
    v = learn.add_parser("verify"); v.add_argument("id"); v.add_argument("--evidence", default=""); v.add_argument("--reviewer", default="human")
    r = learn.add_parser("reject"); r.add_argument("id"); r.add_argument("--reviewer", default="human")

    rel = sub.add_parser("releases").add_subparsers(dest="action", required=True)
    for a in ("approve", "reject"):
        r = rel.add_parser(a); r.add_argument("id"); r.add_argument("--reviewer", required=True); r.add_argument("--notes", default="")

    s = sub.add_parser("purge"); s.add_argument("entity_type"); s.add_argument("id"); s.add_argument("--reason", required=True)
    s = sub.add_parser("merge-projects", help="move all entries of SOURCE into TARGET (fix fragmented ids)")
    s.add_argument("source"); s.add_argument("target")
    s = sub.add_parser("purge-project"); s.add_argument("project_id")
    s = sub.add_parser("export"); s.add_argument("--project", default=""); s.add_argument("--out", default="")
    s = sub.add_parser("backup"); s.add_argument("--out", default="")
    s = sub.add_parser("audit"); s.add_argument("--limit", type=int, default=50)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--project", default="")

    args = p.parse_args(argv)
    st = store or MemoryStore(DB_PATH, WORKSPACE_ID, WORKSPACE_NAME)

    try:
        if args.cmd == "stats":
            _print(st.stats(args.project or None))
        elif args.cmd == "projects":
            _print(st.list_projects())
        elif args.cmd == "candidates":
            _print(st.list_candidates(args.project or None, args.limit))
        elif args.cmd == "search":
            _print([h.__dict__ for h in st.search(args.query, args.project or None)])
        elif args.cmd == "rules":
            if args.action == "approve":
                rule = next((r for r in st.list_candidates(None, 200)["rules"] if r["id"] == args.id), None)
                if not rule:
                    print(f"Candidate rule not found: {args.id}", file=sys.stderr)
                    return 2
                summary = f"Approve rule for agent '{rule['agent_name']}':\n  {rule['rule_text']}\n  Rationale: {rule['rationale']}"
                if rule.get("flags_json", "[]") != "[]":
                    summary += f"\n  WARNING flags: {rule['flags_json']}"
                if not confirm(summary, args.id):
                    return 3
            _print(st.review_rule(args.id, args.action, args.reviewer, args.notes, allow_approval=(args.action == "approve")))
        elif args.cmd == "releases":
            if args.action == "approve" and not confirm(
                f"Approve agent release {args.id} as human reviewer '{args.reviewer}'. "
                "R3 releases need two distinct human reviewers; the release author cannot approve.", args.id):
                return 3
            _print(st.review_agent_release(args.id, args.action, args.reviewer, args.notes, allow_approval=(args.action == "approve")))
        elif args.cmd == "learnings":
            if args.action == "verify":
                if not confirm(f"Verify learning {args.id} as human reviewer '{args.reviewer}'.", args.id):
                    return 3
                _print(st.verify_learning(args.id, args.reviewer, args.evidence, via="human"))
            else:
                _print(st.reject_learning(args.id, args.reviewer))
        elif args.cmd == "purge":
            if not confirm(f"IRREVERSIBLY delete {args.entity_type} {args.id}.", f"PURGE {args.id}"):
                return 3
            _print(st.purge(args.entity_type, args.id, args.reason, via="human"))
        elif args.cmd == "merge-projects":
            if not confirm(f"Merge project '{args.source}' INTO '{args.target}' (source is deleted).", f"MERGE {args.source}"):
                return 3
            _print(st.merge_projects(args.source, args.target))
        elif args.cmd == "purge-project":
            if not confirm(f"IRREVERSIBLY delete project {args.project_id} and ALL its memory.", f"PURGE {args.project_id}"):
                return 3
            _print(st.purge_project(args.project_id, via="human"))
        elif args.cmd == "export":
            data = st.export(args.project or None)
            if args.out:
                Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                print(f"Exported to {args.out}")
            else:
                _print(data)
        elif args.cmd == "backup":
            out = Path(args.out) if args.out else DATA_DIR / "backups" / f"memory-{datetime.now():%Y%m%d-%H%M%S}.db"
            print(f"Backup written to {st.backup(out)}")
        elif args.cmd == "audit":
            _print(st.audit_tail(args.limit))
    except (KeyError, ValueError, PermissionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
