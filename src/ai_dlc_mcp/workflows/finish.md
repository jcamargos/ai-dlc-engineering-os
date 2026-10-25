# Native workflow: finish

Use before declaring completion, handing off work or publishing an authorized change.

1. Compare the final diff with the requested outcome and plan. Reconcile task statuses;
   inspect the working tree so unrelated files are excluded from delivery.
2. Run the checks that support each claim against the final state. Inspect exit status,
   failed/skipped cases and coverage limits. `ai-dlc verify` can bind command evidence to
   repository identity and content; receipts are local unsigned evidence, not certification.
3. Complete the integrated review. Document compatibility, security, operational impact
   and rollback proportional to the change. Recheck affected behavior after any repair.
4. Deliver within existing authorization: local handoff, PR, merge or deployment as
   requested. If approval is required and missing, present the concrete verified result
   for that approval. Do not infer deployment permission from permission to edit code.
5. Preserve a recovery record: repository/commit, plan and swarm references, completed
   outputs, remaining blockers and next action. Clean up only task-owned disposable
   resources after checking for uncommitted work. Record a durable task outcome with evidence.

Report what changed, which checks passed, what remains unverified and where the result
is available. Tests of a workflow loader or evaluator do not establish agent compliance,
token savings or superiority; those require observed, comparable model evaluations.

Exit: the requested delivery is complete or its exact blocking condition is visible.
