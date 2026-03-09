#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Multi-agent orchestrator for eleicoes-2026-monitor.
    Monitors .DONE sentinel files and dispatches phases to Codex agents.

.DESCRIPTION
    File-based handoff protocol:
    - Each phase produces a plans/phase-NN-arch.DONE sentinel when complete.
    - conductor.ps1 watches for sentinels and launches the next phase.
    - Agents are stateless; all context comes from PLAN.md + plans/*.md + docs/.

.NOTES
    Requires PowerShell 7+.
    Run from repo root: pwsh conductor.ps1
#>

param(
    [switch]$DryRun,
    [int]$PollIntervalSeconds = 30,
    [int]$MaxPhase = 17
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$PlansDir = Join-Path $RepoRoot "plans"
$TasksDir = Join-Path $RepoRoot "tasks"

function Get-CompletedPhases {
    Get-ChildItem -Path $PlansDir -Filter "phase-*-arch.DONE" -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Name -match 'phase-(\d+)-arch\.DONE') {
                [int]$Matches[1]
            }
        } |
        Sort-Object
}

function Get-NextPhase {
    $completed = Get-CompletedPhases
    if (-not $completed) { return 1 }
    $last = $completed | Select-Object -Last 1
    $next = $last + 1
    if ($next -gt $MaxPhase) { return -1 }
    return $next
}

function Get-PhaseSpec {
    param([int]$Phase)
    $padded = $Phase.ToString("D2")
    $specFile = Join-Path $PlansDir "phase-$padded-arch.md"
    if (Test-Path $specFile) {
        return Get-Content $specFile -Raw
    }
    return $null
}

function Invoke-Phase {
    param([int]$Phase)

    $padded = $Phase.ToString("D2")
    $spec = Get-PhaseSpec -Phase $Phase

    if (-not $spec) {
        Write-Host "[conductor] No spec found for phase $padded. Skipping." -ForegroundColor Yellow
        return $false
    }

    Write-Host "[conductor] Dispatching phase $padded..." -ForegroundColor Cyan

    if ($DryRun) {
        Write-Host "[conductor] DRY RUN: Would dispatch phase $padded" -ForegroundColor DarkGray
        return $true
    }

    # Create task file for the agent to pick up
    $taskFile = Join-Path $TasksDir "phase-$padded.task.md"
    $taskContent = @"
# Task: Phase $padded

Dispatched by conductor.ps1 at $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")

## Instructions

Read and implement the spec in ``plans/phase-$padded-arch.md``.

When complete:
1. Commit all changes with message: "feat: phase $padded - [description]"
2. Create the sentinel file: ``plans/phase-$padded-arch.DONE``

## Context Files

- PLAN.md (master plan)
- plans/phase-$padded-arch.md (this phase's spec)
- docs/agent-protocol.md (handoff protocol)
- .github/copilot-instructions.md (project rules)
"@

    New-Item -ItemType Directory -Path $TasksDir -Force | Out-Null
    Set-Content -Path $taskFile -Value $taskContent -Encoding UTF8
    Write-Host "[conductor] Task file created: $taskFile" -ForegroundColor Green
    return $true
}

function Start-Conductor {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " Portal Eleicoes BR 2026 - Conductor" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Repo root:     $RepoRoot"
    Write-Host "Plans dir:     $PlansDir"
    Write-Host "Poll interval: ${PollIntervalSeconds}s"
    Write-Host "Max phase:     $MaxPhase"
    Write-Host "Dry run:       $DryRun"
    Write-Host ""

    $completed = Get-CompletedPhases
    if ($completed) {
        Write-Host "[conductor] Completed phases: $($completed -join ', ')" -ForegroundColor Green
    }
    else {
        Write-Host "[conductor] No phases completed yet." -ForegroundColor Yellow
    }

    while ($true) {
        $next = Get-NextPhase
        if ($next -eq -1) {
            Write-Host "[conductor] All $MaxPhase phases completed." -ForegroundColor Green
            break
        }

        $padded = $next.ToString("D2")
        $sentinel = Join-Path $PlansDir "phase-$padded-arch.DONE"

        if (Test-Path $sentinel) {
            Write-Host "[conductor] Phase $padded already done." -ForegroundColor DarkGray
            continue
        }

        # Check if there's a spec for this phase
        $spec = Get-PhaseSpec -Phase $next
        if (-not $spec) {
            Write-Host "[conductor] Waiting for phase $padded spec..." -ForegroundColor Yellow
            Start-Sleep -Seconds $PollIntervalSeconds
            continue
        }

        # Check if task was already dispatched
        $taskFile = Join-Path $TasksDir "phase-$padded.task.md"
        if (Test-Path $taskFile) {
            Write-Host "[conductor] Phase $padded dispatched, waiting for .DONE sentinel..." -ForegroundColor DarkGray
            Start-Sleep -Seconds $PollIntervalSeconds
            continue
        }

        $dispatched = Invoke-Phase -Phase $next
        if (-not $dispatched) {
            Start-Sleep -Seconds $PollIntervalSeconds
            continue
        }

        # Wait for completion
        Write-Host "[conductor] Waiting for phase $padded to complete..." -ForegroundColor Cyan
        while (-not (Test-Path $sentinel)) {
            Start-Sleep -Seconds $PollIntervalSeconds
        }
        Write-Host "[conductor] Phase $padded completed." -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "All phases complete. Portal Eleicoes BR 2026 is ready." -ForegroundColor Green
}

# Entry point
Start-Conductor
