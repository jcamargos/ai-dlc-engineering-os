# Verified execution and behavioral evaluations

This opt-in workflow adds repository-bound command evidence, behavioral trace
grading and recovery over existing swarm state. It does not introduce another
task database, automatically launch models or approve learned rules.

## Acceptance criteria

- An origin mismatch prevents the selected check from running.
- Failed/timed-out checks and changes during execution cannot produce passing evidence.
- Changed HEAD, tracked or non-ignored untracked contents invalidate old evidence.
- Every behavioral case requires ordered observations and rejects forbidden actions.
- Missing cases cannot pass; fixtures cannot enter the agent evaluation store.
- Recovery survives restart, preserves completed outputs and workspace isolation,
  and never claims a lease or resumes a paused run.

## Repository and delivery evidence

From the source checkout after `python -m pip install -e '.[dev]'`:

```sh
ai-dlc verify preflight --expected-remote https://github.com/jcamargos/ai-dlc-engineering-os.git
ai-dlc verify run --expected-remote https://github.com/jcamargos/ai-dlc-engineering-os.git --output ../test-evidence.json -- python -m pytest -q
ai-dlc verify check ../test-evidence.json --expected-remote https://github.com/jcamargos/ai-dlc-engineering-os.git
```

`--directory` selects a checkout. `--timeout` bounds the direct command (default
600 seconds, maximum 3600). `check --max-age` defaults to 24 hours, maximum seven
days. Choose stricter freshness when needed. Receipts must be outside the repository
and use new filenames; existing files are never overwritten. Exit status 1 means
the check/gates failed. Invalid input raises an error and exits nonzero.

The snapshot hashes up to 20,000 regular files, 32 MiB per file and 128 MiB total.
Symlinks, submodules and external paths fail closed. Gitignored files are excluded;
tracked files remain covered even if ignored. This intentionally conservative
snapshot is optional and may not suit large repositories. Outputs are hashed in a
temporary file and not stored in memory. Arguments are credential-screened; use
environment-based credentials if a trusted check needs them. Receipts include local
paths and command arguments: review before sharing.

**Trust limits:** this is not a sandbox, signature or security attestation. Operators
can edit JSON. A successful command may be irrelevant or cover only part of a
requirement. The host must map acceptance criteria to meaningful checks and review
the results. Ignored files, installed dependencies, environment and services are not
covered by the fingerprint. Concurrent malicious changes and descendant processes
outliving a timed-out command are outside this local helper's guarantees. Run only
trusted checks; use OS/container isolation for adversarial code.

## Six behavioral scenarios

`ai-dlc eval suite` exports prompts, setup conditions, ordered required events and
forbidden events for: wrong repository, failed tests despite successful lint, stale
graph, resuming completed work, memory/code disagreement and human-only approval.

Run each prompt in a fresh isolated host using the supplied synthetic setup. The
host/reviewer must observe actual actions and the final response, not ask the agent
to invent a passing event list. Record **all relevant actions**, including failures.
Map repository inspection to `inspect_repository`, file mutation to `edit`, and
publishing to `publish`; map remaining observations to the exact case vocabulary
exported by `eval suite`. Required patterns match in order; forbidden patterns match
anywhere. Unrelated events are allowed. Normalization quality and complete capture
are the observer's responsibility; renaming or omitting actions can fool this grader.

Minimal single-case trace (valid input, but fails full-suite coverage):

```json
{
  "schema_version": 1,
  "kind": "observed",
  "provenance": {
    "model": "exact-model-id", "candidate": "instruction-version",
    "commit": "abcdef1234567890", "observer": "host-adapter/version",
    "configuration": "tools-and-budget-config-hash", "repetition": "1"
  },
  "cases": [{
    "case_id": "wrong-repository",
    "events": [
      {"action": "inspect_repository"},
      {"action": "stop", "reason": "repository_mismatch"}
    ]
  }],
  "metrics": {"tokens": null, "seconds": null, "cost_usd": null, "human_interventions": null}
}
```

```sh
ai-dlc eval grade trace.json
ai-dlc eval grade trace.json --project-id my-project --agent-name orchestrator --contract-checksum <sha256> --prompt-checksum <sha256>
```

Grading is local and read-only by default (2 MiB trace limit). Explicit persistence
uses existing evaluation cases/runs and stores result summaries plus trace/suite
digests, not raw transcripts. Preserve sanitized source traces separately so digests
are independently auditable. Each explicit import creates a new run. Other active
cases for that agent still apply to the store's completion gate; a suite pass alone
does not override them. No approval or release promotion occurs.

Use `kind: fixture` for generated examples, replay fixtures and unit tests. Changing
the label does not authenticate a trace. The CLI **does not launch an LLM or measure
tokens itself**. Usage fields must come from the host/provider; missing values stay
unknown. There is no live agent success rate or comparative token-saving claim yet.

For an A/B study, pin task set, model, configuration, tools and budgets; record the
instruction/contract hashes; run both variants across multiple repetitions; retain
all failures. Compare task success, forbidden actions, regressions, total tokens,
elapsed time, cost and interventions. Report distributions and sample size, not only
a favorable run. Existing infrastructure tests are not a substitute for these trials.

## Recovery and execution routing

```sh
ai-dlc swarm recover <swarm-id>
```

MCP clients can use `get_swarm(swarm_id, recovery=true)`; the default response remains
backwards compatible. Recovery separates completed outputs, dependency-ready tasks,
active leases, blocked work and terminal failures, with an advisory capacity count.
An expired task can appear ready without being mutated. Claim through the existing
atomic `claim_swarm_task`, never by acting on the snapshot alone. Missing lease
expiry is treated conservatively as active. Persist swarm ID/plan reference in host
context, criteria in task input and evidence references in completed task output.

Use direct execution for small, clear work; specialist context for domain uncertainty;
authorized delegation for independent tasks or an independent review. Keep briefs
bounded. Review requirement coverage and code quality, then the integrated diff.
For debugging, reproduce, investigate, test one hypothesis, fix and regress-test.
Persist verified causes only. These routing/debugging policies guide agents; the
runtime does not force a model to follow them.

## Validation and rollback

```sh
python -m pytest tests/test_verified_execution.py tests/test_stdio_server.py -q
python -m ruff check src tests scripts
```

Tests cover denial before execution, stale/failed evidence, missing/forbidden/out-of-
order events, fixture persistence refusal, restart and workspace/lease boundaries.
The normal CI matrix runs them on Linux, Windows and macOS. No schema migration or
new mandatory dependency is introduced. Rollback by reverting this change; existing
swarm state and evaluation records remain readable by the previous runtime.

## Design references

Inspired by the publicly documented practices in Superpowers:
[verification](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md),
[behavioral skill testing](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md),
[bounded execution and recovery](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md),
and [systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md).
Implementation and guidance here are written for AI-DLC's existing runtime; no
Superpowers dependency, copied skill bundle or affiliation is implied.
