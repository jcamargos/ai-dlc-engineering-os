# Measured agent evolution

AI-DLC Engineering OS replaces subjective agent upgrades with an evidence-gated release process and measurable post-release drift detection. It does not retrain model weights and it does not claim equivalence with any aerospace company. It applies public safety-critical engineering principles: traceability, adversarial verification, independent review, staged exposure, deterministic gates, rollback, and post-release evidence.

## Lifecycle

```text
contract change
  -> golden evaluation cases
  -> candidate evaluation against the last passing baseline
  -> quality + safety + coverage + non-regression gates
  -> independent review (two reviewers for R3)
  -> shadow
  -> bounded canary (1-50%)
  -> active
  -> execution receipts and scorecard
  -> drift window over scored receipts
  -> hold/rollback if evidence regresses
```

No release may skip a state. The author cannot approve their own release. R3 releases require two distinct independent approvals. A single safety violation fails the evaluation even when the average score exceeds the threshold.

## Contract assurance

Every one of the 26 canonical agent contracts includes:

- a measurable mission baseline and required outputs;
- an adversarial trust-boundary case covering tenant escape, fabricated evidence, secret exfiltration, and self-approval;
- minimum score `0.85`;
- non-regression against the last passing score;
- zero tolerance for cross-tenant access, fabricated evidence, secret exfiltration, and self-approval;
- maximum autonomous risk `R2` and human approval for `R3`;
- independent review, sandbox, and rollback requirements.

## Drift policy

`get_agent_scorecard` evaluates the latest 20 execution receipts that contain a `quality_score`. Fewer than five scored receipts yield `insufficient_data`; the system does not manufacture confidence from a small sample. A quality delta of `-0.05` against the latest evaluated baseline raises `warning`. A delta of `-0.10`, or average quality below `0.85`, raises `critical` and recommends holding promotion or rolling back an active canary. The decision is deterministic in both SQLite and PostgreSQL-backed runtimes.

## Flight recorder

Each completed remote agent step requires an execution manifest containing agent and prompt versions, contract checksum, model, configuration hash, commit SHA, context manifest, and tool manifest. The server computes the output hash and appends an immutable receipt chained to the previous receipt hash. Data API callers can read receipts but cannot insert, update, or delete them directly.

The chain provides tamper evidence, not absolute tamper prevention against database superusers. Database administrative access remains a separate trust boundary.

## Operating the release tools

1. `bootstrap_agent_eval_cases` creates project cases from the canonical contracts.
2. `start_agent_evaluation` records the candidate provenance and last passing baseline.
3. `record_agent_eval_result` stores evidence for each active case.
4. `complete_agent_evaluation` atomically applies all release gates.
5. `propose_agent_release` accepts only a passing evaluation for the same agent and version.
6. `review_agent_release` records an independent approval or rejection.
7. `advance_agent_release` moves through shadow, canary, and active.
8. `get_agent_scorecard` exposes evaluation, release, receipt, and drift evidence.
9. `rollback_agent_release` retires a bad canary/active version and restores its predecessor when present.

## Verification

The local implementation is covered by Python tests for safety failure, non-regression, independent R3 approval, ordered promotion, chained receipts, drift detection, and rollback restoration.
