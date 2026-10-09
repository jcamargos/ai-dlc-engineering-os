"""Input hygiene for persisted memory: secret detection, injection flags, limits, ids.

Everything written to the store passes through this module. The goal is that a
model cannot (accidentally or under prompt injection) persist credentials, and
that suspicious "instruction-like" content is labelled before it is ever served
back into another model's context.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# --------------------------------------------------------------------------- limits
MAX_TITLE = 200
MAX_SHORT = 2_000  # reviewer, category, severity, reason, ...
MAX_TEXT = 20_000  # content, decision, evidence, ...
MAX_TAGS = 20
MAX_TAG_LEN = 48

MEMORY_KINDS = frozenset(
    {"fact", "constraint", "pattern", "convention", "preference", "risk", "glossary", "dependency", "runbook", "other"}
)
DECISION_STATUSES = frozenset({"proposed", "accepted", "superseded", "deprecated", "rejected"})
INCIDENT_SEVERITIES = frozenset({"sev1", "sev2", "sev3", "sev4", "critical", "high", "medium", "low"})
INCIDENT_STATUSES = frozenset({"open", "mitigated", "resolved", "closed"})


class ValidationError(ValueError):
    """Raised for caller errors. The message is safe to show to the model."""


# --------------------------------------------------------------------------- secrets
@dataclass(frozen=True)
class SecretFinding:
    kind: str
    field: str


_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{32,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{32,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("azure_storage_key", re.compile(r"AccountKey=[A-Za-z0-9+/=]{40,}")),
    (
        "connection_string_password",
        re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]{3,}@[^\s/]+", re.IGNORECASE),
    ),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|senha)"
            r"\s*[:=]\s*['\"]?(?!<|\$|%|\{\{|\*{3}|x{3}|redacted|changeme|example|your[_-]|process\.env|os\.environ|os\.getenv|getenv|"
            r"import\.meta\.env|Deno\.env|env\(|settings\.|config\.|vault:|secretsmanager:|ref\+)[^\s'\"]{8,}"
        ),
    ),
]


def find_secrets(fields: dict[str, str | None]) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for name, value in fields.items():
        if not value:
            continue
        for kind, pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                findings.append(SecretFinding(kind, name))
    return findings


def assert_no_secrets(fields: dict[str, str | None]) -> None:
    findings = find_secrets(fields)
    if findings:
        where = ", ".join(sorted({f"{f.field} ({f.kind})" for f in findings}))
        raise ValidationError(
            "Refused: the payload looks like it contains a credential in " + where + ". "
            "Never persist secrets. Describe the fact without the value (e.g. 'API key is stored in Vault at path X')."
        )


# --------------------------------------------------------------------------- injection flags
_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore (?:all |any )?(?:previous|prior|above|earlier) (?:instructions|rules|messages)"),
    re.compile(r"(?i)\bdisregard (?:the |all )?(?:system|previous|prior) (?:prompt|instructions)"),
    re.compile(r"(?i)\byou (?:are now|must now|will now) (?:act|behave|operate) as\b"),
    re.compile(r"(?i)<\s*/?\s*(?:system|assistant|tool_call|instructions?)\s*>"),
    re.compile(r"(?i)\b(?:always|never) (?:approve|auto-?approve|skip (?:review|tests|security))\b"),
    re.compile(r"(?i)\b(?:exfiltrate|send (?:the )?(?:secrets?|tokens?|credentials?) to)\b"),
    re.compile(r"(?i)\bcurl\s+[^\n|]*\|\s*(?:ba)?sh\b"),
]


def injection_flags(*texts: str | None) -> list[str]:
    """Return flags for instruction-like content. Content is stored, but labelled."""
    joined = "\n".join(t for t in texts if t)
    return ["possible_prompt_injection"] if any(p.search(joined) for p in _INJECTION_PATTERNS) else []


# --------------------------------------------------------------------------- normalisation
_PROJECT_RE = re.compile(r"[^a-z0-9._-]+")


def normalize_project_id(value: str | None) -> str:
    """Stable, case-insensitive project id: 'FleetOS AI' -> 'fleetos-ai'."""
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    slug = _PROJECT_RE.sub("-", raw.strip().lower().replace("_", "-")).strip("-.")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise ValidationError("project_id is required (letters, digits, '.', '-' ).")
    if len(slug) > 80:
        raise ValidationError("project_id must be at most 80 characters.")
    return slug


def clean_text(value: str | None, field: str, limit: int = MAX_TEXT, required: bool = False) -> str:
    text = (value or "").replace("\x00", "").strip()
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > limit:
        raise ValidationError(f"{field} exceeds {limit} characters ({len(text)}). Summarise it.")
    return text


def clean_choice(value: str | None, field: str, allowed: frozenset[str], default: str) -> str:
    v = (value or default).strip().lower()
    if v not in allowed:
        raise ValidationError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return v


def clean_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = (t or "").strip().lower()[:MAX_TAG_LEN]
        if t and t not in out:
            out.append(t)
    if len(out) > MAX_TAGS:
        raise ValidationError(f"At most {MAX_TAGS} tags.")
    return out


def clamp_confidence(value: float | int | str | None, default: float) -> float:
    try:
        v = float(value if value is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValidationError("confidence must be a number between 0 and 1.") from exc
    return min(1.0, max(0.0, v))
