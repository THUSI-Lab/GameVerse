#!/bin/bash

# Define the lists of parameters to iterate over
# You can add or remove items from these arrays to customize your batch run.

models=("qwen3-vl-8b-instruct" "gpt-4o" "gemini-2.5-pro")

# Action modes: "semantic" or "gui"
action_modes=("gui")

# Game modes: "discrete" or "realtime"
game_modes=("realtime")

# Timeout for waiting LLM action in realtime mode (seconds)
action_timeouts=("20.0" "40.0")

# Number of times to repeat each experiment
num_runs=4

game="snake"
agent="zeroshot_agent"

# Iterate over each combination
for model in "${models[@]}"; do
    for action_mode in "${action_modes[@]}"; do
        for game_mode in "${game_modes[@]}"; do
            for action_timeout in "${action_timeouts[@]}"; do
                for ((i=1; i<=num_runs; i++)); do
                    echo "----------------------------------------------------------------"
                    echo "Running Snake (Run $i/$num_runs) with:"
                    echo "  Model: $model"
                    echo "  Action Mode: $action_mode"
                    echo "  Game Mode: $game_mode"
                    echo "  Action Timeout: $action_timeout seconds"
                    echo "----------------------------------------------------------------"

                    # Construct the prompt path based on action mode
                    # Assuming the directory structure follows agent_servers.snake.prompts.<action_mode>.<agent>
                    prompt_path="agent_servers.${game}.prompts.${action_mode}.${agent}"

                    python scripts/play_game.py \
                        --config="./src/agent_client/configs/$game/config.yaml" \
                            env.action_mode="$action_mode" \
                            env.game_mode="$game_mode" \
                            env.action_timeout="$action_timeout" \
                            agent.llm_name="$model" \
                            agent.agent_type="$agent" \
                            agent.prompt_path="$prompt_path"
                    
                    echo "Finished run $i/$num_runs for $model - $action_mode - $game_mode - timeout $action_timeout"
                    echo ""
                    
                    # Optional: Add a small delay between runs to let resources settle
                    sleep 2 
                done
            done
        done
    done
done
