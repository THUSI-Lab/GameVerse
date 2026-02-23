#!/bin/bash

# 硬编码参数
GAME="Snake"
GAME_LOWER="snake" # 用于 prompt path 拼接
EXPERT_VIDEO="data/expertvideo/snake/playthrough_video.mp4"

# 为每个模型定义时间戳范围
# 格式: "模型名称:开始时间:结束时间"
declare -A MODEL_TIME_RANGES=(
    ["gpt-4o"]="20260112_165000:20260112_185900"
    ["gpt-4o-mini"]="20260112_150000:20260112_185900"
    ["gemini-2.5-pro"]="20251230_120000:20251230_125900"
    ["gemini-2.5-flash"]="20251230_120000:20251230_125900"
    ["qwen3-vl-32b-instruct"]="20251230_130000:20251230_135900"
    ["qwen3-vl-8b-instruct"]="20251230_130000:20251230_135900"
    ["doubao-seed-1-8-251228"]="20260112_160000:20260112_185900"
)

echo "Start scanning logs for $GAME with model-specific time ranges..."

# 遍历 logs 目录下的所有时间戳文件夹
# 假设目录结构: logs/Snake/Model/ActionMode/AgentType/Timestamp
find logs/$GAME -type d -name "20*" | while read log_dir; do
    timestamp=$(basename "$log_dir")
    
    echo "=========================================================="
    echo "Processing: $log_dir"
    
    # 解析路径参数
    # 路径示例: logs/Snake/gemini-2.5-pro/gui/zeroshot_agent/20251230_123853
    # 使用 IFS 切分
    IFS='/' read -r -a parts <<< "$log_dir"
    # parts[0]=logs, parts[1]=Snake, parts[2]=model, parts[3]=action_mode, parts[4]=agent_type, parts[5]=timestamp
    
    model="${parts[2]}"
    action_mode="${parts[3]}"
    agent_type="${parts[4]}"
    
    # 获取该模型的时间戳范围
    if [ -z "${MODEL_TIME_RANGES[$model]}" ]; then
        echo "No time range defined for model: $model, skipping."
        continue
    fi
    
    IFS=':' read -r START_TIME END_TIME <<< "${MODEL_TIME_RANGES[$model]}"
    
    # 检查时间戳是否在该模型的范围内
    if [[ "$timestamp" < "$START_TIME" || "$timestamp" > "$END_TIME" ]]; then
        echo "Timestamp $timestamp outside range for model $model ($START_TIME to $END_TIME), skipping."
        continue
    fi
    
    echo "  Model: $model (Time range: $START_TIME to $END_TIME)"
    echo "  Timestamp: $timestamp"
    
    # 使用和原始实验相同的 config 参数, 仅覆盖需要修改的reflection部分
    config_file="$log_dir/config.yaml"
    
    if [ ! -f "$config_file" ]; then
        echo "Config file not found in $log_dir, skipping."
        continue
    fi

    # 跳过 semantic action_mode
    if [ "$action_mode" = "semantic" ]; then
        echo "Skipping semantic action_mode experiment: $log_dir"
        echo ""
        continue
    fi

    # 检查游戏模式，跳过 realtime 模式
    game_mode=$(grep -A 1 "game_mode:" "$config_file" | grep -oP '(realtime|discrete)' | head -1)
    
    if [ -z "$game_mode" ]; then
        echo "Warning: Could not detect game_mode from config, assuming discrete mode."
        game_mode="discrete"
    fi
    
    if [ "$game_mode" = "realtime" ]; then
        echo "Skipping realtime mode experiment: $log_dir"
        echo ""
        continue
    fi

    echo "  Model: $model"
    echo "  Action Mode: $action_mode"
    echo "  Agent Type: $agent_type"
    echo "  Game Mode: $game_mode"

    # 1. 检查并生成 obs_video.mp4
    if [ ! -f "$log_dir/obs_video.mp4" ]; then
        echo "Generating obs_video.mp4..."
        python scripts/playvideo_gen.py --log_path "$log_dir"
        if [ $? -ne 0 ]; then
            echo "Failed to generate video, skipping."
            continue
        fi
    else
        echo "obs_video.mp4 exists."
    fi

    # 2. 生成经验 (Reflection)
    # 使用当前model自己生成经验
    # generate_reflection.py 默认会覆盖 data/reflections/Snake_reflections.json
    echo "Generating reflection experience..."
    python scripts/generate_reflection.py \
        --config "$config_file" \
        --failure_video_path "$log_dir/obs_video.mp4" \
        --expert_video_path "$EXPERT_VIDEO" \
        --obs_images_dir "$log_dir/obs_images" \
        --log_path "$log_dir" \

    if [ $? -ne 0 ]; then
        echo "Failed to generate reflection, skipping."
        continue
    fi

    # 3. 重命名经验文件以独立保存
    default_reflection="data/reflections/${GAME}_reflections.json"
    # 创建按游戏和模式分类的目录结构
    reflection_dir="data/reflections/${GAME}/${action_mode}"
    mkdir -p "$reflection_dir"
    
    specific_reflection="${reflection_dir}/${GAME}/${action_mode}/reflection_${timestamp}.json"
    
    if [ -f "$default_reflection" ]; then
        mv "$default_reflection" "$specific_reflection"
        echo "Reflection saved to: $specific_reflection"
    else
        echo "Error: Reflection file not found at $default_reflection"
        continue
    fi

    # 4. 重新运行实验
    echo "Rerunning experiment with reflection..."
    
    # 构造 prompt_path
    prompt_path="agent_servers.${GAME_LOWER}.prompts.${action_mode}.${agent_type}"

    # 使用这些参数运行 play_game.py, 仅修改 reflection 相关参数
    python scripts/play_game.py \
        --config "$config_file" \
        agent.use_reflection=true \
        agent.reflection_file_path="$specific_reflection"
        
    echo "Rerun finished."
    echo ""
    
done

echo "Batch processing completed."
