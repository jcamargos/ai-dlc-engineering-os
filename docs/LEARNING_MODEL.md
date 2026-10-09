# Learning model

This package does not change LLM weights. Cross-session learning is retrieval-backed memory.

```text
TASK → retrieve context → implement/verify → record outcome/lesson → candidate knowledge → evidence/review → verified lesson → optional candidate agent rule → human governance → approved rule → future retrieval
```

Persist only durable information: invariants, architectural decisions, integration quirks, repeated failure patterns, incident prevention, validated implementation patterns and explicit constraints.

Do not persist conversational filler or secrets. Confidence metadata is not truth; current repository behavior and tests override stale memory.

Agent evolution is a separate governed path: learned knowledge may suggest a contract change, but it cannot promote an agent release. A changed contract must pass golden evaluations, safety and non-regression gates, independent review, staged rollout and rollback readiness. Execution receipts feed future candidate lessons; receipts never auto-approve knowledge or releases.
