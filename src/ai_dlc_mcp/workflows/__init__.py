"""Native, versioned procedures shared by CLI and MCP; no remote loaders."""
from importlib.resources import files
import json


PHASES = {
    "discover": "Resolve requirements, constraints and design uncertainty before implementation.",
    "plan": "Break an agreed outcome into independently verifiable tasks and handoffs.",
    "implement": "Execute a bounded task with a meaningful regression test cycle.",
    "debug": "Investigate a failure with reproducible evidence and isolated hypotheses.",
    "review": "Check requirement coverage and technical quality before accepting work.",
    "finish": "Verify the complete change, deliver within authorization and preserve recovery context.",
}


def catalog() -> list[dict[str, str]]:
    return [{"name": name, "description": description} for name, description in PHASES.items()]


def load(name: str) -> str:
    if name not in PHASES:
        raise ValueError(f"Unknown workflow '{name}'. Available: {', '.join(PHASES)}")
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")


def cli_command(args) -> int:
    print(json.dumps(catalog(), indent=2) if args.workflow_action == "list" else load(args.phase))
    return 0


def add_parser(commands) -> None:
    parser = commands.add_parser("workflow", help="load a native engineering procedure")
    actions = parser.add_subparsers(dest="workflow_action", required=True)
    actions.add_parser("list").set_defaults(func=cli_command)
    show = actions.add_parser("show")
    show.add_argument("phase", choices=tuple(PHASES))
    show.set_defaults(func=cli_command)
