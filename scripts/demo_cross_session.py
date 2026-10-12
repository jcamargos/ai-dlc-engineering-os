"""Reproducible demo: a decision made in one session is recalled by a different session.

Two separate MCP server processes talk to the same local memory over stdio, the way two
editors (or two days of work) would. A generic MCP client stands in for the editors;
the server, transport and database are the real ones. Nothing is mocked. Run:

    python scripts/demo_cross_session.py               # print the transcript
    python scripts/demo_cross_session.py --svg out.svg # also render the README animation
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT = "checkout-api"


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def _session(data: str, steps):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_DLC_")}
    env["AI_DLC_DATA_DIR"] = data
    params = StdioServerParameters(command=sys.executable, args=["-m", "ai_dlc_mcp.server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await steps(session)


async def record() -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory() as data:
        async def first(s: ClientSession):
            lines.append(("head", "Session 1 · editor A · Monday"))
            await s.call_tool("bootstrap_project", {"project_id": PROJECT, "name": "Checkout API"})
            saved = await s.call_tool("save_decision", {
                "project_id": PROJECT, "title": "Idempotency keys on every payment write",
                "context": "Retries after gateway timeouts created duplicate charges.",
                "decision": "Require an Idempotency-Key header on POST /payments; store keys for 24h.",
            })
            lines.append(("call", "save_decision → Idempotency keys on every payment write"))
            lines.append(("deny", "decision not stored") if saved.is_error else ("ok", "stored as accepted decision"))
            secret = await s.call_tool("save_memory", {"project_id": PROJECT, "kind": "fact", "title": "Gateway",
                                                       "content": "key sk_live_" + "4" * 32})
            lines.append(("call", "save_memory → gateway key sk_live_…"))
            lines.append(("deny" if secret.is_error else "ok", "refused: looks like a credential" if secret.is_error else "stored"))

        async def second(s: ClientSession):
            lines.append(("head", "Session 2 · editor B · Tuesday (new process)"))
            res = await s.call_tool("get_project_context", {"project_id": PROJECT, "task": "add refund endpoint"})
            context = _text(res)
            lines.append(("call", "get_project_context → task: add refund endpoint"))
            recalled = "Idempotency-Key" in context
            lines.append(("ok" if recalled else "deny", "recalled: Idempotency-Key required on payment writes" if recalled else "decision not recalled"))
            leaked = "sk_live_" in context
            lines.append(("ok" if not leaked else "deny", "no credential in context" if not leaked else "credential leaked"))
            stats = json.loads(_text(await s.call_tool("memory_stats", {"project_id": PROJECT})))
            lines.append(("dim", f"memory: one local SQLite file · search: {stats.get('search', 'n/a')}"))

        await _session(data, first)
        await _session(data, second)
    return lines


STYLE = {"head": ("#e6edf3", "700"), "call": ("#7ee787", "400"), "ok": ("#a5d6ff", "400"),
         "deny": ("#ffa198", "400"), "dim": ("#8b949e", "400")}
PREFIX = {"head": "", "call": "› ", "ok": "  ✓ ", "deny": "  ✗ ", "dim": "  "}


def render_svg(lines: list[tuple[str, str]]) -> str:
    width, row, top = 860, 26, 58
    height = top + row * (len(lines) + 1) + 10
    step = 0.9
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           'role="img" aria-label="Recorded demo: a decision saved in one session is recalled by another session; a credential is refused.">',
           "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:15px}"
           ".l{opacity:0;animation:in .35s forwards}@keyframes in{to{opacity:1}}"
           "@media (prefers-reduced-motion:reduce){.l{animation:none;opacity:1}}</style>",
           f'<rect width="{width}" height="{height}" rx="12" fill="#0d1117"/>',
           '<circle cx="24" cy="22" r="6" fill="#ff5f57"/><circle cx="44" cy="22" r="6" fill="#febc2e"/><circle cx="64" cy="22" r="6" fill="#28c840"/>',
           f'<text x="{width // 2}" y="27" fill="#8b949e" text-anchor="middle" font-size="13">recorded by scripts/demo_cross_session.py</text>']
    y = top
    for index, (kind, value) in enumerate(lines):
        if kind == "head" and index:
            y += row // 2
        color, weight = STYLE[kind]
        out.append(f'<text class="l" style="animation-delay:{index * step:.1f}s" x="24" y="{y}" fill="{color}" '
                   f'font-weight="{weight}">{html.escape(PREFIX[kind] + value)}</text>')
        y += row
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg", help="write the animated transcript to this path")
    args = parser.parse_args()
    lines = asyncio.run(record())
    for kind, value in lines:
        print(PREFIX[kind] + value)
    if args.svg:
        Path(args.svg).write_text(render_svg(lines), encoding="utf-8")
    raise SystemExit(1 if any(kind == "deny" and "refused" not in value for kind, value in lines) else 0)


if __name__ == "__main__":
    main()
