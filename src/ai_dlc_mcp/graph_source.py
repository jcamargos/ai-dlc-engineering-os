"""Bounded, local-only repository inventory. Never execute repository code."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile

VERSION = "imports-v1"
MAX_FILES = 5000
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
EXCLUDED = {"node_modules", "vendor", "dist", "build", "coverage", "output",
            "__pycache__", "venv", "env", "site-packages"}


class GraphError(ValueError):
    """A safe, actionable graph failure; never include source content."""


def git(root: Path, *args: str, optional: bool = False) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    # Spooling avoids an unbounded in-memory stdout/stderr allocation.
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(
                ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                 "-C", str(root), *args], env=env, stdout=output,
                stderr=subprocess.DEVNULL, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GraphError("Git unavailable or timed out; check the local repository.") from exc
        if result.returncode:
            if optional:
                return ""
            raise GraphError("Git inventory failed; check repository access and Git trust settings.")
        if output.tell() > 4 * 1024 * 1024:
            raise GraphError("Git inventory exceeds the 4 MiB output limit.")
        output.seek(0)
        try:
            return output.read().decode("utf-8")
        except UnicodeError as exc:
            raise GraphError("Repository paths must be valid UTF-8.") from exc


def checked_root(repo_path: str) -> Path:
    if not repo_path or not Path(repo_path).is_absolute():
        raise GraphError("Register an absolute repo_path with bootstrap_project first.")
    root = Path(repo_path).resolve()
    allowed = [Path(p).expanduser().resolve() for p in
               os.environ.get("AI_DLC_GRAPH_ROOTS", "").split(os.pathsep) if p.strip()]
    if not any(root == parent or root.is_relative_to(parent) for parent in allowed):
        raise GraphError("Repository is not allowed by AI_DLC_GRAPH_ROOTS on this MCP host.")
    if not root.is_dir():
        raise GraphError("Registered repository is unavailable.")
    top = git(root, "rev-parse", "--show-toplevel").strip()
    if Path(top).resolve() != root:
        raise GraphError("repo_path must be the Git repository root, not a subdirectory.")
    return root


def safe_file(root: Path, relative: str) -> Path:
    if root.is_symlink() or root.resolve() != root:
        raise GraphError("Repository root changed.")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise GraphError("Unsafe repository path.")
    candidate = root
    for part in path.parts:
        candidate = candidate / part
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise GraphError("Links and Windows reparse points are excluded.")
    if not candidate.resolve().is_relative_to(root):
        raise GraphError("Repository path escapes its root.")
    if not candidate.is_file():
        raise GraphError("Only regular source files can be indexed.")
    return candidate


def scan(root: Path) -> dict:
    before = git(root, "rev-parse", "--verify", "HEAD", optional=True).strip() or None
    inventory = sorted(set(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")) - {""})
    candidates = []
    excluded = 0
    for name in inventory:
        path = PurePosixPath(name)
        if (len(name.encode("utf-8")) > 512 or path.suffix.lower() not in EXTENSIONS or any(
                part.startswith(".") or part.lower() in EXCLUDED for part in path.parts)
                or path.name.endswith((".min.js", ".d.ts"))):
            excluded += 1
        else:
            candidates.append(name)
    if len(candidates) > MAX_FILES:
        raise GraphError("Graph exceeds 5000 source files; narrow the repository or exclusions.")
    files, hashes, skipped = {}, {}, []
    total = 0
    for name in candidates:
        try:
            path = safe_file(root, name)
            with path.open("rb") as source:
                initial = os.fstat(source.fileno())
                actual = safe_file(root, name).stat()
                if (actual.st_dev, actual.st_ino) != (initial.st_dev, initial.st_ino):
                    raise GraphError("File changed while opening; retry.")
                if not stat.S_ISREG(initial.st_mode):
                    raise GraphError("Non-regular file.")
                data = source.read(MAX_FILE_BYTES + 1)
                final = os.fstat(source.fileno())
            if (initial.st_mtime_ns, initial.st_size) != (final.st_mtime_ns, final.st_size):
                raise GraphError("File changed while scanning; retry.")
            if len(data) > MAX_FILE_BYTES:
                skipped.append({"path": name, "reason": "file_size_limit"})
                continue
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise GraphError("Graph exceeds the 32 MiB source budget.")
            hashes[name] = hashlib.sha256(data).hexdigest()
            try:
                files[name] = data.decode("utf-8-sig")
            except UnicodeError:
                skipped.append({"path": name, "reason": "unsupported_encoding"})
        except (OSError, GraphError) as exc:
            if isinstance(exc, GraphError) and ("budget" in str(exc) or "changed" in str(exc)):
                raise
            skipped.append({"path": name, "reason": "unavailable_or_unsafe"})
    after = git(root, "rev-parse", "--verify", "HEAD", optional=True).strip() or None
    if before != after:
        raise GraphError("HEAD changed while scanning; retry.")
    manifest = {"version": VERSION, "commit": after, "hashes": hashes, "skipped": skipped,
                "inventory": candidates}
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return {"files": files, "fingerprint": fingerprint, "commit": after,
            "skipped": skipped, "excluded_files": excluded, "source_bytes": total}
