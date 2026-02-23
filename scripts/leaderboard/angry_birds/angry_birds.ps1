# llms: gpt-4o, gpt-4o-mini, gemini-2.5-pro, gemini-2.5-flash, qwen3-vl-8b-instruct, qwen3-vl-32b-instruct, doubao-seed-1-8-251228

# 1. 定义变量 (对应 .sh 文件里的设置)
$game = "angry_birds"
$model = "qwen3-vl-32b-instruct"
$agent = "zeroshot_agent"
$action_mode = "gui" # gui or semantic

# 2. 运行 Python (PowerShell 支持这种多行写法，注意行尾是反引号 ` )
# 注意：OmegaConf 要求参数不带 -- 前缀（除了 --config）
python scripts/play_game.py `
  --config="./src/agent_client/configs/$game/config.yaml" `
  env.action_mode="$action_mode" `
  agent.llm_name="$model" `
  agent.agent_type="$agent" `
  agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"