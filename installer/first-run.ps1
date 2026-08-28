<#
.SYNOPSIS
  Post-install setup for SVR IOCL Station. Run elevated (the NSIS installer invokes
  this as Administrator).

.DESCRIPTION
  1. Creates the data + per-component log tree under C:\ProgramData\SVR-IOCL (SDD 14.3).
  2. Applies SQLite migrations via svr-migrate.
  3. Registers the two Windows Services (Automatic start) via pywin32.
  4. Adds the Electron frontend as a per-user Startup-folder shortcut (SDD 19 item 23).

.PARAMETER InstallDir
  Root of the installed app (contains the frozen backend and the Electron exe).
  Defaults to the script's parent directory.
#>
param(
  [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
  [string]$DataDir    = "$env:ProgramData\SVR-IOCL"
)

$ErrorActionPreference = "Stop"

Write-Host "SVR IOCL Station - first run setup"
Write-Host "  InstallDir = $InstallDir"
Write-Host "  DataDir    = $DataDir"

# --- 1. data + log tree ------------------------------------------------------
$logDir = Join-Path $DataDir "logs"
New-Item -ItemType Directory -Force -Path $DataDir, $logDir, (Join-Path $DataDir "backups") | Out-Null
foreach ($f in @(
    "backend-service.log", "scheduler.log", "database.log",
    "frontend.log", "email-integration.log", "ocr-processing.log")) {
  $p = Join-Path $logDir $f
  if (-not (Test-Path $p)) { New-Item -ItemType File -Path $p | Out-Null }
}

$env:SVR_DATA_DIR = $DataDir
$env:SVR_DB_PATH  = Join-Path $DataDir "svr.sqlite"
$env:SVR_LOG_DIR  = $logDir

# --- 2. migrations ---------------------------------------------------------------
# Prefer the frozen backend's console script; fall back to a dev install on PATH.
$svrMigrate = Join-Path $InstallDir "backend\svr-migrate.exe"
if (-not (Test-Path $svrMigrate)) { $svrMigrate = "svr-migrate" }
Write-Host "Applying migrations with $svrMigrate ..."
& $svrMigrate

# --- 3. Windows Services ------------------------------------------------------
# Each service module self-registers via pywin32 (win32serviceutil.HandleCommandLine).
$python = Join-Path $InstallDir "backend\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

foreach ($mod in @("svr_backend.services.backend_service", "svr_backend.services.scheduler_service")) {
  Write-Host "Registering $mod (Automatic) ..."
  & $python -m $mod --startup auto install
  & $python -m $mod start
}

# --- 4. frontend Startup shortcut (per-user, not a service) -----------------
$exe = Join-Path $InstallDir "SVR IOCL Station.exe"
if (Test-Path $exe) {
  $startup = [Environment]::GetFolderPath("Startup")
  $lnk = Join-Path $startup "SVR IOCL Station.lnk"
  $ws = New-Object -ComObject WScript.Shell
  $s = $ws.CreateShortcut($lnk)
  $s.TargetPath = $exe
  $s.WorkingDirectory = $InstallDir
  $s.Save()
  Write-Host "Startup shortcut -> $lnk"
} else {
  Write-Warning "Frontend exe not found at $exe - skipping Startup shortcut."
}

Write-Host "Done. Check services.msc for SVR-IOCL-Backend and SVR-IOCL-Scheduler (Running / Automatic)."
