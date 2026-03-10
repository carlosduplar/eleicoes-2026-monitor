#!/usr/bin/env pwsh
<#
.SYNOPSIS
    QA conductor for eleicoes-2026-monitor.
    Watches for plans/phase-NN-arch.DONE sentinels and invokes Gemini CLI for QA.
    Run this in a SEPARATE terminal alongside conductor.ps1.

.DESCRIPTION
    Tier 3 of the three-tier agent protocol (docs/agent-protocol.md):

      plans/phase-NN-arch.DONE   <- trigger (written by Operacional/MiniMax)
      qa/phase-NN-report.json    <- Gemini output
      qa/phase-NN-report.DONE    <- completion sentinel

    Gemini reads the phase spec + git diff and runs Playwright tests.
    If QA passes, it writes the report and the .DONE sentinel.
    If QA fails, it writes qa/phase-NN-report.FAIL with findings.

.PARAMETER PollIntervalSeconds
    How often to check for new arch.DONE sentinels. Default: 30.

.PARAMETER MaxPhase
    Stop after this phase number. Default: 17.

.PARAMETER StartPhase
    Skip phases below this number. Default: 2.

.PARAMETER Model
    Gemini model to use. Default: gemini-2.5-flash.

.EXAMPLE
    # Start in a separate terminal while conductor.ps1 is running
    pwsh conductor-qa.ps1

    # Resume from a specific phase
    pwsh conductor-qa.ps1 -StartPhase 7

    # Use a different model
    pwsh conductor-qa.ps1 -Model gemini-2.5-pro
#>

param(
    [int]$PollIntervalSeconds = 30,
    [int]$MaxPhase            = 17,
    [int]$StartPhase          = 2,
    [string]$Model            = "gemini-3-flash-preview"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$PlansDir = Join-Path $RepoRoot "plans"
$QaDir    = Join-Path $RepoRoot "qa"
$LogDir   = Join-Path $RepoRoot ".conductor-logs"

New-Item -ItemType Directory -Path $QaDir   -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir  -Force | Out-Null

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-QA {
    param([string]$Msg, [string]$Color = "White")
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[QA $ts] $Msg" -ForegroundColor $Color
}

function Get-CompletedQA {
    Get-ChildItem -Path $QaDir -Filter "phase-*-report.DONE" -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Name -match 'phase-(\d+)-report\.DONE') { [int]$Matches[1] }
        } |
        Sort-Object
}

function Get-PhasesReadyForQA {
    # Phases that have arch.DONE but not yet qa report.DONE
    $qaCompleted = Get-CompletedQA
    Get-ChildItem -Path $PlansDir -Filter "phase-*-arch.DONE" -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Name -match 'phase-(\d+)-arch\.DONE') {
                $n = [int]$Matches[1]
                if ($n -ge $StartPhase -and $n -le $MaxPhase -and $n -notin $qaCompleted) {
                    $n
                }
            }
        } |
        Sort-Object
}

function Get-PhaseSpec {
    param([int]$Phase)
    $padded   = $Phase.ToString("D2")
    $specFile = Join-Path $PlansDir "phase-$padded-arch.md"
    if (Test-Path $specFile) { return Get-Content $specFile -Raw }
    return ""
}

# ---------------------------------------------------------------------------
# Run Gemini QA for one phase
# ---------------------------------------------------------------------------

