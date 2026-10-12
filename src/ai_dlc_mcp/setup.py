"""Interactive bootstrap: persistent uv tool environment, never the uvx cache."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

from . import __version__
from .config import default_data_dir
from .installer import Installer, Plan, vscode_user_dirs

EDITORS = ("codex", "claude", "vscode")


def package_source() -> str:
    """Preserve the source resolved by uvx, including a Git commit or local wheel."""
    raw = distribution("ai-dlc-engineering-os").read_text("direct_url.json")
    if raw:
        direct = json.loads(raw)
        vcs = direct.get("vcs_info", {})
        if vcs.get("vcs") == "git":
            return f"git+{direct['url']}@{vcs['commit_id']}"
        if "archive_info" in direct or "dir_info" in direct:
            return direct["url"]
    return f"ai-dlc-engineering-os=={__version__}"


def select_editors(value: str) -> list[str]:
    names = list(dict.fromkeys(x.strip().lower() for x in value.split(",") if x.strip()))
    if not names or any(name not in EDITORS for name in names):
        raise ValueError("Choose codex, claude, vscode, or a comma-separated combination.")
    return names


def register(home: Path, python: Path, editors: list[str], dry_run: bool) -> None:
    # File edits provide backups and exactly the same preview/apply paths; no host CLI side effects.
    inst = Installer(home, str(python), Plan(dry_run=dry_run), use_cli=False)
    for editor in editors:
        if editor == "claude":
            inst.install_claude(allow_read_tools=False)
        else:
            getattr(inst, f"install_{editor}")()


def backup_memory(home: Path) -> None:
    data = default_data_dir(home)
    db = Path(os.getenv("AI_DLC_DB_PATH", str(data / "memory.db"))).expanduser().resolve()
    if not db.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = db.parent / "backups" / f"pre-setup-{stamp}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    print(f"Memory backup: {target}")


def run(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser().resolve()
    if args.editors:
        editors = select_editors(args.editors)
    elif sys.stdin.isatty():
        print("Editors: codex, claude, vscode (comma-separated for multiple editors)")
        editors = select_editors(input("Configure which editors? "))
    else:
        raise ValueError("Non-interactive setup requires --editors and --yes (or --dry-run).")
    if "vscode" in editors and not vscode_user_dirs(home):
        raise ValueError("Open VS Code once to create its default profile, then run setup again.")
    if not args.yes and not args.dry_run and not sys.stdin.isatty():
        raise ValueError("Non-interactive setup requires --yes; use --dry-run to preview.")
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("Install uv first: https://docs.astral.sh/uv/getting-started/installation/")
    tool_root = Path(subprocess.check_output([uv, "tool", "dir"], text=True).strip())
    python = tool_root / "ai-dlc-engineering-os" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    source = args.source or package_source()
    if source.startswith("-"):
        raise ValueError("Package source cannot begin with '-'.")
    print(f"Install {source} in a persistent uv tool environment: {python.parent.parent}")
    print(f"Editors: {', '.join(editors)}. Existing configuration files and memory are backed up.")
    print("Read-only tool permissions are not pre-approved. Editor confirmation remains enabled.")
    register(home, python, editors, dry_run=True)
    if args.dry_run:
        print("Preview complete. No installation or configuration changes made.")
        return 0
    if not args.yes and input("Apply these changes? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Cancelled. No changes made.")
        return 0
    # Install first; a download/build failure must not touch editor configuration or memory.
    subprocess.run([uv, "tool", "install", "--python", sys._base_executable, source], check=True, timeout=600)
    version = subprocess.check_output(
        [str(python), "-c", "from ai_dlc_mcp import __version__; print(__version__)"], text=True, timeout=30,
    ).strip()
    if version != __version__:
        raise ValueError(f"Installed version {version} differs from setup version {__version__}; configuration unchanged.")
    backup_memory(home)
    register(home, python, editors, dry_run=False)
    env = dict(os.environ)
    env.setdefault("AI_DLC_DATA_DIR", str(default_data_dir(home)))
    for editor in editors:
        subprocess.run(
            [str(python), "-m", "ai_dlc_mcp.installer", "doctor", "--only", editor, "--home", str(home)],
            env=env, check=True, timeout=120,
        )
    print(f"Setup complete. Restart {', '.join(editors)} and ask for your project's engineering context.")
    print(f"Persistent runtime: {python}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-dlc-engineering-os")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="preview and install persistent MCP registrations")
    setup.add_argument("--editors", help="codex, claude, vscode, or comma-separated names")
    setup.add_argument("--yes", action="store_true", help="apply the displayed plan without prompting")
    setup.add_argument("--dry-run", action="store_true", help="show changes without installing or writing files")
    setup.add_argument("--source", help="install this package source instead of the matching PyPI release")
    setup.add_argument("--home", default=str(Path.home()), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"Setup failed: {exc}\nExisting backups are preserved. Correct the error and rerun setup.", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
