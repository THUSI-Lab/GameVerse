# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

game="metro"
model="qwen3-vl-32b-instruct"
agent="zeroshot_agent"
action_mode="gui" # (gui or semantic)

# 测试不用边缘检测辅助 归一化后能否正常运行
if [[ "$model" == "qwen3-vl-8b-instruct" || "$model" == "qwen3-vl-32b-instruct" || "$model" == "doubao-seed-1-8-251228" ]]; then
    coor_trans="true"
    enable_contour_detection="false"
else
    coor_trans="false"
    enable_contour_detection="true"
fi

python scripts/play_game.py \
    --config="./src/agent_client/configs/$game/config.yaml" \
        env.action_mode="$action_mode" \
        env.coor_trans="$coor_trans" \
        agent.llm_name="$model" \
        agent.agent_type="$agent" \
        agent.prompt_path=agent_servers."$game".prompts."$action_mode"."$agent"