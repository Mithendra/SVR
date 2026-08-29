<#
.SYNOPSIS
  Uninstall-time teardown for SVR IOCL Station. Runs elevated from the NSIS
  customUnInstall hook (frontend/build/installer.nsh).

.DESCRIPTION
  Stops and deletes the two Windows Services and removes the per-user Startup
  shortcut. It deliberately DOES NOT touch C:\ProgramData\SVR-IOCL - the SQLite
  database, the nightly backups and the logs are business records and are left in
  place. A reinstall picks them straight back up.

.PARAMETER InstallDir
  Root of the installed app (holds resources\backend\ with the service exes).
#>
param(
  [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
  [string]$DataDir     = "$env:ProgramData\SVR-IOCL"
)

# Best-effort: never let a teardown hiccup block the uninstaller.
$ErrorActionPreference = "Continue"

Write-Host "SVR IOCL Station - uninstall teardown"

$backendDir    = Join-Path $InstallDir "resources\backend"
$backendSvcExe = Join-Path $backendDir "svr-backend-service.exe"
$schedSvcExe   = Join-Path $backendDir "svr-scheduler-service.exe"

function Remove-SvrService([string]$Name, [string]$Exe) {
  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if (-not $svc) { Write-Host "  $Name not present - skipping."; return }
  if ($svc.Status -ne "Stopped") {
    Write-Host "  stopping $Name ..."
    Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
    (Get-Service -Name $Name -ErrorAction SilentlyContinue).WaitForStatus("Stopped", "00:00:20") 2>$null
  }
  if ((Test-Path $Exe)) {
    & $Exe remove | Out-Null           # pywin32 self-deregister
  }
  if (Get-Service -Name $Name -ErrorAction SilentlyContinue) {
    & sc.exe delete $Name | Out-Null   # fallback / make sure it's gone
  }
  Write-Host "  $Name removed."
}

Remove-SvrService "SVR-IOCL-Backend"   $backendSvcExe
Remove-SvrService "SVR-IOCL-Scheduler" $schedSvcExe

# per-user Startup shortcut
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "SVR IOCL Station.lnk"
if (Test-Path $lnk) { Remove-Item -Force $lnk; Write-Host "  removed Startup shortcut." }

# Machine env vars we created (leave SVR_FIELD_KEY? no - if data is kept, the key
# must be kept too, or kept records become unreadable). Keep them all.
Write-Host "  keeping machine config + data tree at $DataDir (DB, backups, logs)."
Write-Host "Done."
