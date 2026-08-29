<#
.SYNOPSIS
  One-shot local build of the SVR IOCL Station Windows installer.

.DESCRIPTION
  1. Freezes the Python backend  -> backend/packaging/dist/svr-backend/
  2. Packages the Electron app   -> installer/output/SVR-IOCL-Station-Setup-*.exe
     (electron-builder bundles the frozen backend as resources/backend/ and runs
     first-run.ps1 elevated on install - see frontend/build/installer.nsh).

  Prereqs: Python 3.11+ (a backend/.venv is used if present), Node 20+, and
  `npm ci` already run in frontend/.

.PARAMETER SkipBackendInstall
  Pass through to build-backend.ps1: assume PyInstaller + deps are already present.
#>
param(
  [switch]$SkipBackendInstall
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "== 1/2  Freezing backend =="
& (Join-Path $repo "backend\packaging\build-backend.ps1") -SkipInstall:$SkipBackendInstall

Write-Host ""
Write-Host "== 2/2  Packaging Electron installer =="
Push-Location (Join-Path $repo "frontend")
try {
  if (-not (Test-Path "node_modules")) { throw "run 'npm ci' in frontend/ first" }
  & npm run dist
}
finally {
  Pop-Location
}

Write-Host ""
Get-ChildItem (Join-Path $repo "installer\output") -Filter *.exe | ForEach-Object {
  Write-Host "Installer: $($_.FullName)  ($([math]::Round($_.Length / 1MB, 1)) MB)"
}
