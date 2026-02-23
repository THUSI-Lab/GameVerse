$GAME = "ForzaHorizon5" 
$GAME_LOWER = "forza_horizon5"
$EXPERT_VIDEO = "data/expertvideo/horizon/skill_video.mp4"

# Specify the model, mode and timestamp to facilitate reflection experiments
$target_model = "gpt-4o"  
$action_mode = "gui"
$target_timestamp = "20260118_113128"  

$TARGET_DIR = "logs/ForzaHorizon5/$target_model/$action_mode/zeroshot_agent"
$log_dir = "$TARGET_DIR/$target_timestamp"
$timestamp = "$target_timestamp"

Write-Host "Start processing reflection experiment"
Write-Host "  Model: $target_model"
Write-Host "  Action mode: $action_mode"
Write-Host "  Timestamp: $timestamp"
Write-Host "  Log directory: $log_dir"
Write-Host ""

if (-not (Test-Path "$log_dir")) {
    Write-Error "Error: Directory does not exist: $log_dir"
    exit 1
}

Write-Host "=========================================================="
Write-Host "Processing: $log_dir"

$config_file = Join-Path $log_dir "config.yaml"
if (-not (Test-Path $config_file)) {
    Write-Error "Error: Config file not found: $config_file"
    exit 1
}

# 1. Check and generate obs_video.mp4
$obs_video = Join-Path $log_dir "obs_video.mp4"
if (-not (Test-Path $obs_video)) {
    Write-Host "Generating obs_video.mp4..."
    python scripts/playvideo_gen.py --log_path "$log_dir"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to generate video."
        exit 1
    }
} else {
    Write-Host "obs_video.mp4 exists."
}

# 2. Generate Reflection (Experience)
Write-Host "Generating reflection experience..."
python scripts/generate_reflection.py `
    --config "$config_file" `
    --failure_video_path "$obs_video" `
    --expert_video_path "$EXPERT_VIDEO" `
    --obs_images_dir "$(Join-Path $log_dir 'obs_images')" `
    --log_path "$log_dir"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to generate reflection."
    exit 1
}

# 3. Rename experience file
$default_reflection = "data/reflections/${GAME}_reflections.json"

# Create directory structure
$reflection_dir = "data/reflections/${GAME}/${target_model}/${action_mode}"
if (-not (Test-Path $reflection_dir)) {
    New-Item -ItemType Directory -Force -Path $reflection_dir | Out-Null
}

$specific_reflection = "$reflection_dir/reflection_${timestamp}.json"

if (Test-Path $default_reflection) {
    Move-Item -Path $default_reflection -Destination $specific_reflection -Force
    Write-Host "Reflection saved to: $specific_reflection"
} else {
    Write-Error "Error: Reflection file not found at $default_reflection"
    exit 1
}

# 4. Rerun experiment
Write-Host "Rerunning experiment with reflection..."

python scripts/play_game.py `
    --config "$config_file" `
    agent.use_reflection=true `
    agent.reflection_file_path="$specific_reflection"
    
Write-Host "Rerun finished."
Write-Host "Processing completed for: $log_dir"
