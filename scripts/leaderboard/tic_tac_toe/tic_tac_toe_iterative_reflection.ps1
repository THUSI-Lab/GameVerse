param(
    [string]$Model = "qwen3-vl-32b-instruct",
    [string]$Agent = "zeroshot_agent",
    [string]$ActionMode = "semantic",
    [int]$Iterations = 5
)

$ErrorActionPreference = "Stop"

$GAME = "TicTacToe"
$GAME_LOWER = "tic_tac_toe"
$CONFIG_PATH = "./src/agent_client/configs/tic_tac_toe/config.yaml"
$EXPERT_VIDEO = ""
$DEFAULT_REFLECTION = "data/reflections/${GAME}_reflections.json"
$REFLECTION_ROOT = "data/reflections/${GAME}/iterative/$Model/$ActionMode"
$RUN_ROOT = "logs/$GAME/$Model/$ActionMode/$Agent"

function Get-LatestRunDir {
    param([string]$RunRoot)

    if (-not (Test-Path $RunRoot)) {
        return $null
    }

    $dirs = Get-ChildItem -Path $RunRoot -Directory |
        Where-Object { $_.Name -match '^\d{8}_\d{6}$' } |
        Sort-Object Name -Descending

    if ($dirs.Count -eq 0) {
        return $null
    }

    return $dirs[0].FullName
}

function Invoke-GameRun {
    param(
        [string]$ReflectionFilePath
    )

    $playArgs = @(
        "scripts/play_game.py",
        "--config", $CONFIG_PATH,
        "env.action_mode=$ActionMode",
        "agent.llm_name=$Model",
        "agent.agent_type=$Agent",
        "agent.prompt_path=agent_servers.$GAME_LOWER.prompts.$ActionMode.$Agent"
    )

    if ($ReflectionFilePath) {
        $playArgs += @(
            "agent.use_reflection=true",
            "agent.reflection_file_path=$ReflectionFilePath"
        )
    }

    # Send python output directly to host, avoid polluting function return value
    python @playArgs | Out-Host
    $playExitCode = $LASTEXITCODE
    if ($playExitCode -ne 0) {
        throw "play_game.py failed with exit code $playExitCode"
    }

    Start-Sleep -Seconds 1
    $latest = Get-LatestRunDir -RunRoot $RUN_ROOT
    if (-not $latest) {
        throw "Unable to locate latest run directory under $RUN_ROOT"
    }

    return $latest
}

function Invoke-SingleVideoReflection {
    param(
        [string]$LogDir,
        [string]$OutputReflectionPath
    )

    $obsVideo = Join-Path $LogDir "obs_video.mp4"
    if (-not (Test-Path $obsVideo)) {
        python scripts/playvideo_gen.py --log_path "$LogDir"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to generate obs_video.mp4 for $LogDir"
        }
    }

    $obsImagesDir = Join-Path $LogDir "obs_images"
    $configFile = Join-Path $LogDir "config.yaml"

    $reflectionArgs = @(
        "scripts/generate_reflection.py",
        "--config", $configFile,
        "--failure_video_path", $obsVideo,
        "--obs_images_dir", $obsImagesDir,
        "--log_path", $LogDir
    )

    if ($EXPERT_VIDEO -and $EXPERT_VIDEO.Trim() -ne "") {
        $reflectionArgs += @("--expert_video_path", $EXPERT_VIDEO)
    } else {
        # Ablation mode: explicitly override config expert video path
        $reflectionArgs += @("--expert_video_path", "none")
    }

    python @reflectionArgs

    if ($LASTEXITCODE -ne 0) {
        throw "generate_reflection.py failed for $LogDir"
    }

    if (-not (Test-Path $DEFAULT_REFLECTION)) {
        throw "Default reflection file not found: $DEFAULT_REFLECTION"
    }

    $parentDir = Split-Path -Parent $OutputReflectionPath
    if (-not (Test-Path $parentDir)) {
        New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
    }

    Move-Item -Path $DEFAULT_REFLECTION -Destination $OutputReflectionPath -Force
}

if (-not (Test-Path $REFLECTION_ROOT)) {
    New-Item -ItemType Directory -Force -Path $REFLECTION_ROOT | Out-Null
}

Write-Host "Start iterative reflection experiment"
Write-Host "  Model: $Model"
Write-Host "  Agent: $Agent"
Write-Host "  Action mode: $ActionMode"
Write-Host "  Iterations: $Iterations"
Write-Host ""

$currentReflectionForNextIter = $null

for ($iter = 1; $iter -le $Iterations; $iter++) {
    $iterLabel = "iter_{0:D3}" -f $iter

    Write-Host "=========================================================="
    Write-Host "[$iterLabel] Step 1: Run once"
    $run1LogDir = Invoke-GameRun -ReflectionFilePath $currentReflectionForNextIter
    Write-Host "[$iterLabel] Run1 log: $run1LogDir"

    $run1Reflection = Join-Path $REFLECTION_ROOT "${iterLabel}_run1_reflection.json"
    Write-Host "[$iterLabel] Step 2: Reflect run1 failure video"
    Invoke-SingleVideoReflection -LogDir $run1LogDir -OutputReflectionPath $run1Reflection
    Write-Host "[$iterLabel] Run1 reflection: $run1Reflection"

    Write-Host "[$iterLabel] Step 3: Rerun with run1 reflection"
    $run2LogDir = Invoke-GameRun -ReflectionFilePath $run1Reflection
    Write-Host "[$iterLabel] Run2 log: $run2LogDir"

    $run2Reflection = Join-Path $REFLECTION_ROOT "${iterLabel}_run2_reflection.json"
    Write-Host "[$iterLabel] Step 4: Reflect run2 failure video (single video)"
    Invoke-SingleVideoReflection -LogDir $run2LogDir -OutputReflectionPath $run2Reflection
    Write-Host "[$iterLabel] Run2 reflection: $run2Reflection"

    # Next iteration starts from run2 reflection
    $currentReflectionForNextIter = $run2Reflection
}

Write-Host ""
Write-Host "Iterative reflection experiment completed."
Write-Host "Reflection outputs: $REFLECTION_ROOT"
