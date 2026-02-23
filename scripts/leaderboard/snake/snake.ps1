# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

$game="snake"
$model="qwen3-vl-8b-instruct"  # change model here
$agent="zeroshot_agent"
$action_mode="gui" # gui or semantic_action
$game_mode="realtime"    # "discrete" or "realtime"
$action_timeout="20.0"  # Timeout for waiting LLM action in realtime mode (seconds)

python scripts/play_game.py `
    --config="./src/agent_client/configs/$game/config.yaml" `
        env.action_mode="$action_mode" `
        env.game_mode="$game_mode" `
        env.action_timeout="$action_timeout" `
        agent.llm_name="$model" `
        agent.agent_type="$agent" `
        agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"
