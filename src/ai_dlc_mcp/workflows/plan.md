# Native workflow: plan

Use for multi-step implementation after the outcome is understood. Keep the plan in
the repository's established location or the host's durable task artifact; record its
reference in the task context. A small change can use a short inline plan.

For each independently reviewable deliverable, record:

| Field | Required content |
| --- | --- |
| Identity | Stable task ID, objective and relevant acceptance criteria |
| Scope | Files/components owned; existing interfaces and invariants to preserve |
| Dependencies | Earlier task IDs and exact interfaces or artifacts consumed/produced |
| Verification | Command or reproducible check, expected behavior and failure cases |
| Status | Pending, active, blocked or complete, with evidence references |
| Handoff | Changed files, unresolved issues, next action and relevant decisions |

1. Inspect similar implementations before prescribing file paths or interfaces.
2. Order tasks by dependencies. Include negative cases and compatibility checks with
   the task that owns the behavior. Avoid isolated scaffolding with no usable outcome.
3. Choose inline execution unless authorized delegation materially helps. A delegated
   brief includes its task, shared constraints, relevant source references and acceptance
   checks; avoid passing the entire conversation. Assign non-overlapping ownership.
4. Use the existing swarm ledger only when coordination warrants it. Link the plan and
   swarm ID; use atomic claims and leases. Do not create a second competing status ledger.
5. Include a final cross-task review and delivery/rollback check. Replan when evidence
   invalidates an assumption, preserving completed work and explaining the scope change.

Exit: each task has a checkable outcome and enough context to resume independently.
After interruption, read the saved plan and `get_swarm(..., recovery=true)` when used;
validate completed evidence freshness before resuming remaining work.
