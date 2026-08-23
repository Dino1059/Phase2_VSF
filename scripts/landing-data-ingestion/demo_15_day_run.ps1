#Requires -Version 5.1
# demo_15_day_run.ps1 - End-to-end 15-day demo script for DataTrust OS
# Phase 8 (Giai doan 8)
# Usage: .\demo_15_day_run.ps1 [-DryRun] [-SkipWarmup] [-LLM]

param(
    [string]$ApiBase = "http://localhost:8000/api/v1",
    [switch]$SkipWarmup,
    [switch]$DryRun,
    [switch]$LLM
)

$ErrorActionPreference = "Stop"

function Write-Step { param([string]$Msg) Write-Host "[STEP] $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "[OK]   $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "[WARN] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[FAIL] $Msg" -ForegroundColor Red }
function Write-Info { param([string]$Msg) Write-Host "       $Msg" -ForegroundColor Gray }

function Invoke-ApiGet {
    param([string]$Path)
    $url = "$ApiBase$Path"
    try {
        $resp = Invoke-WebRequest -Uri $url -Method GET -ContentType "application/json" -TimeoutSec 15
        return $resp.Content | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Invoke-ApiPost {
    param([string]$Path, [object]$Body)
    $url = "$ApiBase$Path"
    $bodyJson = $Body | ConvertTo-Json -Compress
    try {
        $resp = Invoke-WebRequest -Uri $url -Method POST -ContentType "application/json" -Body $bodyJson -TimeoutSec 30
        return $resp.Content | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Show-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  =========================================================" -ForegroundColor Magenta
    Write-Host "     DataTrust OS - 15-Day Landing Demo Runner" -ForegroundColor Magenta
    Write-Host "  =========================================================" -ForegroundColor Magenta
    Write-Host ""
    if ($DryRun) {
        Write-Warn "DRY RUN MODE - no actual API calls will be made"
    }
    if (-not $LLM) {
        Write-Info "LLM DISABLED - set -LLM to enable LLM in batch analysis"
    } else {
        Write-Info "LLM ENABLED"
    }
    Write-Host ""
}

function Test-Server {
    Write-Step "Checking API server..."
    $health = Invoke-ApiGet -Path "/ingestion/health"
    if ($null -eq $health) {
        Write-Fail "Server not responding. Start: python -m uvicorn src.main:app --reload"
        exit 1
    }
    Write-OK "Server OK - $($health.version)"
}

function Get-CurrentStatus {
    return Invoke-ApiGet -Path "/ingestion/status"
}

function Get-Timeline {
    return Invoke-ApiGet -Path "/ingestion/days"
}

function Show-CurrentState {
    $status = Get-CurrentStatus
    $timeline = Get-Timeline
    Write-Host ""
    Write-Host "-- Current Demo State -------------------------------------------" -ForegroundColor DarkGray
    if ($null -ne $status) {
        Write-Info "current_day_idx  : $($status.current_day_idx)"
        Write-Info "warmup_completed : $($status.warmup_completed)"
        Write-Info "realtime_active  : $($status.realtime_active)"
    }
    if ($null -ne $timeline) {
        $activated = @($timeline.days | Where-Object { $_.is_activated }).Count
        Write-Info "timeline         : $($timeline.total_days) days, $activated activated"
    }
    Write-Host ""
}

function Reset-DemoState {
    Write-Step "Resetting demo state..."
    if ($DryRun) {
        Write-Info "[DryRun] Would POST /ingestion/reset"
        return
    }
    $result = Invoke-ApiPost -Path "/ingestion/reset" -Body @{}
    if ($null -ne $result) {
        Write-OK "Reset complete - phase: $($result.phase)"
    }
}

function Activate-Day {
    param([int]$DayIdx, [string]$RunType)

    Write-Host ""
    Write-Host "-- Day $DayIdx ($RunType) ---------------------------------------" -ForegroundColor Yellow
    if ($DryRun) {
        Write-Info "[DryRun] Would POST /ingestion/days/$DayIdx/activate"
        return
    }
    $body = @{ force_replay = $false }
    $result = Invoke-ApiPost -Path "/ingestion/days/$DayIdx/activate" -Body $body
    if ($null -ne $result) {
        Write-OK "Activated - status: $($result.status), run_id: $($result.ingestion_run_id)"
    } else {
        Write-Fail "Activation failed"
    }
}

function Invoke-Warmup {
    Write-Step "Running warmup (Day 0 triggers WARMUP_10D with 10-day lookback)..."
    if ($DryRun) {
        Write-Info "[DryRun] Would activate day 0 (warmup)"
        return
    }
    Activate-Day -DayIdx 0 -RunType "WARMUP_10D"
}

function Invoke-DemoDays {
    param([int[]]$Days = @(10, 11, 12, 13, 14))

    Write-Step "Activating demo days: $($Days -join ', ')..."
    if ($DryRun) {
        Write-Info "[DryRun] Would activate days: $($Days -join ', ')"
        return
    }
    foreach ($day in $Days) {
        Activate-Day -DayIdx $day -RunType "DAILY_PLUS1"
        Start-Sleep -Seconds 3
        $rt = Invoke-ApiGet -Path "/ingestion/realtime/status"
        if ($null -ne $rt) {
            Write-Info "Realtime: active=$($rt.active), day=$($rt.current_day_idx), ticks=$($rt.tick_count)"
        }
    }
}

function Verify-EndState {
    Write-Step "Verifying end state..."

    $timeline = Get-Timeline
    $runs = Invoke-ApiGet -Path "/ingestion/runs"
    $quarantine = Invoke-ApiGet -Path "/ingestion/quarantine/summary"

    Write-Host ""
    Write-Host "-- Final State ------------------------------------------------" -ForegroundColor DarkGray

    if ($null -ne $timeline) {
        Write-Info "Total days   : $($timeline.total_days)"
        Write-Info "Activated   : $($timeline.activated_days)"
        Write-Host ""
        Write-Host "  Day Timeline:" -ForegroundColor White
        foreach ($day in $timeline.days) {
            $flag = if ($day.is_activated) { "[X]" } else { "[ ]" }
            $ingestFlag = if ($day.is_ingested) { "ingested" } else { "pending" }
            $color = if ($day.is_activated) { "Green" } else { "DarkGray" }
            $rowInfo = if ($day.is_ingested) { "($($day.ingested_rows) rows)" } else { "" }
            Write-Host "    $flag Day $($day.day_idx.ToString().PadLeft(2,'0')) $ingestFlag $rowInfo" -ForegroundColor $color
        }
    }

    Write-Host ""
    if ($null -ne $runs) {
        $warmup = @($runs.runs | Where-Object { $_.run_type -eq "WARMUP_10D" }).Count
        $daily = @($runs.runs | Where-Object { $_.run_type -eq "DAILY_PLUS1" }).Count
        Write-Info "Ingestion runs: WARMUP_10D=$warmup, DAILY_PLUS1=$daily (total=$($runs.total))"
    }

    Write-Host ""
    if ($null -ne $quarantine) {
        $openCount = 0
        foreach ($rule in $quarantine.rules) {
            $openCount += $rule.open_count
        }
        Write-Info "Quarantine open violations: $openCount"
    }

    Write-Host ""
    Write-Host "===============================================================" -ForegroundColor Magenta
    Write-Host "  Demo Complete!" -ForegroundColor Green
    Write-Host "  Open: http://localhost:8000/dashboard/ingestion" -ForegroundColor Cyan
    Write-Host "===============================================================" -ForegroundColor Magenta
}

# MAIN
Show-Banner
Test-Server
Show-CurrentState

$status = Get-CurrentStatus
$alreadyDone = $false
if ($null -ne $status) {
    $alreadyDone = $status.warmup_completed -and ($status.current_day_idx -ge 14)
}

if ($alreadyDone) {
    Write-Warn "Demo already completed (day=$($status.current_day_idx))"
    $confirm = Read-Host "Reset and re-run? (y/N)"
    if ($confirm -ne "y") {
        Write-Info "Aborted."
        exit 0
    }
}

Reset-DemoState

if (-not $SkipWarmup) {
    Invoke-Warmup
} else {
    Write-Warn "Skipping warmup (--SkipWarmup)"
}

Invoke-DemoDays -Days @(10, 11, 12, 13, 14)
Verify-EndState
