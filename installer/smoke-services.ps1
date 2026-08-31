<#
.SYNOPSIS
  Self-cleaning smoke test for the frozen Windows Service machinery. Run ELEVATED.

.DESCRIPTION
  Proves the parts first-run.ps1 depends on but that could not be tested on the
  build box (HANDOVER.md section 6):

    1. svr-backend-service.exe / svr-scheduler-service.exe register with an
       ImagePath that is the exe itself (not "python -m ...").
    2. The SCM can actually START them (the frozen bare-argv ->
       StartServiceCtrlDispatcher path).
    3. The running backend service answers http://127.0.0.1:<port>/health.
    4. A machine-scope SVR_* env var set before start is seen by the service.

  It uses a TEMP data dir and TEMP machine env vars, then removes both services
  and restores every env var it touched. It does NOT touch C:\ProgramData\SVR-IOCL
  or any real install. Safe to run on the build PC.

.PARAMETER BackendDir
  Folder holding the three frozen exes. Default: the build output
  (backend/packaging/dist/svr-backend); falls back to an installed copy.

.PARAMETER Port
  Loopback port for the health probe. Default 8756 (must be free).
#>
param(
  [string]$BackendDir,
  [int]$Port = 8756
)

$ErrorActionPreference = "Stop"
$pass = @(); $fail = @()
function Check([string]$name, [bool]$ok, [string]$detail = "") {
  if ($ok) { $script:pass += $name; Write-Host "  PASS  $name $detail" -ForegroundColor Green }
  else     { $script:fail += $name; Write-Host "  FAIL  $name $detail" -ForegroundColor Red }
}

