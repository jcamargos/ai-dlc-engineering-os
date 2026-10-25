# Native workflow: debug

Use for unexpected behavior, failed tests or regressions. In an incident, prioritize
authorized containment and preserve evidence before deeper investigation.

1. Capture the expected/observed behavior and a minimal reproduction, including relevant
   versions and conditions. If intermittent, measure frequency and gather safe diagnostic
   evidence; inability to reproduce is an uncertainty, not proof of a cause.
2. Inspect the error, recent changes and a comparable working path. Trace the failing
   value through component boundaries until the first violated invariant is identified.
   Log only necessary redacted diagnostics; never dump credentials or customer payloads.
3. Record one hypothesis, its supporting evidence and a discriminating experiment with
   an expected result. Change one relevant variable, run it and record the observation.
4. Reject unsupported hypotheses. Revert only your own experimental changes when no
   longer needed. Repeated failures require reassessing assumptions, environment and
   architecture rather than stacking speculative patches. Escalate material scope changes.
5. Turn the reproducer into a regression check where feasible, apply the correction,
   and rerun it plus affected checks. Separate containment from a confirmed permanent fix.

Exit: reproduction, supported cause, correction and verification are linked. If evidence
is insufficient, report the remaining hypothesis and next experiment instead of claiming
resolution. Persist a verified lesson only when the evidence supports it.
