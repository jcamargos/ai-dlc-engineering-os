# Contributing

Thanks for helping improve AI-DLC Engineering OS.

## Ground rules
- Open an issue before large changes; the core scope is intentionally small (local runtime,
  agents, installer, plugin, SDK clients).
- Every change needs tests and must keep these green: `ruff check src tests scripts`,
  `python scripts/validate_agent_registry.py`, `python scripts/validate_platform_v3.py`, `pytest`.
- Never commit secrets, real customer data or production identifiers.
- Keep `README.md` (English), `README.pt-BR.md` (Brazilian Portuguese) and `README.es.md` (Spanish) synchronized
  when changing features, commands, requirements, version details or examples.
  Run `python scripts/validate_readmes.py` to verify local links and shared feature coverage.
- Agent guides (`src/ai_dlc_mcp/agents/*.md`) carry a generated contract block; edit
  `contracts/agent_contracts.json` and run `python scripts/validate_agent_registry.py --write`.

## Developer Certificate of Origin
Contributions are accepted under the Apache License, Version 2.0 and the
[Developer Certificate of Origin](https://developercertificate.org/): by signing off you certify
that you wrote the change or have the right to submit it under the project's license.

Add `Signed-off-by: Your Name <email>` to each commit (`git commit -s`).

## Support
Community support only (issues/discussions). There is no SLA for the open-source edition.
