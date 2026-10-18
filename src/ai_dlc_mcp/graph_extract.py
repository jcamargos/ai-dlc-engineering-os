"""File-level imports: Python AST and explicitly heuristic JS/TS lexical edges."""
from __future__ import annotations

import ast
from collections import defaultdict
import posixpath
import re

from .graph_source import GraphError, VERSION

MAX_EDGES = 20000
JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
# Consume strings/templates/comments as single tokens so embedded import text is
# not mistaken for code. This is deliberately not a TypeScript type resolver.
TOKEN = re.compile(
    r"(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
    r"|(?P<template>`(?:\\.|[^`\\])*`)"
    r"|(?P<word>[A-Za-z_$][\w$]*)|(?P<punct>[^\s])"
)


def js_imports(text: str):
    tokens = []
    line, previous = 1, 0
    for match in TOKEN.finditer(text):
        line += text.count("\n", previous, match.start())
        if match.lastgroup != "comment":
            tokens.append((match.lastgroup, match.group(), line))
        previous = match.start()
    for i, (kind, value, line) in enumerate(tokens):
        if kind != "word" or value not in {"import", "export", "require"}:
            continue
        if i and tokens[i - 1][1] in {".", "?."}:
            continue
        tail = tokens[i + 1:i + 100]
        literal = None
        if value == "import" and tail and tail[0][0] == "string":
            literal = tail[0][1]
        elif value in {"import", "require"} and len(tail) >= 3 and (
                tail[0][1] == "(" and tail[1][0] == "string" and tail[2][1] in {")", ","}):
            literal = tail[1][1]
        elif value in {"import", "export"}:
            for j, token in enumerate(tail[:-1]):
                if token[1] == ";" or token[1] in {"import", "export"}:
                    break
                if token[1] == "from" and tail[j + 1][0] == "string":
                    literal = tail[j + 1][1]
                    break
        if literal and "\\" not in literal:
            yield literal[1:-1], line


def _python_modules(files: dict) -> dict:
    modules = defaultdict(set)
    for name in files:
        if not name.endswith(".py"):
            continue
        value = name[:-3]
        if value.endswith("/__init__"):
            value = value[:-9]
        for variant in {value, value.removeprefix("src/")}:
            modules[variant.replace("/", ".")].add(name)
    return modules


def extract(snapshot: dict) -> dict:
    files = snapshot["files"]
    modules = _python_modules(files)
    edges, unresolved, issues = set(), 0, list(snapshot["skipped"])
    for source, text in files.items():
        if source.endswith(".py"):
            try:
                tree = ast.parse(text, filename=source)
            except (SyntaxError, ValueError, RecursionError):
                issues.append({"path": source, "reason": "python_parse_error"})
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    base = node.module or ""
                    if node.level:
                        package = source.rsplit("/", 1)[0].split("/") if "/" in source else []
                        if node.level > len(package):
                            unresolved += 1
                            continue
                        base = ".".join(package[:len(package) - node.level + 1] + ([base] if base else []))
                    names = [base] + [f"{base}.{alias.name}" if base else alias.name for alias in node.names]
                found = False
                for name in names:
                    targets = modules.get(name, set())
                    if len(targets) == 1:
                        target = next(iter(targets))
                        if target != source:
                            edges.add((source, target, node.lineno, "python_ast"))
                            found = True
                if not found:
                    unresolved += 1
        else:
            for specifier, line in js_imports(text):
                if not specifier.startswith("."):
                    unresolved += 1
                    continue
                base = posixpath.normpath(posixpath.join(posixpath.dirname(source), specifier))
                candidates = [base] if base in files else []
                if not candidates:
                    candidates = [base + ext for ext in JS_EXT if base + ext in files]
                    candidates += [base + "/index" + ext for ext in JS_EXT if base + "/index" + ext in files]
                if not candidates and base.endswith((".js", ".mjs", ".cjs")):
                    stem = base.rsplit(".", 1)[0]
                    candidates = [stem + ext for ext in (".ts", ".tsx", ".mts", ".cts") if stem + ext in files]
                if len(candidates) == 1:
                    if candidates[0] != source:
                        edges.add((source, candidates[0], line, "js_ts_lexical"))
                else:
                    unresolved += 1
        if len(edges) > MAX_EDGES:
            raise GraphError("Graph exceeds the 20000-edge budget.")
    return {"schema_version": 1, "extractor": VERSION,
            "fingerprint": snapshot["fingerprint"], "commit": snapshot["commit"],
            "nodes": sorted(files), "edges": [dict(zip(("source", "target", "line", "method"), edge, strict=True))
                                                for edge in sorted(edges)],
            "coverage": {"scope": "file_imports", "unresolved_imports": unresolved,
                         "issues": issues, "excluded_files": snapshot["excluded_files"],
                         "source_bytes": snapshot["source_bytes"],
                         "limitations": ["No runtime calls or complete impact guarantee",
                                         "JS/TS lexical edges require code verification",
                                         "Package imports, aliases and dynamic expressions are not resolved"]}}
