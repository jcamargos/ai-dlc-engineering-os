# Native workflow: discover

Use when the requested behavior, constraints or architecture are materially uncertain.
For a clear small correction, capture the acceptance check and proceed directly.

1. Confirm the requested repository against Git origin and inspect the working tree.
   Read applicable repository instructions and the smallest relevant specs, code and tests.
   Retrieve project context; reconcile conflicts against current source evidence.
2. State the user-visible outcome, non-goals, compatibility constraints and observable
   acceptance criteria. Label assumptions and unanswered questions separately from facts.
3. Resolve uncertainty through targeted inspection first. Ask the user only about choices
   that materially affect the outcome and cannot be inferred; continue independent work.
4. For a consequential design choice, compare viable options using failure behavior,
   security boundaries, migration/rollback, maintenance and operational cost. Recommend
   the smallest sufficient option. Record an accepted decision, not an unapproved proposal.
5. Hand off a short specification: outcome, affected components, invariants, acceptance
   checks, chosen approach, residual risks and sources. Keep it with the task's plan.

Exit: the implementation can be assessed against concrete behavior. An unresolved
security boundary, destructive migration or conflicting requirement blocks dependent
work; routine implementation choices do not require an extra approval ceremony.
