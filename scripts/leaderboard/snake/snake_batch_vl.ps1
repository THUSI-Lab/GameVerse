$GAME = "Snake"
$GAME_LOWER = "snake"
$EXPERT_VIDEO = "data/expertvideo/snake/playthrough_video.mp4"

$MODEL_TIME_RANGES = @{
    "gpt-4o" = "20260112_165000:20260112_185900"
    "gpt-4o-mini" = "20260112_150000:20260112_185900"
    "gemini-2.5-pro" = "20251230_120000:20251230_125900"
    "gemini-2.5-flash" = "20251230_120000:20251230_125900"
    "qwen3-vl-32b-instruct" = "20251230_130000:20251230_135900"
    "qwen3-vl-8b-instruct" = "20251230_130000:20251230_135900"
    "doubao-seed-1-8-251228" = "20260112_160000:20260112_185900"
}

Write-Host "Start scanning logs for $GAME with model-specific time ranges..."

# Find all directories starting with "20"
$log_dirs = Get-ChildItem -Path "logs/$GAME" -Recurse -Directory -Filter "20*"

foreach ($log_dir_item in $log_dirs) {
    if ($log_dir_item.Name -notmatch "^\d{8}_\d{6}$") { continue }
    
    $log_dir = $log_dir_item.FullName
    $timestamp = $log_dir_item.Name
    
    # Path: logs/Snake/Model/ActionMode/AgentType/Timestamp
    $agent_type_dir = $log_dir_item.Parent
    $action_mode_dir = $agent_type_dir.Parent
    $model_dir = $action_mode_dir.Parent
    
    if ($model_dir.Parent.Name -ne $GAME) {
        # continue
    }

    $model = $model_dir.Name
    $action_mode = $action_mode_dir.Name
    $agent_type = $agent_type_dir.Name
    
    if (-not $MODEL_TIME_RANGES.ContainsKey($model)) {
        continue
    }
    
    $range = $MODEL_TIME_RANGES[$model]
    $START_TIME = $range.Split(":")[0]
    $END_TIME = $range.Split(":")[1]
    
    if ($timestamp -lt $START_TIME -or $timestamp -gt $END_TIME) {
        continue
    }
    
    Write-Host "=========================================================="
    Write-Host "Processing: $log_dir"
    Write-Host "  Model: $model (Time range: $START_TIME to $END_TIME)"
    Write-Host "  Timestamp: $timestamp"
    
    $config_file = Join-Path $log_dir "config.yaml"
    if (-not (Test-Path $config_file)) {
        Write-Host "Config file not found in $log_dir, skipping."
        continue
    }
    
    if ($action_mode -eq "semantic") {
        Write-Host "Skipping semantic action_mode experiment: $log_dir"
        continue
    }
    
    # Check game mode
    $content = Get-Content $config_file -Raw
    $game_mode = "discrete" # Default
    if ($content -match "game_mode:\s*[`"']?(realtime|discrete)[`"']?") {
        $game_mode = $matches[1]
    }
    
    if ($game_mode -eq "realtime") {
        Write-Host "Skipping realtime mode experiment: $log_dir"
        continue
    }
    
    Write-Host "  Model: $model"
    Write-Host "  Action Mode: $action_mode"
    Write-Host "  Agent Type: $agent_type"
    Write-Host "  Game Mode: $game_mode"
    
    # 1. Check/Generate obs_video.mp4
    $obs_video = Join-Path $log_dir "obs_video.mp4"
    if (-not (Test-Path $obs_video)) {
        Write-Host "Generating obs_video.mp4..."
        python scripts/playvideo_gen.py --log_path "$log_dir"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to generate video, skipping."
            continue
        }
    } else {
        Write-Host "obs_video.mp4 exists."
    }
    
    # 2. Generate Reflection
    Write-Host "Generating reflection experience..."
    python scripts/generate_reflection.py `
        --config "$config_file" `
        --failure_video_path "$obs_video" `
        --expert_video_path "$EXPERT_VIDEO" `
        --obs_images_dir "$(Join-Path $log_dir 'obs_images')" `
        --log_path "$log_dir"
        
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to generate reflection, skipping."
        continue
    }
    
    # 3. Rename and move reflection
    $default_reflection = "data/reflections/${GAME}_reflections.json"
    $reflection_dir = "data/reflections/${GAME}/${action_mode}"
    
    if (-not (Test-Path $reflection_dir)) {
        New-Item -ItemType Directory -Force -Path $reflection_dir | Out-Null
    }
    
    $specific_reflection = "$reflection_dir/reflection_${timestamp}.json"
    
    if (Test-Path $default_reflection) {
        Move-Item -Path $default_reflection -Destination $specific_reflection -Force
        Write-Host "Reflection saved to: $specific_reflection"
    } else {
        Write-Error "Error: Reflection file not found at $default_reflection"
        continue
    }
    
    # 4. Rerun experiment
    Write-Host "Rerunning experiment with reflection..."
    
    python scripts/play_game.py `
        --config "$config_file" `
        agent.use_reflection=true `
        agent.reflection_file_path="$specific_reflection"
        
    Write-Host "Rerun finished."
    Write-Host ""
}

Write-Host "Batch processing completed."
