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
    - Phase 1      : manual (Opus — architecture + schemas)
    - Phases 2+    : two Copilot invocations per phase (this script):
                     1. Planner  (claude-opus-4.6)          — writes task spec
                     2. Implementor (gpt-5.3-codex, xhigh) — implements from spec

    NOTE: --autopilot + --no-ask-user is the functional equivalent of
    unattended/yolo mode for the Copilot CLI.

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

.PARAMETER PlannerModel
    Copilot model for the planning step (writes task spec). Default: claude-opus-4.6.

.PARAMETER Model
    Copilot model for the implementation step. Default: gpt-5.3-codex.

.PARAMETER Variant
    Model variant (reasoning effort) for the implementation step. Default: xhigh.

.EXAMPLE
    # Normal run from phase 2 onwards
    pwsh conductor.ps1

    # Resume from phase 6 after an escalation
    pwsh conductor.ps1 -StartPhase 6

    # Dry run to verify task files would be created correctly
    pwsh conductor.ps1 -DryRun

    # Run phases 2/3/4 in parallel, then sequential from 5
    pwsh conductor.ps1 -Parallel
#>

param(
    [switch]$DryRun,
    [int]$PollIntervalSeconds = 30,
    [int]$MaxPhase = 17,
    [int]$StartPhase = 2,
    [switch]$Parallel,
    [string]$PlannerModel = "claude-opus-4.6",
    [string]$Model        = "gpt-5.3-codex",
    [string]$Variant      = "xhigh"
)

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

    $padded          = $Phase.ToString("D2")
    $taskDir         = Join-Path $TasksDir "phase-$padded"
    $taskFile        = Join-Path $taskDir  "task.md"
    $plannerPrompt   = Join-Path $taskDir  "planner-prompt.txt"
    $implPrompt      = Join-Path $taskDir  "impl-prompt.txt"
    $taskSpecFile    = Join-Path $taskDir  "task-01-spec.md"
    $taskSpecDone    = Join-Path $taskDir  "task-01-spec.DONE"
    $sentinelFile    = Join-Path $PlansDir "phase-$padded-arch.DONE"

    New-Item -ItemType Directory -Path $taskDir -Force | Out-Null

    $taskContent = @"
# Task: Phase $padded

Dispatched by conductor.ps1 at $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
Planner     : $PlannerModel
Implementor : $Model (variant: $Variant)

## Agent roles

- Planner  ($PlannerModel)         : reads plans/phase-$padded-arch.md, writes tasks/phase-$padded/task-01-spec.md
- Implementor ($Model / $Variant)  : reads task-01-spec.md, implements deliverables, commits, pushes

## Escalation protocol

If the same error occurs 3+ times, write tasks/phase-$padded/ESCALATION.md and stop.
"@

    # Planner prompt: Opus reads the arch spec, writes the task spec — no code
    $plannerContent = @"
You are the PLANNER for Portal Eleicoes BR 2026 (Phase $padded).

YOUR ONLY JOB: Read the architecture spec and write a detailed implementation task spec.
DO NOT write any application code. DO NOT implement any deliverable.

INPUT:  plans/phase-$padded-arch.md

OUTPUT: tasks/phase-$padded/task-01-spec.md

