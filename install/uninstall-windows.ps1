# Removes AgentShield registrations from Codex and Claude Code. Memory data is preserved.
$ErrorActionPreference = "Stop"
$VenvPy = Join-Path $HOME ".codex\ai-dlc-mcp\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { throw "AgentShield is not installed at $VenvPy" }
& $VenvPy -m ai_dlc_mcp.installer uninstall
Write-Host "Registrations removed. Delete $HOME\.codex\ai-dlc-mcp to remove the runtime; memory stays in $HOME\.codex\ai-dlc-memory."
