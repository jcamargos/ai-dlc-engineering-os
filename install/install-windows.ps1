# AI-DLC Engineering OS - global install for Codex + Claude Code (Windows).
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File .\install\install-windows.ps1 [-Only codex|claude] [-DryRun]
param(
  [ValidateSet("", "codex", "claude", "vscode", "cursor")][string]$Only = "",
  [switch]$DryRun,
  [string]$Target = (Join-Path $HOME ".codex\ai-dlc-mcp")
)
$ErrorActionPreference = "Stop"
$Source = Split-Path -Parent $PSScriptRoot

function Find-Python {
  foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
    $cmd = Get-Command $c[0] -ErrorAction SilentlyContinue
    if (-not $cmd -or $cmd.Source -like "*WindowsApps*") { continue }   # skip the Microsoft Store stub
    $probe = @($c | Select-Object -Skip 1) + @("-c", "import sys; print(sys.version_info >= (3,10))")
    if ((& $cmd.Source @probe) -eq "True") { return @($cmd.Source) + @($c | Select-Object -Skip 1) }
  }
  throw "Python 3.10+ not found. Install it from https://www.python.org/downloads/ and re-run."
}

Write-Host "AI-DLC Engineering OS -> $Target"
$Py = Find-Python
$Venv = Join-Path $Target ".venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $Target | Out-Null
if (-not (Test-Path $VenvPy)) { & $Py[0] @($Py | Select-Object -Skip 1) -m venv $Venv }
# Snapshot the memory database before an upgrade can migrate it (sqlite online backup, WAL-safe).
# Same resolution as ai_dlc_mcp.config.default_data_dir: override > ~/.ai-dlc/memory > legacy ~/.codex location.
$Legacy = Join-Path $HOME ".codex\ai-dlc-memory"
$Current = Join-Path $HOME ".ai-dlc\memory"
if ($env:AI_DLC_DATA_DIR) { $Data = $env:AI_DLC_DATA_DIR }
elseif ((Test-Path (Join-Path $Legacy "memory.db")) -and -not (Test-Path (Join-Path $Current "memory.db"))) { $Data = $Legacy }
else { $Data = $Current }
$Db = if ($env:AI_DLC_DB_PATH) { $env:AI_DLC_DB_PATH } else { Join-Path $Data "memory.db" }
if (Test-Path $Db) {
  $Snap = Join-Path (Split-Path $Db) ("backups\pre-install-" + (Get-Date -Format "yyyyMMddHHmmss") + ".db")
  New-Item -ItemType Directory -Force -Path (Split-Path $Snap) | Out-Null
  & $VenvPy -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $Db $Snap
  Write-Host "Memory backup: $Snap"
}
& $VenvPy -m pip install --quiet --upgrade pip
& $VenvPy -m pip install --quiet --upgrade $Source
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$installArgs = @("-m", "ai_dlc_mcp.installer", "install")
if ($Only) { $installArgs += @("--only", $Only) }
if ($DryRun) { $installArgs += "--dry-run" }
& $VenvPy @installArgs
if ($LASTEXITCODE -ne 0) { throw "installer failed" }
& $VenvPy -m ai_dlc_mcp.installer doctor
Write-Host "`nAdmin CLI: $Venv\Scripts\ai-dlc-admin.exe  (approvals, purge, backup)"
