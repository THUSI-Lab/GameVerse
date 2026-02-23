# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

$game = "slay_the_spire"
$model = "gemini-2.5-pro"  # change model here
$agent = "zeroshot_agent"
$action_mode = "gui"  # gui or semantic

# 检测是否使用 qwen3-vl 模型，如果是则启用坐标转换
if ($model -eq "qwen3-vl-8b-instruct" -or $model -eq "qwen3-vl-32b-instruct" -or $model -eq "doubao-seed-1-8-251228") {
    $coor_trans = "true"
} else {
    $coor_trans = "false"
}

python scripts/play_game.py `
    --config="./src/agent_client/configs/$game/config.yaml" `
    env.action_mode="$action_mode" `
    env.coor_trans="$coor_trans" `
    runner.max_steps=200 `
    agent.llm_name="$model" `
    agent.agent_type="$agent" `
    agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"
