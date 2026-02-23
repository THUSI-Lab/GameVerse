# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

$game="baba_is_you"
$model="gpt-4o-mini"
$agent="zeroshot_agent"
$action_mode="gui" # (gui or semantic)

python scripts/play_game.py `
    --config="./src/agent_client/configs/$game/config.yaml" `
        env.action_mode="$action_mode" `
        agent.llm_name="$model" `
        agent.agent_type="$agent" `
        agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"
