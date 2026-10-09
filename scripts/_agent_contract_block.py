"""Render the generated contract block embedded in each agent guide."""
from __future__ import annotations

from typing import Any

BEGIN = "<!-- contract:begin (generated from contracts/agent_contracts.json; do not edit) -->"
END = "<!-- contract:end -->"


def render_contract_block(contract: dict[str, Any]) -> str:
    p = contract.get("permissions", {})
    rc = contract.get("risk_controls", {})
    lines = [
        BEGIN,
        "## Contract",
        f"- **Mission:** {contract['mission']}",
        f"- **Version:** {contract['version']}",
        f"- **Reads:** {', '.join(contract.get('reads', []))}",
        f"- **Writes:** {', '.join(contract.get('writes', []))}",
        f"- **Hands off to:** {', '.join(contract.get('handoff', []))}",
        f"- **Permissions:** code `{p.get('code')}` · memory `{p.get('memory')}` · secrets `{p.get('secrets')}` · "
        f"promote knowledge `{str(p.get('promote_knowledge')).lower()}`",
        f"- **Max autonomous risk:** {rc.get('maximum_autonomous_risk')} · R3 needs human approval · "
        f"self-approval {'forbidden' if contract.get('self_approval') is False else 'ALLOWED'} · "
        f"evidence {'required' if contract.get('requires_evidence') else 'optional'}",
        END,
    ]
    return "\n".join(lines)


def replace_block(text: str, block: str) -> str:
    start, end = text.find(BEGIN), text.find(END)
    if start == -1 or end == -1:
        raise ValueError("contract block markers not found")
    return text[:start] + block + text[end + len(END):]


def extract_block(text: str) -> str | None:
    start, end = text.find(BEGIN), text.find(END)
    return None if start == -1 or end == -1 else text[start:end + len(END)]
