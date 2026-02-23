# Snake Game for GeneralGameBench

This directory contains the implementation of Snake game integrated with the GeneralGameBench framework, adapted from the realtimegym implementation.

## Game Overview

Snake is a classic arcade game where the player controls a snake that moves around a grid, eating food to grow longer while avoiding walls, obstacles, and its own body.

## Features

- **Classic Snake Gameplay**: Control a snake using directional commands (L, R, U, D)
- **Food System**: Positive food (+1) grows the snake, negative food shrinks it
- **Food Lifespan**: Food disappears after a certain number of turns if not eaten
- **Obstacles**: Configurable obstacles on the board
- **Multiple Input Modalities**: Support for text, image, and text+image inputs
- **Visual Representation**: Automatic board image generation for visual analysis
- **Strategic Prompts**: AI-optimized prompts for gameplay

## File Structure

```
snake/
├── config.yaml                    # Game server configuration
├── game/
│   ├── __init__.py                # Module initialization
│   ├── snake_game.py              # Core game logic (adapted from realtimegym)
│   └── snake_env.py               # GeneralGameBench environment wrapper
└── README.md                      # This file
```

## Game Configuration

The game can be configured through `config.yaml`:

```yaml
env:
  task: "Control the snake to eat food and avoid obstacles"
  input_modality: "text"           # "text", "image", or "text_image"
  board_size: 8                    # Size of the game board (default: 8x8)
  num_obstacles: 0                 # Number of obstacles on the board
  seed: 42                         # Random seed for reproducibility
  show_graphic: false              # Enable/disable graphical display
  max_turns: 100                   # Maximum number of turns before game ends
  step_interval: 0.0              # Time interval between steps (seconds). Use to control game speed and study model performance under different delays.
```

### Speed Control

The game supports a simple speed control parameter:

- **`step_interval`** (float, default: 0.0):
  - Time interval in seconds between game steps
  - Applied after each step execution, before returning the observation
  - Useful for controlling game speed and studying model performance under different latency conditions
  - Example values:
    - `0.0`: No delay (real-time)
    - `0.5`: 500ms delay between steps
    - `1.0`: 1 second delay between steps
    - `2.0`: 2 seconds delay between steps

## Usage

### Running with GeneralGameBench

```bash
python scripts/play_game.py --config src/agent_client/configs/snake/config.yaml
```

### Direct Game Usage

```python
from game_servers.snake.game.snake_game import SnakeGame

# Create a new game
game = SnakeGame(board_size=8, seed=42, num_obstacles=0)
game.reset()

# Make moves
reward, terminal = game.step("R")  # Move right
reward, terminal = game.step("U")  # Move up
reward, terminal = game.step("L")  # Move left

# Check game state
print(game.state_string())
print(f"Score: {game.reward}")
print(f"Game over: {game.terminal}")
```

### Using the Environment

```python
from game_servers.snake.game.snake_env import SnakeEnv, SnakeAction
from omegaconf import OmegaConf

# Create configuration
cfg = OmegaConf.create({
    'task': 'Play Snake',
    'log_path': './logs',
    'input_modality': 'text',
    'board_size': 8,
    'num_obstacles': 0,
    'seed': 42,
    'show_graphic': False,
    'max_turns': 100
})

# Initialize environment
env = SnakeEnv(cfg)
env.configure()

# Get initial observation
obs = env.initial_obs()

# Take actions
action = SnakeAction(actions=['R'])
obs, reward, terminated, truncated, info = env.step(action)
```

## Action Format

Actions are specified using directional commands:
- **L**: Move left
- **R**: Move right
- **U**: Move up
- **D**: Move down

**Important**: You cannot reverse direction immediately. If moving left, you cannot immediately move right (and vice versa). Same for up/down.

## Game Rules

1. The snake moves one cell per turn in the current direction
2. The snake grows longer when it eats positive food (+)
3. The snake shrinks when it eats negative food (-)
4. Food has a lifespan and disappears after a certain number of turns
5. The game ends (you lose) if:
   - The snake hits a wall (border of the board)
   - The snake hits its own body
   - The snake hits an obstacle
   - The snake eats negative food when its head is at the tail position
6. The game also ends after 100 turns (you win if you survive)

## Grid Representation

The grid is displayed as a text representation where:
- `#` represents walls or obstacles
- Letters (a, b, c, ...) represent the snake body, with the head being the last letter in the alphabet
- `+` followed by a number represents positive food with remaining lifespan
- `-` followed by a number represents negative food with remaining lifespan
- `.` represents empty cells

## Integration with GeneralGameBench

The Snake implementation follows GeneralGameBench conventions:

1. **BaseEnv Interface**: Implements all required methods (`initial_obs`, `step`, `obs2text`, `text2action`, etc.)
2. **Observation/Action Classes**: Structured data classes for game state and actions
3. **Configuration System**: YAML-based configuration compatible with the framework
4. **Logging Support**: Integrated logging and step-by-step game recording
5. **Multi-modal Support**: Text and image-based observations

## Strategic Guidelines

The AI agent is provided with strategic guidelines:

1. **Prioritize survival** - Avoid walls, obstacles, and your own body at all costs
2. **Plan your path** - Look ahead to avoid trapping yourself
3. **Eat positive food** when safe to do so to increase your score and length
4. **Avoid negative food** unless necessary, as it shrinks your snake
5. **Consider food lifespan** - Prioritize food that will disappear soon
6. **Avoid tight spaces** - Don't move into areas where you might get trapped
7. **Use the full board** - Don't restrict yourself to a small area
8. **Watch your tail** - Remember where your tail will be after moving

## Dependencies

- Python 3.7+
- PIL (Pillow) for image generation
- gymnasium (for BaseEnv interface)
- numpy for game logic
- Other GeneralGameBench dependencies

## Source

This implementation is adapted from the realtimegym Snake environment:
- Original game logic from `RealtimeGym/src/realtimegym/environments/snake.py`
- Adapted to follow GeneralGameBench conventions and structure
- Integrated with the BaseEnv interface and configuration system

## Testing

The implementation has been tested for:
- ✅ Game logic correctness
- ✅ Environment interface compliance
- ✅ Configuration system integration
- ✅ Prompt system compatibility
- ✅ Image generation functionality