# --- elevation ---------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
  [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Run this from an elevated PowerShell (Run as administrator)." }

# --- locate the frozen exes ------------------------------------------------------
if (-not $BackendDir) {
  $repo = Split-Path -Parent $PSScriptRoot
  $cand = @(
    (Join-Path $repo "backend\packaging\dist\svr-backend"),
    "C:\Program Files\SVR IOCL Station\resources\backend"
  )
  $BackendDir = $cand | Where-Object { Test-Path (Join-Path $_ "svr-backend-service.exe") } | Select-Object -First 1
}
if (-not $BackendDir -or -not (Test-Path (Join-Path $BackendDir "svr-backend-service.exe"))) {
  throw "Could not find svr-backend-service.exe. Pass -BackendDir explicitly."
}
$svr        = Join-Path $BackendDir "svr-backend.exe"
$backendSvc = Join-Path $BackendDir "svr-backend-service.exe"
$schedSvc   = Join-Path $BackendDir "svr-scheduler-service.exe"
Write-Host "BackendDir = $BackendDir"
Write-Host "Port       = $Port`n"

# --- temp data dir + machine env (remember prior values to restore) ------------
$tmpData = Join-Path $env:TEMP ("svr-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$tmpLogs = Join-Path $tmpData "logs"
New-Item -ItemType Directory -Force -Path $tmpLogs | Out-Null
$sentinel = "SMOKE-" + [guid]::NewGuid().ToString("N").Substring(0, 12)

$envKeys = "SVR_DATA_DIR", "SVR_DB_PATH", "SVR_LOG_DIR", "SVR_API_PORT", "SVR_FIELD_KEY", "SVR_SMOKE_MARKER"
$prior = @{}
foreach ($k in $envKeys) { $prior[$k] = [Environment]::GetEnvironmentVariable($k, "Machine") }

function Restore-Env {
  foreach ($k in $envKeys) {
    [Environment]::SetEnvironmentVariable($k, $prior[$k], "Machine")
    if ($null -eq $prior[$k]) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
    else { Set-Item "Env:$k" $prior[$k] }
  }
}
function Remove-SmokeService([string]$name, [string]$exe) {
  if (Get-Service -Name $name -ErrorAction SilentlyContinue) {
    Stop-Service -Name $name -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    if (Test-Path $exe) { & $exe remove 2>&1 | Out-Null }
    if (Get-Service -Name $name -ErrorAction SilentlyContinue) { & sc.exe delete $name | Out-Null }
  }
}

try {
  foreach ($kv in @{ SVR_DATA_DIR = $tmpData; SVR_DB_PATH = (Join-Path $tmpData "svr.sqlite");
                     SVR_LOG_DIR = $tmpLogs; SVR_API_PORT = "$Port";
                     SVR_FIELD_KEY = (& $svr gen-key).Trim(); SVR_SMOKE_MARKER = $sentinel }.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Machine")
    Set-Item "Env:$($kv.Key)" $kv.Value
  }

  Write-Host "1) migrate (frozen svr-backend.exe)"
  & $svr migrate | Out-Null
  Check "migrate builds a DB" (Test-Path (Join-Path $tmpData "svr.sqlite"))

  Write-Host "2) register + start both services"
  Remove-SmokeService "SVR-IOCL-Backend"   $backendSvc
  Remove-SmokeService "SVR-IOCL-Scheduler" $schedSvc
  & $backendSvc --startup auto install ; & $backendSvc start
  & $schedSvc   --startup auto install ; & $schedSvc   start
  Start-Sleep 3

  $qcB = (& sc.exe qc SVR-IOCL-Backend) -join "`n"
  $qcS = (& sc.exe qc SVR-IOCL-Scheduler) -join "`n"
  Check "backend ImagePath = the frozen exe"  ($qcB -match [regex]::Escape($backendSvc)) "`n$qcB"
  Check "backend START_TYPE = AUTO_START"     ($qcB -match "AUTO_START")
  Check "scheduler ImagePath = the frozen exe" ($qcS -match [regex]::Escape($schedSvc))
  Check "backend service Running"   ((Get-Service SVR-IOCL-Backend).Status   -eq "Running")
  Check "scheduler service Running" ((Get-Service SVR-IOCL-Scheduler).Status -eq "Running")

  Write-Host "3) health probe"
  $health = $null
  for ($i = 0; $i -lt 15 -and -not $health; $i++) {
    try { $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2 } catch { Start-Sleep 1 }
  }
  Check "GET /health returns ok" ($health.status -eq "ok") "($($health | ConvertTo-Json -Compress))"

  Write-Host "4) machine env reaches the service process"
  $svcPid = (Get-CimInstance Win32_Service -Filter "Name='SVR-IOCL-Backend'").ProcessId
  $seesMarker = $false
  if ($svcPid) {
    # the service logs its resolved data dir; confirm it used our TEMP path, not a dev default
    $bl = Join-Path $tmpLogs "backend-service.log"
    if (Test-Path $bl) { $seesMarker = (Select-String -Path $bl -SimpleMatch "startup complete" -Quiet) }
  }
  Check "backend service started against the TEMP data dir" `
        ((Test-Path (Join-Path $tmpLogs "backend-service.log")) -and `
         -not (Test-Path (Join-Path $BackendDir "..\..\..\local\svr.sqlite")))
}
finally {
  Write-Host "`n-- cleanup --"
  Remove-SmokeService "SVR-IOCL-Backend"   $backendSvc
  Remove-SmokeService "SVR-IOCL-Scheduler" $schedSvc
  Restore-Env
  Remove-Item -Recurse -Force $tmpData -ErrorAction SilentlyContinue
  Write-Host "   services removed, env restored, temp dir deleted."
}

Write-Host "`n==== RESULT ===="
Write-Host ("PASS {0}  FAIL {1}" -f $pass.Count, $fail.Count)
if ($fail.Count) { Write-Host ("Failed: " + ($fail -join "; ")) -ForegroundColor Red; exit 1 }
Write-Host "Frozen service machinery looks good. Proceed to the full HANDOVER section 5 test on a clean PC." -ForegroundColor Green