function Invoke-QA {
    param([int]$Phase)

    $padded     = $Phase.ToString("D2")
    $reportJson = Join-Path $QaDir "phase-$padded-report.json"
    $reportDone = Join-Path $QaDir "phase-$padded-report.DONE"
    $reportFail = Join-Path $QaDir "phase-$padded-report.FAIL"
    $logFile    = Join-Path $LogDir "phase-$padded-qa-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

    # Get the recent git diff for context
    $gitDiff = & git -C $RepoRoot --no-pager diff HEAD~1 HEAD --stat 2>&1 | Out-String

    $spec    = Get-PhaseSpec -Phase $Phase

    $qaPrompt = @"
You are the QA agent for Portal Eleicoes BR 2026 (Phase $padded).

CONTEXT:
- Repo: $RepoRoot
- Phase spec: plans/phase-$padded-arch.md
- Recent changes (git diff --stat): $gitDiff

SPEC SUMMARY:
$spec

YOUR JOB:
1. Verify every deliverable listed in the phase spec exists and is correct.
2. Run Playwright tests if they exist: npx playwright test --reporter=json
3. Run Python tests if they exist: python -m pytest --tb=short -q
4. Check JSON data files conform to docs/schemas/*.schema.json.
5. Check no console errors on the built site (if applicable).

REPORT: Write qa/phase-$padded-report.json with this exact schema:
{
  "phase": $Phase,
  "model": "$Model",
  "timestamp": "<ISO 8601>",
  "passed": <true|false>,
  "deliverables_checked": [ { "file": "...", "status": "ok|missing|invalid", "note": "..." } ],
  "test_results": { "playwright": "...", "pytest": "..." },
  "issues": [ "..." ],
  "recommendation": "pass|fail|needs-review"
}

COMPLETION:
- If QA passes: New-Item -Path qa/phase-$padded-report.DONE -ItemType File -Force
- If QA fails:  New-Item -Path qa/phase-$padded-report.FAIL -ItemType File -Force
  (Also include details in the issues array of the JSON report.)

RULES:
- Do NOT modify any application code.
- Do NOT commit anything.
- Use PowerShell 7 syntax for all shell commands (Windows 11).
- STOP after writing the report and sentinel.
"@

    Write-QA "Phase $padded — invoking Gemini ($Model)..." "Cyan"

    try {
        # Out-File only — Tee-Object would flood the function's return pipeline,
        # causing $result in the caller to be an array of hundreds of output lines.
        & gemini `
            -m $Model `
            --prompt $qaPrompt `
            2>&1 | Out-File -FilePath $logFile -Encoding UTF8

        Write-QA "Phase $padded — Gemini process exited. Log: $logFile" "DarkGray"
    }
    catch {
        Write-QA "Phase $padded — Gemini invocation error: $_" "Red"
        return "error"
    }

    if (Test-Path $reportDone) {
        Write-QA "Phase $padded — QA PASSED." "Green"
        return "passed"
    }
    if (Test-Path $reportFail) {
        Write-QA "Phase $padded — QA FAILED. See $reportFail" "Red"
        if (Test-Path $reportJson) {
            Write-Host (Get-Content $reportJson -Raw) -ForegroundColor Yellow
        }
        return "failed"
    }

    Write-QA "Phase $padded — no sentinel created; treating as inconclusive." "Yellow"
    return "inconclusive"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host " Portal Eleicoes BR 2026 - QA Conductor" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Repo root     : $RepoRoot"
Write-Host "Model         : $Model  (Gemini)"
Write-Host "Poll interval : ${PollIntervalSeconds}s"
Write-Host "Start phase   : $StartPhase"
Write-Host "Max phase     : $MaxPhase"
Write-Host ""
Write-Host "Watching for plans/phase-NN-arch.DONE sentinels..." -ForegroundColor DarkGray
Write-Host ""

$dots = 0

while ($true) {
    $ready = @(Get-PhasesReadyForQA)

    if ($ready.Count -eq 0) {
        # Check if all phases are QA-complete
        $qaCompleted = @(Get-CompletedQA | Where-Object { $_ -ge $StartPhase -and $_ -le $MaxPhase })
        $allArchDone = @(
            Get-ChildItem -Path $PlansDir -Filter "phase-*-arch.DONE" -ErrorAction SilentlyContinue |
                ForEach-Object {
                    if ($_.Name -match 'phase-(\d+)-arch\.DONE') {
                        $n = [int]$Matches[1]
                        if ($n -ge $StartPhase -and $n -le $MaxPhase) { $n }
                    }
                }
        )
        if ($allArchDone.Count -gt 0 -and $qaCompleted.Count -eq $allArchDone.Count) {
            Write-Host ""
            Write-QA "All phases QA-complete. Exiting." "Green"
            break
        }

        $dots++
        Write-Host "." -NoNewline
        if ($dots % 20 -eq 0) { Write-Host "" -NoNewline }
        Start-Sleep -Seconds $PollIntervalSeconds
        continue
    }

    Write-Host ""
    $dots = 0

    foreach ($phase in $ready) {
        $result = Invoke-QA -Phase $phase
        # Resolve color outside Write-QA to avoid array-to-ConsoleColor binding errors
        $color = switch ([string]$result) {
            "passed" { "Green" }
            "failed" { "Red" }
            default  { "Yellow" }
        }
        Write-QA "Phase $($phase.ToString('D2')) result: $result" $color
        Write-Host ""
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " QA conductor finished."                 -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
