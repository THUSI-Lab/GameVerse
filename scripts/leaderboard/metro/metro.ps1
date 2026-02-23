# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

$game="metro"
$model="qwen3-vl-32b-instruct"
$agent="zeroshot_agent"
$action_mode="gui" # (gui or semantic)

# Test whether it can run normally after coordinate transformation normalization without edge detection assistance
if ($model -eq "qwen3-vl-8b-instruct" -or $model -eq "qwen3-vl-32b-instruct" -or $model -eq "doubao-seed-1-8-251228") {
    $coor_trans="true"
    $enable_contour_detection="false"
} else {
    $coor_trans="false"
    $enable_contour_detection="true"
}

python scripts/play_game.py `
    --config="./src/agent_client/configs/$game/config.yaml" `
        env.action_mode="$action_mode" `
        env.coor_trans="$coor_trans" `
        agent.llm_name="$model" `
        agent.agent_type="$agent" `
        agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"
