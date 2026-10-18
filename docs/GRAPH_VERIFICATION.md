# Repository graph verification

Scope: local optional import graph, schema v3, MCP exposure, three READMEs and
AI-DLC presentation. Verified on Windows / Python 3.13 on 2026-10-17.

| Check | Evidence |
|---|---|
| Full Python suite | `python -m pytest -q -rs`: 131 passed, 4 skipped, 14 subtests passed |
| Graph store regressions | 20 passed, 1 symlink test skipped; included in full suite |
| Real MCP transport | `tests/test_graph_mcp.py`, `tests/test_stdio_server.py`, `tests/test_server_e2e.py` passed |
| Static checks | `python -m ruff check src tests scripts` passed |
| Contracts/manifests | `validate_agent_registry.py` and `validate_platform_v3.py` passed; 26 specialists, 43 default + 5 opt-in tools |
| Documentation | `python scripts/validate_readmes.py` passed for EN/PT-BR/ES |
| Reproducible demo | `python scripts/demo_repository_graph.py`: transitive evidence, stale refusal and refresh passed |
| Packaging | `python -m build --wheel` passed |
| Installation | `python scripts/smoke_setup.py dist/ai_dlc_engineering_os-3.2.0-py3-none-any.whl` passed for isolated Codex, Claude Code, VS Code and Cursor homes; 43-tool handshake survives launcher-cache removal |
| TypeScript SDK | `npm ci`, `npm run build`, `npm test`: 2 passed; `npm audit --audit-level=high`: 0 vulnerabilities |
| Python dependencies | `python -m pip_audit --skip-editable`: no known vulnerabilities after updating the isolated verification environment's pip |

The four Windows skips require symbolic-link privilege: three existing installer
tests and one graph exclusion test. The CI matrix runs Python 3.10/3.13 on Linux,
macOS and Windows; check the PR run for those platform results rather than treating
this local record as evidence for other operating systems.

Review covered allowlist denial, traversal validation, source exclusion, bounded
reads/results, workspace ownership, stale refusal, failed-refresh preservation,
project merge/purge and migration from schema v2 without losing memory. Indexing
performs two scans; querying rehashes files. This costs local I/O and is not a
constant-time query or a measured token-saving guarantee.

Rollback: remove `AI_DLC_GRAPH_ROOTS` and restart the MCP server to deny graph reads.
The additive graph table can remain when reverting code. Existing command aliases,
SDK imports, ownership markers and embedding model identifiers remain compatible;
historical licensing notices remain intact.

This verifies installation files and the real MCP protocol, not discovery/delegation
inside every live editor UI. No PyPI release or personal MCP installation was updated.
