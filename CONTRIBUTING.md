# Contributing

Thanks for helping improve AI-DLC Engineering OS.

## Ground rules
- Open an issue before large changes; the core scope is intentionally small (local runtime,
  agents, installer, plugin, SDK clients).
- Every change needs tests and must keep these green: `ruff check src tests scripts`,
  `python scripts/validate_agent_registry.py`, `python scripts/validate_platform_v3.py`, `pytest`.
- Never commit secrets, real customer data or production identifiers.
- Agent guides (`src/ai_dlc_mcp/agents/*.md`) carry a generated contract block; edit
  `contracts/agent_contracts.json` and run `python scripts/validate_agent_registry.py --write`.

## Contributor License Agreement
By submitting a contribution you agree that:
1. you wrote it or have the right to submit it;
2. it is licensed to the project under the Apache License 2.0; and
3. you grant the copyright holder a perpetual, worldwide, irrevocable, royalty-free license to
   use, modify, sublicense and relicense your contribution, including in the commercial
   AI-DLC OS Cloud offering.

Add `Signed-off-by: Your Name <email>` to each commit (`git commit -s`) to confirm.

## Support
Community support only (issues/discussions). There is no SLA for the open-source edition.
