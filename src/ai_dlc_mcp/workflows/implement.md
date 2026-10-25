# Native workflow: implement

Use for a bounded behavior change. Read its acceptance criteria, dependencies and owned
files before editing. Preserve unrelated changes and do not expand the task silently.

1. Identify the smallest observable behavior the change must establish. For a defect,
   use the debug procedure to isolate the cause before choosing the correction.
2. Add a meaningful regression check when behavior warrants it. Run it before the fix
   and inspect why it fails: an import/setup error alone does not prove the regression.
   If it already passes, find a check that exposes the missing behavior or explain why
   this is a refactor covered by existing tests. Never delete user code to manufacture red.
3. Implement the smallest coherent change. Check invalid inputs, boundary conditions
   and applicable authorization, retry, transaction and concurrency paths.
4. Run the targeted checks and inspect results. Refactor only with passing behavioral
   checks, then rerun affected checks. Broaden to relevant integration/static checks.
5. Review the task against its acceptance criteria and technical quality; fix findings
   before marking it complete. Save command evidence and a concise handoff in the plan
   or leased swarm task. Failed or missing checks remain visible as blockers/limitations.

For documentation, visual changes or environments without automation, use an appropriate
reproducible inspection instead of an artificial test. State the alternative and its
limits. Do not create tests that merely repeat implementation text.

Exit: the task's observable outcome is demonstrated and the next task has its interfaces
and evidence. A passing task check does not establish that the entire delivery is ready.
