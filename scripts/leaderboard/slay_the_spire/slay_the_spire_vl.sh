#!/bin/bash

# 硬编码参数
GAME="SlayTheSpire" 
GAME_LOWER="slay_the_spire"
EXPERT_VIDEO="data/expertvideo/${GAME_LOWER}/skill_video.mp4"

# 指定要处理的模型、模式和时间戳（修改这里来针对不同模型运行反思实验）
target_model="gpt-4o"
action_mode="gui"
target_timestamp="20260113_151845"  # 指定要处理的时间戳

TARGET_DIR="logs/SlayTheSpire/$target_model/$action_mode/zeroshot_agent"
log_dir="$TARGET_DIR/$target_timestamp"
timestamp="$target_timestamp"

echo "Start processing reflection experiment"
echo "  Model: $target_model"
echo "  Action mode: $action_mode"
echo "  Timestamp: $timestamp"
echo "  Log directory: $log_dir"
echo ""

if [ ! -d "$log_dir" ]; then
    echo "Error: Directory does not exist: $log_dir"
    exit 1
fi

echo "=========================================================="
echo "Processing: $log_dir"
echo "  Timestamp: $timestamp"
    
    # 使用和原始实验相同的 config 参数, 仅覆盖需要修改的reflection部分
    config_file="$log_dir/config.yaml"
    
    if [ ! -f "$config_file" ]; then
        echo "Error: Config file not found: $config_file"
        exit 1
    fi

    # 1. 检查并生成 obs_video.mp4
    if [ ! -f "$log_dir/obs_video.mp4" ]; then
        echo "Generating obs_video.mp4..."
        python scripts/playvideo_gen.py --log_path "$log_dir"
        if [ $? -ne 0 ]; then
            echo "Failed to generate video."
            exit 1
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
        --log_path "$log_dir"

    if [ $? -ne 0 ]; then
        echo "Failed to generate reflection."
        exit 1
    fi

    # 3. 重命名经验文件以独立保存，按照游戏和game mode分开
    default_reflection="data/reflections/${GAME}_reflections.json"
    
    # 创建按游戏和模式分类的目录结构
    reflection_dir="data/reflections/${GAME}/${target_model}/${action_mode}"
    mkdir -p "$reflection_dir"
    
    specific_reflection="${reflection_dir}/reflection_${timestamp}.json"
    
    if [ -f "$default_reflection" ]; then
        mv "$default_reflection" "$specific_reflection"
        echo "Reflection saved to: $specific_reflection"
    else
        echo "Error: Reflection file not found at $default_reflection"
        exit 1
    fi

    # 4. 重新运行实验
    echo "Rerunning experiment with reflection..."
    
    # 使用这些参数运行 play_game.py, 仅修改 reflection 相关参数
    python scripts/play_game.py \
        --config "$config_file" \
        agent.use_reflection=true \
        agent.reflection_file_path="$specific_reflection"
        
    echo "Rerun finished."
    echo ""

echo "Processing completed for: $log_dir"
