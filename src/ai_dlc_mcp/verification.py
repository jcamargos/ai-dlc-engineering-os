"""Local, opt-in verification receipts. No shell, network, or model calls of our own."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from .security import assert_no_secrets


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Git inspection failed; check repository and origin configuration")
    return result.stdout


def repository_identity(remote: str) -> str:
    """Compare HTTPS/SSH remotes without persisting credentials or local paths."""
    remote = remote.strip()
    if re.fullmatch(r"[^/@:]+@[^/:]+:.+", remote):
        host, path = remote.split("@", 1)[1].split(":", 1)
    else:
        parsed = urlsplit(remote)
        if parsed.scheme not in {"https", "ssh"} or not parsed.hostname or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Expected an HTTPS or SSH repository remote without credentials/query")
        if parsed.scheme == "https" and parsed.username:
            raise ValueError("Credential-bearing HTTPS remotes are not supported")
        host, path = parsed.hostname, parsed.path
        if parsed.port:
            host += f":{parsed.port}"
    path = path.strip("/").removesuffix(".git")
    if not path or any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("Invalid repository remote path")
    return host.lower() + "/" + path


def snapshot(directory: str | Path, expected_remote: str) -> dict:
    root = Path(_git(Path(directory), "rev-parse", "--show-toplevel").decode().strip()).resolve()
    identity = repository_identity(_git(root, "remote", "get-url", "origin").decode())
    if identity != repository_identity(expected_remote):
        raise ValueError("Repository identity mismatch; no verification command was executed")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    entries = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    names = sorted(set(name for name in entries if name))
    if len(names) > 20000:
        raise ValueError("Verification snapshot exceeds 20000 files")
    digest, total = hashlib.sha256(), 0
    for name in names:
        path = root / os.fsdecode(name)
        if root not in path.resolve().parents or path.is_symlink():
            raise ValueError("Verification snapshot refuses external paths and symlinks")
        digest.update(name + b"\0")
        if not path.exists():
            digest.update(b"deleted\0")
            continue
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Verification snapshot requires regular files (submodules are unsupported)")
        total += info.st_size
        if info.st_size > 32 * 1024 * 1024 or total > 128 * 1024 * 1024:
            raise ValueError("Verification snapshot exceeds file/total byte budget")
        digest.update(str(stat.S_IMODE(info.st_mode)).encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {"root": str(root), "repository": identity, "commit": head,
            "tree_sha256": digest.hexdigest(), "file_count": len(names)}


def run_check(directory: str, expected_remote: str, command: list[str], timeout: int = 600) -> dict:
    if not command or not all(isinstance(value, str) and value for value in command):
        raise ValueError("An explicit command argument list is required")
    if not 1 <= timeout <= 3600:
        raise ValueError("timeout must be between 1 and 3600 seconds")
    assert_no_secrets({"command": json.dumps(command)})
    before = snapshot(directory, expected_remote)
    started = time.time()
    # Output is hashed, never embedded in a receipt or memory. Commands are trusted
    # local programs chosen by the operator, not sandboxed by this helper.
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(command, cwd=before["root"], stdout=output, stderr=subprocess.STDOUT,
                                    timeout=timeout, shell=False)
            code, timed_out = result.returncode, False
        except subprocess.TimeoutExpired:
            code, timed_out = None, True
        output.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: output.read(65536), b""):
            digest.update(chunk)
    after = snapshot(directory, expected_remote)
    return {"schema_version": 1, "kind": "local-command-evidence", "before": before, "after": after,
            "command": command, "started_at": started, "finished_at": time.time(),
            "exit_code": code, "timed_out": timed_out, "output_sha256": digest.hexdigest(),
            "passed": code == 0 and not timed_out and before == after}


def validate_evidence(receipt: dict, directory: str, expected_remote: str, max_age: int = 86400) -> dict:
    if not 1 <= max_age <= 604800:
        raise ValueError("max_age must be between 1 and 604800 seconds")
    current = snapshot(directory, expected_remote)
    try:
        age = time.time() - receipt["finished_at"]
        gates = {
            "schema": receipt["schema_version"] == 1 and receipt["kind"] == "local-command-evidence",
            "command": bool(receipt["command"]) and all(isinstance(x, str) and x for x in receipt["command"]),
            "successful": type(receipt["exit_code"]) is int and receipt["exit_code"] == 0 and receipt["timed_out"] is False,
            "unchanged": receipt["before"] == receipt["after"] == current,
            "fresh": 0 <= age <= max_age and receipt["started_at"] <= receipt["finished_at"],
            "output_digest": bool(re.fullmatch(r"[0-9a-f]{64}", receipt["output_sha256"])),
        }
    except (KeyError, TypeError, ValueError):
        raise ValueError("Malformed verification receipt") from None
    return {"passed": all(gates.values()), "gates": gates,
            "limitation": "Local evidence is not signed; command success does not prove requirement coverage."}


def cli_command(args) -> int:
    if args.verify_action == "preflight":
        result = snapshot(args.directory, args.expected_remote)
    elif args.verify_action == "run":
        destination = Path(args.output).resolve()
        root = Path(_git(Path(args.directory), "rev-parse", "--show-toplevel").decode().strip()).resolve()
        if destination == root or root in destination.parents:
            raise ValueError("Store receipts outside the repository to avoid invalidating the snapshot")
        if destination.exists():
            raise ValueError("Receipt already exists; choose a new filename before running the check")
        command = args.check_command
        if command[:1] == ["--"]:
            command = command[1:]
        result = run_check(args.directory, args.expected_remote, command, args.timeout)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids overwriting an earlier run's evidence.
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
    else:
        result = validate_evidence(json.loads(Path(args.receipt).read_text(encoding="utf-8")),
                                   args.directory, args.expected_remote, args.max_age)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


def add_parser(commands) -> None:
    parser = commands.add_parser("verify", help="repository preflight and fresh command evidence")
    actions = parser.add_subparsers(dest="verify_action", required=True)
    for name in ("preflight", "run", "check"):
        action = actions.add_parser(name)
        action.add_argument("--directory", default=".")
        action.add_argument("--expected-remote", required=True)
        if name == "run":
            action.add_argument("--output", required=True)
            action.add_argument("--timeout", type=int, default=600)
            action.add_argument("check_command", nargs="...")
        elif name == "check":
            action.add_argument("receipt")
            action.add_argument("--max-age", type=int, default=86400)
        action.set_defaults(func=cli_command)
