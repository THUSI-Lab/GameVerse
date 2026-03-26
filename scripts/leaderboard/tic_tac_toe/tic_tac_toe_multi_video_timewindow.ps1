param(
    [string]$Model = "qwen3-vl-8b-instruct",
    [string]$Agent = "zeroshot_agent",
    [string]$ActionMode = "semantic",
    [string]$StartTime = "20260326_150958",
    [string]$EndTime = "20260326_151309",
    [int]$TopK = 5
)

$ErrorActionPreference = "Stop"

$GAME = "TicTacToe"
$GAME_LOWER = "tic_tac_toe"
$EXPERT_VIDEO = ""
$DEFAULT_REFLECTION = "data/reflections/${GAME}_reflections.json"
$RUN_ROOT = "logs/$GAME/$Model/$ActionMode/$Agent"
$REFLECTION_DIR = "data/reflections/${GAME}/multi-video/$Model/$ActionMode"

if (-not (Test-Path $RUN_ROOT)) {
    throw "Run root does not exist: $RUN_ROOT"
}

if (-not (Test-Path $REFLECTION_DIR)) {
    New-Item -ItemType Directory -Force -Path $REFLECTION_DIR | Out-Null
}

$allCandidates = Get-ChildItem -Path $RUN_ROOT -Directory |
    Where-Object { $_.Name -match '^\d{8}_\d{6}$' } |
    Where-Object { $_.Name -ge $StartTime -and $_.Name -le $EndTime } |
    Sort-Object Name -Descending

if ($allCandidates.Count -eq 0) {
    throw "No run directories found in time window [$StartTime, $EndTime] under $RUN_ROOT"
}

$selectedRuns = $allCandidates | Select-Object -First $TopK

Write-Host "Start multi-video reflection experiment"
Write-Host "  Model: $Model"
Write-Host "  Agent: $Agent"
Write-Host "  Action mode: $ActionMode"
Write-Host "  Time window: $StartTime ~ $EndTime"
Write-Host "  Default selected count: $TopK (no program hard limit)"
Write-Host "  Actual selected count: $($selectedRuns.Count)"
Write-Host ""

$failureVideos = @()
$obsImagesDirs = @()

foreach ($run in $selectedRuns) {
    $logDir = $run.FullName
    $obsVideo = Join-Path $logDir "obs_video.mp4"

    if (-not (Test-Path $obsVideo)) {
        Write-Host "Generating obs_video.mp4 for $logDir"
        python scripts/playvideo_gen.py --log_path "$logDir"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to generate obs_video.mp4 for $logDir"
        }
    }

    $obsImagesDir = Join-Path $logDir "obs_images"
    $failureVideos += $obsVideo
    $obsImagesDirs += $obsImagesDir
}

$configFile = Join-Path $selectedRuns[0].FullName "config.yaml"
if (-not (Test-Path $configFile)) {
    throw "Config file not found in selected run: $configFile"
}

if ($failureVideos.Count -eq 0) {
    throw "No failure videos collected for multi-video reflection"
}

$reflectionArgs = @(
    "scripts/generate_reflection.py",
    "--config", $configFile,
    "--log_path", $selectedRuns[0].FullName,
    "--failure_video_paths"
)
$reflectionArgs += $failureVideos

if ($EXPERT_VIDEO -and $EXPERT_VIDEO.Trim() -ne "") {
    $reflectionArgs += @("--expert_video_path", $EXPERT_VIDEO)
} else {
    # Ablation mode: explicitly override config expert video path
    $reflectionArgs += @("--expert_video_path", "none")
}

$reflectionArgs += @("--obs_images_dirs")
$reflectionArgs += $obsImagesDirs

python @reflectionArgs
if ($LASTEXITCODE -ne 0) {
    throw "generate_reflection.py failed for multi-video reflection"
}

if (-not (Test-Path $DEFAULT_REFLECTION)) {
    throw "Default reflection file not found: $DEFAULT_REFLECTION"
}

$rangeTag = "range_${StartTime}_${EndTime}"
$finalReflection = Join-Path $REFLECTION_DIR "${rangeTag}_top${TopK}_reflection.json"
Move-Item -Path $DEFAULT_REFLECTION -Destination $finalReflection -Force

Write-Host "Multi-video reflection saved: $finalReflection"
Write-Host ""
Write-Host "Rerunning one experiment with multi-video reflection..."

$playArgs = @(
    "scripts/play_game.py",
    "--config", "./src/agent_client/configs/tic_tac_toe/config.yaml",
    "env.action_mode=$ActionMode",
    "agent.llm_name=$Model",
    "agent.agent_type=$Agent",
    "agent.prompt_path=agent_servers.$GAME_LOWER.prompts.$ActionMode.$Agent",
    "agent.use_reflection=true",
    "agent.reflection_file_path=$finalReflection"
)

python @playArgs
if ($LASTEXITCODE -ne 0) {
    throw "play_game.py failed during rerun with multi-video reflection"
}

Write-Host ""
Write-Host "Multi-video time-window experiment completed."
