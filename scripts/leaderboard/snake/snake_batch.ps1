$models = @("qwen3-vl-8b-instruct", "gpt-4o", "gemini-2.5-pro")
$action_modes = @("gui")
$game_modes = @("realtime")
$action_timeouts = @("20.0", "40.0")
$num_runs = 4

$game = "snake"
$agent = "zeroshot_agent"

foreach ($model in $models) {
    foreach ($action_mode in $action_modes) {
        foreach ($game_mode in $game_modes) {
            foreach ($action_timeout in $action_timeouts) {
                for ($i = 1; $i -le $num_runs; $i++) {
                    Write-Host "----------------------------------------------------------------"
                    Write-Host "Running Snake (Run $i/$num_runs) with:"
                    Write-Host "  Model: $model"
                    Write-Host "  Action Mode: $action_mode"
                    Write-Host "  Game Mode: $game_mode"
                    Write-Host "  Action Timeout: $action_timeout"
                    
                    python scripts/play_game.py `
                        --config="./src/agent_client/configs/$game/config.yaml" `
                        env.action_mode="$action_mode" `
                        env.game_mode="$game_mode" `
                        env.action_timeout="$action_timeout" `
                        agent.llm_name="$model" `
                        agent.agent_type="$agent" `
                        agent.prompt_path="agent_servers.$game.prompts.$action_mode.$agent"
                }
            }
        }
    }
}