The task-01-spec.md MUST contain:
1. All files to create or modify (exact relative paths)
2. Function signatures and TypeScript types / Python type hints for each file
3. Data contract notes: which docs/schemas/*.schema.json fields each file must satisfy
4. Step-by-step implementation order (dependency-aware)
5. Exact shell commands to run tests and verify correctness (PowerShell 7 syntax)
6. The git commit message to use (follow Conventional Commits, include Co-authored-by trailer)
7. The exact PowerShell command to create the completion sentinel:
   New-Item -Path plans/phase-$padded-arch.DONE -ItemType File -Force

RULES:
- Do NOT ask for confirmation or clarification.
- Do NOT write any code beyond the task spec document itself.
- Follow docs/agent-protocol.md section "Tatico responsibilities" exactly.
- Reference .github/copilot-instructions.md for project conventions.

COMPLETION (do this as the very last action):
  New-Item -Path tasks/phase-$padded/task-01-spec.DONE -ItemType File -Force
  STOP — do not proceed to implementation.
"@

    # Implementor prompt: Codex reads the task spec, implements, commits
    $implContent = @"
You are the IMPLEMENTOR for Portal Eleicoes BR 2026 (Phase $padded).

YOUR JOB: Implement EVERYTHING in the attached task spec using a RALPH loop.
  Run tests -> Assert pass -> Loop on failure (max 3 attempts) -> Push on pass -> Halt on 3x failure

TASK SPEC: tasks/phase-$padded/task-01-spec.md

RULES (non-negotiable):
- Do NOT skip any deliverable in the spec.
- Do NOT proceed to any other phase.
- Do NOT ask for confirmation, input, or clarification at any point.
- All Python scripts must be idempotent (safe to run twice without duplicating data).
- All shell commands must use PowerShell 7 syntax (Windows 11).
- Follow .github/copilot-instructions.md coding conventions exactly.
- Validate JSON output against docs/schemas/*.schema.json before committing.

COMPLETION (do this when ALL deliverables pass tests):
1. git add -A
2. git commit -m "<commit message from spec>"
3. git push
4. New-Item -Path plans/phase-$padded-arch.DONE -ItemType File -Force
5. STOP.

ESCALATION (if same error occurs 3+ times):
1. Write tasks/phase-$padded/ESCALATION.md with: error text, attempt count, hypothesis.
2. STOP immediately — do not retry.
"@

    Set-Content -Path $taskFile      -Value $taskContent    -Encoding UTF8
    Set-Content -Path $plannerPrompt -Value $plannerContent -Encoding UTF8
    Set-Content -Path $implPrompt    -Value $implContent    -Encoding UTF8

    return @{
        TaskFile      = $taskFile
        PlannerPrompt = $plannerPrompt
        ImplPrompt    = $implPrompt
        TaskSpecFile  = $taskSpecFile
        TaskSpecDone  = $taskSpecDone
        Sentinel      = $sentinelFile
        Escalation    = Get-EscalationPath -Phase $Phase
        LogFile       = Join-Path $LogDir "phase-$padded-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    }
}

# ---------------------------------------------------------------------------
# Invoke Copilot for one phase (Planner -> spec -> Implementor)
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
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $files = New-TaskFiles -Phase $Phase
    Write-Phase "  planner prompt : $($files.PlannerPrompt)" "DarkGray"
    Write-Phase "  impl prompt    : $($files.ImplPrompt)"    "DarkGray"
    Write-Phase "  log dir        : $LogDir"                 "DarkGray"

    if ($DryRun) {
        Write-Phase "DRY RUN — planner  : copilot --model $PlannerModel -p <prompt> --yolo --autopilot --no-ask-user" "DarkGray"
        Write-Phase "DRY RUN — impl     : copilot --model $Model --variant $Variant -p <prompt> --yolo --autopilot --no-ask-user" "DarkGray"
        Start-Sleep -Seconds 2
        New-Item -Path $files.Sentinel -ItemType File -Force | Out-Null
        Write-Phase "DRY RUN — created sentinel $($files.Sentinel)" "DarkGray"
        return $true
    }

    # --- Step 1: Planner (Opus) writes task-01-spec.md ---
    # Skip if spec was already written (e.g., manually or from a previous run)
    if (-not (Test-Path $files.TaskSpecDone)) {
        $plannerText = Get-Content $files.PlannerPrompt -Raw
        Write-Phase "Phase $padded — Planner ($PlannerModel): writing task spec..." "Cyan"
        try {
            & copilot `
                --model $PlannerModel `
                -p $plannerText `
                --yolo `
                --autopilot `
                --no-ask-user `
                --add-dir $RepoRoot `
                2>&1 | Tee-Object -FilePath ($files.LogFile -replace '\.log$', '-planner.log')
            Write-Phase "Phase $padded — Planner process exited." "DarkGray"
        }
        catch {
            Write-Phase "Phase $padded — Planner invocation error: $_" "Red"
            return $false
        }

        # Wait up to 30 min for the spec sentinel
        $elapsed = 0; $timeout = 30 * 60; $dots = 0
        Write-Phase "Phase $padded — waiting for task-01-spec.DONE (timeout: 30min)..." "Cyan"
        while (-not (Test-Path $files.TaskSpecDone)) {
            if (Test-Path $files.Escalation) {
                Write-Host ""
                Write-Phase "Phase $padded — ESCALATION during planner step!" "Red"
                Write-Host (Get-Content $files.Escalation -Raw) -ForegroundColor Yellow
                return $false
            }
            if ($elapsed -ge $timeout) {
                Write-Host ""
                Write-Phase "Phase $padded — TIMEOUT waiting for task spec." "Red"
                return $false
            }
            Start-Sleep -Seconds $PollIntervalSeconds
            $elapsed += $PollIntervalSeconds
            $dots++; Write-Host "." -NoNewline
            if ($dots % 20 -eq 0) { Write-Host " ($([int]($elapsed/60))m)" -NoNewline }
        }
        Write-Host ""
        Write-Phase "Phase $padded — task-01-spec.DONE detected." "Green"
    } else {
        Write-Phase "Phase $padded — task-01-spec.DONE already present, skipping planner." "DarkGray"
    }

    # --- Step 2: Implementor (Codex xhigh) implements from task spec ---
    $implText = Get-Content $files.ImplPrompt -Raw
    $specText = if (Test-Path $files.TaskSpecFile) {
        Get-Content $files.TaskSpecFile -Raw
    } else {
        "Task spec not found — fall back to plans/phase-$padded-arch.md"
    }
    $fullImpl = "$implText`n`n--- TASK SPEC ---`n$specText"

    Write-Phase "Phase $padded — Implementor ($Model / $Variant): implementing..." "Cyan"
    try {
        & copilot `
            --model $Model `
            --variant $Variant `
            -p $fullImpl `
            --yolo `
            --autopilot `
            --no-ask-user `
            --add-dir $RepoRoot `
            2>&1 | Tee-Object -FilePath ($files.LogFile -replace '\.log$', '-impl.log')
        Write-Phase "Phase $padded — Implementor process exited." "DarkGray"
    }
    catch {
        Write-Phase "Phase $padded — Implementor invocation error: $_" "Red"
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

    Write-Phase "Phase $padded ÔÇö polling for completion (timeout: 90min)..." "Cyan"

    while ($true) {
        Start-Sleep -Seconds $PollIntervalSeconds
        $elapsed += $PollIntervalSeconds

        if (Test-Path $Files.Sentinel) {
            Write-Host ""
            Write-Phase "Phase $padded ÔÇö .DONE sentinel detected." "Green"
            return "done"
        }

        if (Test-Path $Files.Escalation) {
            Write-Host ""
            Write-Phase "Phase $padded ÔÇö ESCALATION.md detected!" "Red"
            Write-Phase "File: $($Files.Escalation)" "Red"
            Write-Host (Get-Content $Files.Escalation -Raw) -ForegroundColor Yellow
            return "escalation"
        }

        if ($elapsed -ge $timeout) {
            Write-Host ""
            Write-Phase "Phase $padded ÔÇö TIMEOUT after $([int]($timeout/60)) minutes." "Red"
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
            Write-Phase "Phase $padded ÔÇö no spec, skipping parallel slot." "Yellow"
            continue
        }

        $files  = New-TaskFiles -Phase $phase
        $logFile = $files.LogFile
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

        Write-Phase "Phase $padded ÔÇö launching background job..." "Cyan"

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
                Write-Phase "Phase $padded ÔÇö DONE." "Green"
                Remove-Job -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if (Test-Path $entry.Escalation) {
                Write-Host ""
                Write-Phase "Phase $padded ÔÇö ESCALATION!" "Red"
                Remove-Job -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if ($entry.Job.State -in @("Failed", "Stopped")) {
                Write-Host ""
                Write-Phase "Phase $padded ÔÇö background job $($entry.Job.State)." "Red"
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
            Write-Phase "Phase $padded ÔÇö already done, skipping." "DarkGray"
            continue
        }

        # Spec not yet written ÔÇö wait for Opus/Sonnet to deliver it
        if (-not (Get-PhaseSpec -Phase $next)) {
            Write-Phase "Phase $padded ÔÇö waiting for plans/phase-$padded-arch.md..." "Yellow"
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
                Write-Phase "Conductor paused ÔÇö escalation at phase $padded." "Red"
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
