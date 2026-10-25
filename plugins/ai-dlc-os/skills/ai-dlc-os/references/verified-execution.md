# Verified execution

Use the installed `ai-dlc verify preflight --expected-remote <requested-git-url>`
before material changes. This compares origin identity and captures HEAD plus
tracked and non-ignored untracked file content. The Git URL must come from the
user's target or established project configuration, not be inferred from the
checkout you are trying to validate. HTTPS and SSH identities are comparable.

For a relevant check:

```sh
ai-dlc verify run --expected-remote <requested-git-url> --output <outside-repo>/tests.json -- python -m pytest -q
ai-dlc verify check <outside-repo>/tests.json --expected-remote <requested-git-url>
```

Use a new output filename for each run. Commands run locally without a shell; they
are trusted operator-selected programs, not sandboxed. Review any test code before
execution. A receipt records command arguments, timestamps, commit, file fingerprint,
exit code and output digest. It does not retain logs; keep sanitized logs separately
when needed for diagnosis. Recheck after edits. Ignored inputs, dependencies and
external services are not fingerprinted; account for these in the verification plan.
Receipts are unsigned local evidence, not human approval or coverage proof.

For recovery, `get_swarm(swarm_id, recovery=true)` returns completed outputs, ready
tasks, active leases, blocked tasks and terminal failures. This is a read-only view;
`claim_swarm_task` is the authoritative concurrency boundary. Include acceptance
criteria and file ownership in task input; put verification references in task output
and the plan reference in swarm metadata. Check repository identity and freshness
again after a restart. Do not rerun completed work just because context was lost.

For agent-instruction changes, run the six scenarios from `ai-dlc eval suite` in an
isolated host with synthetic data. A trusted host adapter or reviewer translates the
actual ordered tool calls and final response into the documented events; the agent
must not grade itself. `ai-dlc eval grade trace.json` reports omissions, forbidden
actions and missing cases. Only observed runs may be explicitly persisted through
`--project-id` with contract and prompt checksums. No model is called by this CLI.
Compare the same tasks, model, tool permissions, budgets and repeated trials before
claiming an improvement. Report missing usage measurements as unknown, never zero.
