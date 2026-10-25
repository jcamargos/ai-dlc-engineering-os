# Native workflow: review

Use after each meaningful task and again over the complete change. Review actual source,
diff and check outputs; an implementer's summary is a starting point, not proof.

1. Check requirement coverage first: map acceptance criteria to behavior and evidence.
   Identify missing behavior, unintended scope and compatibility changes.
2. Check implementation quality: inspect failure paths, input/permission boundaries,
   data integrity, concurrency, maintainability and relevant operational/performance risk.
   Evaluate whether tests would catch a plausible regression, not just whether they pass.
3. For each material finding, provide severity, precise location, triggering condition,
   user impact and a reproducible check or clear reasoning. Distinguish facts from doubts.
4. Resolve valid findings with focused changes and rerun affected checks. If a finding is
   disputed, inspect or reproduce it before accepting/rejecting it; do not edit blindly.
5. Review the integrated diff after task reviews to catch mismatched interfaces and missing
   cross-task checks. Track unresolved material findings explicitly in the delivery record.

Use an independent reviewer only when authorized and available. Otherwise perform a
separate self-review pass and label it honestly. Neither review mode grants human approval
of governed rules/releases or proves exhaustive correctness.

Exit: criteria coverage and technical findings are recorded, with evidence for resolutions
and remaining risks. A critical failing check prevents claiming the change is ready.
