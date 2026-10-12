#!/usr/bin/env sh
# AI-DLC Engineering OS - global install for Codex + Claude Code (macOS/Linux).
# Usage: ./install/install.sh [--only codex|claude] [--dry-run]
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
TARGET="${AI_DLC_TARGET:-$HOME/.codex/ai-dlc-mcp}"
PY=$(command -v python3 || command -v python || true)
[ -n "$PY" ] || { echo "Python 3.10+ not found" >&2; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python 3.10+ required" >&2; exit 1; }
mkdir -p "$TARGET"
[ -x "$TARGET/.venv/bin/python" ] || "$PY" -m venv "$TARGET/.venv"
# Same resolution as ai_dlc_mcp.config.default_data_dir: override > ~/.ai-dlc/memory > legacy ~/.codex location.
if [ -n "${AI_DLC_DATA_DIR:-}" ]; then DATA="$AI_DLC_DATA_DIR"
elif [ -f "$HOME/.codex/ai-dlc-memory/memory.db" ] && [ ! -f "$HOME/.ai-dlc/memory/memory.db" ]; then DATA="$HOME/.codex/ai-dlc-memory"
else DATA="$HOME/.ai-dlc/memory"; fi
DB="${AI_DLC_DB_PATH:-$DATA/memory.db}"
if [ -f "$DB" ]; then
  SNAP="$(dirname "$DB")/backups/pre-install-$(date +%Y%m%d%H%M%S).db"
  mkdir -p "$(dirname "$SNAP")"
  "$TARGET/.venv/bin/python" -c 'import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' "$DB" "$SNAP"
  echo "Memory backup: $SNAP"
fi
"$TARGET/.venv/bin/python" -m pip install --quiet --upgrade pip
"$TARGET/.venv/bin/python" -m pip install --quiet --upgrade "$SRC"
"$TARGET/.venv/bin/python" -m ai_dlc_mcp.installer install "$@"
"$TARGET/.venv/bin/python" -m ai_dlc_mcp.installer doctor
echo "Admin CLI: $TARGET/.venv/bin/ai-dlc-admin"
