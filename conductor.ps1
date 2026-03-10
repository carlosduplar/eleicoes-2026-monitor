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

    $padded           = $Phase.ToString("D2")
    $taskDir          = Join-Path $TasksDir "phase-$padded"
    $taskFile         = Join-Path $taskDir  "task.md"
    $tacticPromptFile = Join-Path $taskDir  "tactic-prompt.txt"
    $opPromptFile     = Join-Path $taskDir  "operacional-prompt.txt"
    $taskSpecFile     = Join-Path $taskDir  "task-01-spec.md"
    $taskSpecDone     = Join-Path $taskDir  "task-01-spec.DONE"
    $archDone         = Join-Path $PlansDir "phase-$padded-arch.DONE"

    New-Item -ItemType Directory -Path $taskDir -Force | Out-Null

    # Human-readable task card
    $taskContent = @"
# Task: Phase $padded

Dispatched by conductor.ps1 at $(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
Tatico model      : $TacticModel
Operacional model : $OperacionalModel

## Agent roles

- Tatico (Copilot $TacticModel): reads plans/phase-$padded-arch.md, writes tasks/phase-$padded/task-01-spec.md
- Operacional (OpenCode $OperacionalModel): reads task-01-spec.md, implements deliverables, commits, pushes

## Escalation protocol

If the same error occurs 3+ times, write tasks/phase-$padded/ESCALATION.md and stop.
"@

    # --- Tatico prompt (Copilot): produce a task spec, do NOT implement ---
    $tacticPrompt = @"
You are the TATICO agent for Portal Eleicoes BR 2026 (Phase $padded).

YOUR ONLY JOB: Read the architecture spec and write a detailed implementation task spec.
DO NOT write any application code. DO NOT implement any deliverable.

INPUT: plans/phase-$padded-arch.md

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

    # --- Operacional prompt (OpenCode/MiniMax): implement from task spec ---
    $operacionalPrompt = @"
You are the OPERACIONAL agent for Portal Eleicoes BR 2026 (Phase $padded).

YOUR JOB: Implement EVERYTHING in the attached task spec using a RALPH loop.
  Run tests -> Assert pass -> Loop on failure (max 3 attempts) -> Push on pass -> Halt on 3x failure

ATTACHED SPEC: tasks/phase-$padded/task-01-spec.md

RULES (non-negotiable):
- Do NOT skip any deliverable in the spec.
- Do NOT proceed to any other phase.
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

    Set-Content -Path $taskFile         -Value $taskContent       -Encoding UTF8
    Set-Content -Path $tacticPromptFile -Value $tacticPrompt      -Encoding UTF8
    Set-Content -Path $opPromptFile     -Value $operacionalPrompt -Encoding UTF8

    return @{
        TaskFile         = $taskFile
        TacticPromptFile = $tacticPromptFile
        OpPromptFile     = $opPromptFile
        TaskSpecFile     = $taskSpecFile
        TaskSpecDone     = $taskSpecDone
        Sentinel         = $archDone
        Escalation       = Get-EscalationPath -Phase $Phase
        LogFile          = Join-Path $LogDir "phase-$padded-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    }
}

# ---------------------------------------------------------------------------
# Tier 1: Tatico — Copilot writes task-01-spec.md (no implementation)
# ---------------------------------------------------------------------------

function Invoke-Tactic {
    param([int]$Phase, [hashtable]$Files)

    $padded = $Phase.ToString("D2")

    if ($DryRun) {
        Write-Phase "DRY RUN — Tatico: would invoke copilot --model $TacticModel" "DarkGray"
        New-Item -Path $Files.TaskSpecDone -ItemType File -Force | Out-Null
        return $true
    }

    $prompt = Get-Content $Files.TacticPromptFile -Raw
    Write-Phase "Phase $padded — Tatico ($TacticModel): writing task spec..." "Cyan"

    try {
        & copilot `
            --model $TacticModel `
            -p $prompt `
            --yolo `
            --autopilot `
            --no-ask-user `
            --add-dir $RepoRoot `
            2>&1 | Tee-Object -FilePath ($Files.LogFile -replace '\.log$', '-tactic.log')

        Write-Phase "Phase $padded — Tatico process exited." "DarkGray"
    }
    catch {
        Write-Phase "Phase $padded — Tatico invocation error: $_" "Red"
        return $false
    }

    return $true
}

# ---------------------------------------------------------------------------
# Wait for task-01-spec.DONE (Tatico output sentinel)
# ---------------------------------------------------------------------------

function Wait-ForTaskSpec {
    param([int]$Phase, [hashtable]$Files)

    $padded  = $Phase.ToString("D2")
    $elapsed = 0
    $timeout = 30 * 60  # 30-minute timeout for spec writing
    $dots    = 0

    Write-Phase "Phase $padded — waiting for task spec (timeout: 30min)..." "Cyan"

    while ($true) {
        Start-Sleep -Seconds $PollIntervalSeconds
        $elapsed += $PollIntervalSeconds

        if (Test-Path $Files.TaskSpecDone) {
            Write-Host ""
            Write-Phase "Phase $padded — task-01-spec.DONE detected." "Green"
            return $true
        }

        if (Test-Path $Files.Escalation) {
            Write-Host ""
            Write-Phase "Phase $padded — ESCALATION during Tatico phase!" "Red"
            Write-Host (Get-Content $Files.Escalation -Raw) -ForegroundColor Yellow
            return $false
        }

        if ($elapsed -ge $timeout) {
            Write-Host ""
            Write-Phase "Phase $padded — TIMEOUT waiting for task spec." "Red"
            return $false
        }

        $dots++
        Write-Host "." -NoNewline
        if ($dots % 20 -eq 0) {
            Write-Host " ($([int]($elapsed/60))m)" -NoNewline
        }
    }
}

# ---------------------------------------------------------------------------
# Tier 2: Operacional — OpenCode/MiniMax implements from task spec
# ---------------------------------------------------------------------------

function Invoke-Operacional {
    param([int]$Phase, [hashtable]$Files)

    $padded = $Phase.ToString("D2")

    if ($DryRun) {
        Write-Phase "DRY RUN — Operacional: would invoke opencode -m $OperacionalModel --prompt <prompt>" "DarkGray"
        Start-Sleep -Seconds 2
        New-Item -Path $Files.Sentinel -ItemType File -Force | Out-Null
        Write-Phase "DRY RUN — created sentinel $($Files.Sentinel)" "DarkGray"
        return $true
    }

    # Embed the task spec path in the prompt so opencode reads it
    $basePrompt   = Get-Content $Files.OpPromptFile -Raw
    $specContent  = if (Test-Path $Files.TaskSpecFile) {
        Get-Content $Files.TaskSpecFile -Raw
    } else {
        "Task spec not found — fall back to plans/phase-$padded-arch.md"
    }
    $fullPrompt   = "$basePrompt`n`n--- TASK SPEC ---`n$specContent"

    Write-Phase "Phase $padded — Operacional ($OperacionalModel): implementing..." "Cyan"

    # Run opencode from the repo root so relative paths resolve correctly
    Push-Location $RepoRoot
    try {
        & opencode `
            -m $OperacionalModel `
            --prompt $fullPrompt `
            2>&1 | Tee-Object -FilePath ($Files.LogFile -replace '\.log$', '-operacional.log')

        Write-Phase "Phase $padded — Operacional process exited." "DarkGray"
    }
    catch {
        Write-Phase "Phase $padded — Operacional invocation error: $_" "Red"
        return $false
    }
    finally {
        Pop-Location
    }

    return $true
}

# ---------------------------------------------------------------------------
# Invoke-Phase: orchestrates Tatico -> Wait -> Operacional for one phase
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
    Write-Phase "  tactic prompt : $($files.TacticPromptFile)" "DarkGray"
    Write-Phase "  op prompt     : $($files.OpPromptFile)"     "DarkGray"
    Write-Phase "  log dir       : $LogDir"                    "DarkGray"

    # --- Tier 1: Tatico ---
    $tacticOk = Invoke-Tactic -Phase $Phase -Files $files
    if (-not $tacticOk) { return $false }

    # If task spec was already present (e.g., manually written), skip wait
    if (-not (Test-Path $files.TaskSpecDone)) {
        $specReady = Wait-ForTaskSpec -Phase $Phase -Files $files
        if (-not $specReady) {
            Write-Phase "Phase $padded — task spec not ready; aborting Operacional dispatch." "Red"
            return $false
        }
    }

    # --- Tier 2: Operacional ---
    $opOk = Invoke-Operacional -Phase $Phase -Files $files
    return $opOk
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
# Each phase runs in its own sub-conductor process to get the full three-tier flow.
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

        Write-Phase "Phase $padded — launching sub-conductor..." "Cyan"

        $conductorScript = Join-Path $PSScriptRoot "conductor.ps1"
        $job = Start-Job -ScriptBlock {
            param($script, $phase, $dryRun, $tacticModel, $opModel, $pollInterval)
            $args = @(
                "-StartPhase", $phase,
                "-MaxPhase",   $phase,
                "-TacticModel", $tacticModel,
                "-OperacionalModel", $opModel,
                "-PollIntervalSeconds", $pollInterval
            )
            if ($dryRun) { $args += "-DryRun" }
            & pwsh -NonInteractive -File $script @args 2>&1
        } -ArgumentList $conductorScript, $phase, $DryRun.IsPresent, $TacticModel, $OperacionalModel, $PollIntervalSeconds

        $sentinel  = Join-Path $PlansDir "$padded-arch.DONE" # checked via Get-CompletedPhases
        $sentinel  = Join-Path $PlansDir "phase-$padded-arch.DONE"
        $jobs += @{
            Phase      = $phase
            Job        = $job
            Sentinel   = $sentinel
            Escalation = Get-EscalationPath -Phase $phase
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
                Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue | Out-Null
                Remove-Job  -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if (Test-Path $entry.Escalation) {
                Write-Host ""
                Write-Phase "Phase $padded — ESCALATION!" "Red"
                Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue | Out-Null
                Remove-Job  -Job $entry.Job -Force -ErrorAction SilentlyContinue
                continue
            }
            if ($entry.Job.State -in @("Failed", "Stopped")) {
                Write-Host ""
                Write-Phase "Phase $padded — background job $($entry.Job.State)." "Red"
                Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue | Write-Host
                Remove-Job  -Job $entry.Job -Force -ErrorAction SilentlyContinue
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
    Write-Host "Repo root         : $RepoRoot"
    Write-Host "Tatico model      : $TacticModel  (Copilot)"
    Write-Host "Operacional model : $OperacionalModel  (OpenCode)"
    Write-Host "Poll interval     : ${PollIntervalSeconds}s"
    Write-Host "Start phase       : $StartPhase"
    Write-Host "Max phase         : $MaxPhase"
    Write-Host "Parallel          : $Parallel"
    Write-Host "Dry run           : $DryRun"
    Write-Host ""
    Write-Host "QA tier (Gemini): start conductor-qa.ps1 in a separate terminal." -ForegroundColor DarkGray
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