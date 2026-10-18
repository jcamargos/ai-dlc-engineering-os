from __future__ import annotations

import os
from pathlib import Path

from . import __version__

APP_NAME = "AI-DLC Engineering OS"
AUTHOR = "Jose Camargo"
CANONICAL_DOMAIN = "https://github.com/jcamargos/ai-dlc-engineering-os"
VERSION = __version__

WORKSPACE_ID = os.getenv("AI_DLC_WORKSPACE_ID", "local")
WORKSPACE_NAME = os.getenv("AI_DLC_WORKSPACE_NAME", "Local Workspace")
# Agents may hard-delete entries they (or a prompt injection) wrote by mistake. Set to 0 to make purge human-only.
ALLOW_AGENT_PURGE = os.getenv("AI_DLC_ALLOW_AGENT_PURGE", "1").lower() in {"1", "true", "yes"}
# Platform v3 opt-in surfaces. Off by default: federation sends data to remote peers (exfiltration risk under
# prompt injection) and the marketplace has no external trust root yet. Enable only in a reviewed deployment.
ENABLE_FEDERATION = os.getenv("AI_DLC_ENABLE_FEDERATION", "0").lower() in {"1", "true", "yes"}
ENABLE_MARKETPLACE = os.getenv("AI_DLC_ENABLE_MARKETPLACE", "0").lower() in {"1", "true", "yes"}
LOG_LEVEL = os.getenv("AI_DLC_LOG_LEVEL", "WARNING").upper()


def default_data_dir(home: Path | None = None) -> Path:
    """Resolve the shared memory directory; every host must resolve it identically.

    Order: ``AI_DLC_DATA_DIR`` > ``~/.ai-dlc/memory`` > legacy ``~/.codex/ai-dlc-memory``.
    The legacy location is used only while it holds a database and the new one does not, so
    installations created before 3.2.0 keep their memory without any automatic move.
    """
    override = os.getenv("AI_DLC_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = home if home is not None else Path.home()
    current = base / ".ai-dlc" / "memory"
    legacy = base / ".codex" / "ai-dlc-memory"
    if (legacy / "memory.db").exists() and not (current / "memory.db").exists():
        return legacy
    return current


DATA_DIR = default_data_dir()
DB_PATH = Path(os.getenv("AI_DLC_DB_PATH", str(DATA_DIR / "memory.db"))).expanduser().resolve()
AGENTS_DIR = Path(os.getenv("AI_DLC_AGENTS_DIR", str(Path(__file__).parent / "agents"))).expanduser().resolve()
