# Removes AI-DLC Engineering OS registrations from Codex and Claude Code. Memory data is preserved.
$ErrorActionPreference = "Stop"
$VenvPy = Join-Path $HOME ".codex\ai-dlc-mcp\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { throw "AI-DLC Engineering OS is not installed at $VenvPy" }
& $VenvPy -m ai_dlc_mcp.installer uninstall
Write-Host "Registrations removed. Delete $HOME\.codex\ai-dlc-mcp to remove the runtime; memory is preserved (default $HOME\.ai-dlc\memory, or $HOME\.codex\ai-dlc-memory for older installs)."
