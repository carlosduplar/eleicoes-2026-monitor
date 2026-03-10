#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Multi-agent orchestrator for eleicoes-2026-monitor.
    Monitors .DONE sentinel files and dispatches phases to Copilot/Codex.

.DESCRIPTION
    File-based handoff protocol:
    - Each phase produces a plans/phase-NN-arch.DONE sentinel when complete.
    - conductor.ps1 watches for sentinels and dispatches the next phase.
    - Agents are stateless; all context comes from PLAN.md + plans/*.md + docs/.

    Agent mapping:
    - Phase 0      : manual (Stitch MCP + ADR 000)
    - Phase 1      : manual (Opus/Sonnet — architecture + schemas)
    - Phases 2+    : gpt-5.3-codex via copilot CLI (this script)

    NOTE: --reasoning-effort is not configurable via CLI flags as of March 2026.
    --autopilot + --no-ask-user is the functional equivalent for unattended runs.

.PARAMETER DryRun
    Print what would be dispatched without actually invoking Copilot.

.PARAMETER PollIntervalSeconds
    How often (in seconds) to check for .DONE sentinel files. Default: 30.

.PARAMETER MaxPhase
    Stop after this phase number. Default: 17.

.PARAMETER StartPhase
    Skip phases below this number (useful for resuming mid-run). Default: 2.

.PARAMETER Parallel
    Run phases 2/3/4 in parallel using Start-Job. Default: false (sequential).

.PARAMETER Model
    Copilot model to use for implementation phases. Default: gpt-5.3-codex.

.EXAMPLE
    # Normal run from phase 2 onwards
    pwsh conductor.ps1

    # Resume from phase 6 after an escalation
    pwsh conductor.ps1 -StartPhase 6

    # Dry run to verify task files would be created correctly
    pwsh conductor.ps1 -DryRun

    # Run phases 2/3/4 in parallel, then sequential from 5
    pwsh conductor.ps1 -Parallel

    # Use a different model
    pwsh conductor.ps1 -Model claude-sonnet-4.6
#>

param(
    [switch]$DryRun,
    [int]$PollIntervalSeconds = 30,
    [int]$MaxPhase = 17,
    [int]$StartPhase = 2,
    [switch]$Parallel,
    # Tatico agent: Copilot (writes task specs from arch specs)
    [string]$TacticModel      = "gpt-5.3-codex",
    # Operacional agent: OpenCode/MiniMax (implements from task specs)
    [string]$OperacionalModel = "opencode/minimax-m2.5-free",
    # Backward-compat alias — if set, overrides TacticModel
    [string]$Model            = ""
)

if ($Model -ne "") { $TacticModel = $Model }

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$PlansDir = Join-Path $RepoRoot "plans"
$TasksDir = Join-Path $RepoRoot "tasks"
$LogDir   = Join-Path $RepoRoot ".conductor-logs"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Phase {
    param([string]$Msg, [string]$Color = "White")
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $Msg" -ForegroundColor $Color
}

function Get-CompletedPhases {
    Get-ChildItem -Path $PlansDir -Filter "phase-*-arch.DONE" -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Name -match 'phase-(\d+)-arch\.DONE') { [int]$Matches[1] }
        } |
        Sort-Object
}

function Get-NextPhase {
    param([int]$From = $StartPhase)
    $completed = Get-CompletedPhases
    for ($n = $From; $n -le $MaxPhase; $n++) {
        if ($n -notin $completed) { return $n }
    }
    return -1
}

function Get-PhaseSpec {
    param([int]$Phase)
    $padded   = $Phase.ToString("D2")
    $specFile = Join-Path $PlansDir "phase-$padded-arch.md"
    if (Test-Path $specFile) { return Get-Content $specFile -Raw }
    return $null
}

function Get-EscalationPath {
    param([int]$Phase)
    $padded = $Phase.ToString("D2")
    return Join-Path $TasksDir "phase-$padded" "ESCALATION.md"
}

# ---------------------------------------------------------------------------
# Task + prompt file creation
# ---------------------------------------------------------------------------

function New-TaskFiles {
    param([int]$Phase)

    $padded       = $Phase.ToString("D2")
    $taskDir      = Join-Path $TasksDir "phase-$padded"
    $taskFile     = Join-Path $taskDir  "task.md"
    $promptFile   = Join-Path $taskDir  "prompt.txt"
    $sentinelFile = Join-Path $PlansDir "phase-$padded-arch.DONE"

    New-Item -ItemType Directory -Path $taskDir -Force | Out-Null

    # Human-readable task card
    $taskContent = @"
# Task: Phase $padded

Dispatched by conductor.ps1 at $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
Model: $Model

## Instructions

Read and implement the spec in ``plans/phase-$padded-arch.md``.
Follow all rules in ``.github/copilot-instructions.md`` and ``docs/agent-protocol.md``.

## Completion protocol

When ALL deliverables in the spec are implemented and committed:
1. Run any tests defined in the spec and confirm they pass.
2. Commit all changes: ``git add -A && git commit -m "feat: phase $padded complete"``
3. Create the sentinel: ``New-Item -Path plans/phase-$padded-arch.DONE -ItemType File -Force``
4. STOP — do not proceed to the next phase.

## Escalation protocol

If you encounter the same error more than 3 times in a row:
1. Write ``tasks/phase-$padded/ESCALATION.md`` with:
   - Full error + stack trace
   - Number of attempts
   - Your hypothesis (spec ambiguous? broken dependency? logic bug?)
2. Do NOT retry — stop immediately and wait for human review.

## Context files

- ``PLAN.md``                           master plan
- ``plans/phase-$padded-arch.md``       this phase spec
- ``docs/agent-protocol.md``            handoff protocol
- ``docs/schemas/``                     JSON schemas (do not deviate)
- ``.github/copilot-instructions.md``   project-specific rules
"@

    # Prompt fed directly to copilot -p
    $promptContent = @"
You are implementing Phase $padded of the Portal Eleicoes BR 2026 project.

Your context:
- Project rules: .github/copilot-instructions.md
- Handoff protocol: docs/agent-protocol.md
- This phase spec: plans/phase-$padded-arch.md
- JSON schemas (must not deviate): docs/schemas/

TASK: Implement ALL deliverables listed in plans/phase-$padded-arch.md.

RULES (non-negotiable):
- Do NOT ask for confirmation, input, or clarification at any point.
- Do NOT skip any deliverable listed in the spec.
- Do NOT proceed to Phase $([int]$padded + 1) or any other phase.
- Follow the coding conventions in .github/copilot-instructions.md exactly.
- If tests are defined in the spec, run them and fix all failures before finishing.
- All Python scripts must be idempotent (safe to run twice without duplicating data).
- All shell commands must use PowerShell 7 syntax (Windows 11 environment).

COMPLETION (do this when ALL deliverables are done):
1. git add -A
2. git commit -m "feat: phase $padded complete"
3. New-Item -Path plans/phase-$padded-arch.DONE -ItemType File -Force
4. STOP.

ESCALATION (if same error occurs 3+ times):
1. Write tasks/phase-$padded/ESCALATION.md with the full error, attempt count, and hypothesis.
2. STOP immediately — do not retry.
"@

    Set-Content -Path $taskFile   -Value $taskContent   -Encoding UTF8
    Set-Content -Path $promptFile -Value $promptContent -Encoding UTF8

    return @{
        TaskFile    = $taskFile
        PromptFile  = $promptFile
        Sentinel    = $sentinelFile
        Escalation  = Get-EscalationPath -Phase $Phase
        LogFile     = Join-Path $LogDir "phase-$padded-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    }
}

# ---------------------------------------------------------------------------
# Invoke Copilot for one phase
# ---------------------------------------------------------------------------

function Invoke-Phase {
    param([int]$Phase)

    $padded = $Phase.ToString("D2")
    $spec   = Get-PhaseSpec -Phase $Phase

    if (-not $spec) {
        Write-Phase "Phase $padded — spec not found in plans/. Skipping dispatch." "Yellow"
        return $false
    }

    Write-Phase "Phase $padded — creating task files..." "Cyan"
    $files = New-TaskFiles -Phase $Phase
    Write-Phase "  task   : $($files.TaskFile)"   "DarkGray"
    Write-Phase "  prompt : $($files.PromptFile)" "DarkGray"
    Write-Phase "  log    : $($files.LogFile)"    "DarkGray"

    if ($DryRun) {
        Write-Phase "DRY RUN — would invoke: copilot --model $Model -p <prompt> --yolo --autopilot --no-ask-user" "DarkGray"
        Start-Sleep -Seconds 2
        New-Item -Path $files.Sentinel -ItemType File -Force | Out-Null
        Write-Phase "DRY RUN — created sentinel $($files.Sentinel)" "DarkGray"
        return $true
    }

    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $promptContent = Get-Content $files.PromptFile -Raw

    Write-Phase "Phase $padded — invoking Copilot ($Model)..." "Cyan"

    try {
        # --yolo        = --allow-all-tools --allow-all-paths --allow-all-urls
        # --autopilot   = autonomous continuation without pausing
        # --no-ask-user = disables ask_user tool (no interactive prompts)
        # --add-dir     = explicit repo root access (belt + suspenders with --yolo)
        & copilot `
            --model $Model `
            -p $promptContent `
            --yolo `
            --autopilot `
            --no-ask-user `
            --add-dir $RepoRoot `
            2>&1 | Tee-Object -FilePath $files.LogFile

        Write-Phase "Phase $padded — Copilot process exited." "DarkGray"
    }
    catch {
        Write-Phase "Phase $padded — Copilot invocation error: $_" "Red"
        return $false
    }

    return $true
}

# ---------------------------------------------------------------------------
# Wait for .DONE or ESCALATION
# ---------------------------------------------------------------------------

function Wait-ForPhase {
    param([int]$Phase, [hashtable]$Files)

    $padded  = $Phase.ToString("D2")
    $elapsed = 0
    $timeout = 90 * 60   # 90-minute hard timeout per phase
    $dots    = 0

    Write-Phase "Phase $padded — polling for completion (timeout: 90min)..." "Cyan"

    while ($true) {
        Start-Sleep -Seconds $PollIntervalSeconds
        $elapsed += $PollIntervalSeconds

        if (Test-Path $Files.Sentinel) {
            Write-Host ""
            Write-Phase "Phase $padded — .DONE sentinel detected." "Green"
            return "done"
        }

        if (Test-Path $Files.Escalation) {
            Write-Host ""
            Write-Phase "Phase $padded — ESCALATION.md detected!" "Red"
            Write-Phase "File: $($Files.Escalation)" "Red"
            Write-Host (Get-Content $Files.Escalation -Raw) -ForegroundColor Yellow
            return "escalation"
        }

        if ($elapsed -ge $timeout) {
            Write-Host ""
            Write-Phase "Phase $padded — TIMEOUT after $([int]($timeout/60)) minutes." "Red"
            return "timeout"
        }

        $dots++
        Write-Host "." -NoNewline
        if ($dots % 20 -eq 0) {
            Write-Host " ($([int]($elapsed/60))m elapsed)" -NoNewline
        }
    }
}

# ---------------------------------------------------------------------------
# Parallel dispatch for phases 2, 3, 4
# ---------------------------------------------------------------------------

function Invoke-ParallelPhases {
    param([int[]]$Phases)

    Write-Phase "Parallel dispatch: phases $($Phases -join ', ')" "Cyan"
    $jobs = @()

    foreach ($phase in $Phases) {
        $padded = $phase.ToString("D2")
        if (-not (Get-PhaseSpec -Phase $phase)) {
            Write-Phase "Phase $padded — no spec, skipping parallel slot." "Yellow"
            continue
        }

        $files  = New-TaskFiles -Phase $phase
        $logFile = $files.LogFile
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

        Write-Phase "Phase $padded — launching background job..." "Cyan"

        $job = Start-Job -ScriptBlock {
            param($repoRoot, $model, $promptFile, $logFile, $dryRun)
            Set-Location $repoRoot
            $prompt = Get-Content $promptFile -Raw
            if ($dryRun) {
                Start-Sleep -Seconds 5
            } else {
                & copilot `
                    --model $model `
                    -p $prompt `
                    --yolo `
                    --autopilot `
                    --no-ask-user `
                    --add-dir $repoRoot `
                    2>&1 | Out-File $logFile -Encoding UTF8
            }
        } -ArgumentList $RepoRoot, $Model, $files.PromptFile, $logFile, $DryRun.IsPresent

        $jobs += @{
            Phase     = $phase
            Job       = $job
            Sentinel  = $files.Sentinel
            Escalation = $files.Escalation
        }
    }

    Write-Phase "Waiting for parallel phases..." "Cyan"
    $pending = [System.Collections.Generic.List[hashtable]]$jobs

    while ($pending.Count -gt 0) {
        Start-Sleep -Seconds $PollIntervalSeconds
        Write-Host "." -NoNewline

        $stillPending = [System.Collections.Generic.List[hashtable]]@()

        foreach ($entry in $pending) {
            $padded = $entry.Phase.ToString("D2")

            if (Test-Path $entry.Sentinel) {
                Write-Host ""
                Write-Phase "Phase $padded — DONE." "Green"
                Remove-Job -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if (Test-Path $entry.Escalation) {
                Write-Host ""
                Write-Phase "Phase $padded — ESCALATION!" "Red"
                Remove-Job -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if ($entry.Job.State -in @("Failed", "Stopped")) {
                Write-Host ""
                Write-Phase "Phase $padded — background job $($entry.Job.State)." "Red"
                Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue | Write-Host
                Remove-Job -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }

            $stillPending.Add($entry)
        }

        $pending = $stillPending
    }

    Write-Host ""
    Write-Phase "Parallel phases complete." "Green"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

function Start-Conductor {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " Portal Eleicoes BR 2026 - Conductor"   -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Repo root     : $RepoRoot"
    Write-Host "Model         : $Model"
    Write-Host "Poll interval : ${PollIntervalSeconds}s"
    Write-Host "Start phase   : $StartPhase"
    Write-Host "Max phase     : $MaxPhase"
    Write-Host "Parallel      : $Parallel"
    Write-Host "Dry run       : $DryRun"
    Write-Host ""

    $completed = Get-CompletedPhases
    if ($completed) {
        Write-Phase "Completed phases: $($completed -join ', ')" "Green"
    } else {
        Write-Phase "No phases completed yet." "Yellow"
    }
    Write-Host ""

    # Optional parallel fast-start for phases 2/3/4
    if ($Parallel) {
        $parallelCandidates = @(2, 3, 4) | Where-Object {
            $_ -ge $StartPhase -and
            $_ -notin (Get-CompletedPhases) -and
            (Get-PhaseSpec -Phase $_) -ne $null
        }
        if ($parallelCandidates.Count -gt 1) {
            Invoke-ParallelPhases -Phases $parallelCandidates
        }
    }

    # Sequential main loop
    while ($true) {
        $next = Get-NextPhase -From $StartPhase

        if ($next -eq -1) {
            Write-Phase "All phases up to $MaxPhase complete." "Green"
            break
        }

        $padded     = $next.ToString("D2")
        $sentinel   = Join-Path $PlansDir "phase-$padded-arch.DONE"
        $escalation = Get-EscalationPath -Phase $next

        # Already done (e.g. from a parallel run)
        if (Test-Path $sentinel) {
            Write-Phase "Phase $padded — already done, skipping." "DarkGray"
            continue
        }

        # Spec not yet written — wait for Opus/Sonnet to deliver it
        if (-not (Get-PhaseSpec -Phase $next)) {
            Write-Phase "Phase $padded — waiting for plans/phase-$padded-arch.md..." "Yellow"
            Start-Sleep -Seconds $PollIntervalSeconds
            continue
        }

        # Dispatch
        $dispatched = Invoke-Phase -Phase $next
        if (-not $dispatched) {
            Start-Sleep -Seconds $PollIntervalSeconds
            continue
        }

        # Poll
        $files  = @{ Sentinel = $sentinel; Escalation = $escalation }
        $result = Wait-ForPhase -Phase $next -Files $files

        switch ($result) {
            "done" {
                Write-Phase "Phase $padded complete. Advancing..." "Green"
                Write-Host ""
            }
            "escalation" {
                Write-Phase "Conductor paused — escalation at phase $padded." "Red"
                Write-Phase "Fix tasks/phase-$padded/ESCALATION.md, then resume:" "Yellow"
                Write-Phase "  pwsh conductor.ps1 -StartPhase $next" "Yellow"
                exit 1
            }
            "timeout" {
                Write-Phase "Timeout at phase $padded. Check logs: $LogDir" "Red"
                Write-Phase "To resume: pwsh conductor.ps1 -StartPhase $next" "Yellow"
                exit 1
            }
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " All phases complete."                   -ForegroundColor Green
    Write-Host " Portal Eleicoes BR 2026 is ready."     -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}

Start-Conductor