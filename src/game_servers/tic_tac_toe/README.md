# Tic Tac Toe Game for GeneralGameBench

This directory contains the implementation of Tic Tac Toe game integrated with the GeneralGameBench framework.

## Game Overview

Tic Tac Toe is a classic strategy game played on a 3×3 grid where players take turns placing their marks (X or O) with the goal of getting three marks in a row horizontally, vertically, or diagonally.

## Features

- **Strategic AI Opponents**: Choose between Minimax AI (optimal play) or Random AI
- **Flexible Player Configuration**: Play as X (first player) or O (second player)
- **Multiple Input Modalities**: Support for text, image, and text+image inputs
- **Real-time UI Display**: Live graphical interface showing game progress (similar to demo)
- **Comprehensive Observation Space**: Detailed game state including board, valid moves, and game status
- **Strategic Prompts**: AI-optimized prompts for strategic gameplay
- **Image Generation**: Automatic board image generation for visual analysis

## File Structure

```
tic_tac_toe/
├── config.yaml                    # Game server configuration
├── game/
│   ├── __init__.py                # Module initialization
│   ├── tic_tac_toe_game.py       # Core game logic and AI opponents
│   ├── tic_tac_toe_env.py        # GeneralGameBench environment wrapper
│   └── tic_tac_toe_ui.py         # UI implementation with real-time display
└── README.md                      # This file
```

## Game Configuration

The game can be configured through `config.yaml`:

```yaml
env:
  task: "Play Tic Tac Toe and try to win"
  input_modality: "text"           # "text", "image", or "text_image"
  ai_opponent: "minimax"           # "minimax", "random", or "none"
  player_mark: "X"                 # "X" (first player) or "O" (second player)
  show_graphic: true               # Enable/disable real-time UI display
```

## Usage

### Running with GeneralGameBench

```bash
python scripts/play_game.py --config src/agent_client/configs/tic_tac_toe/config.yaml
```

### Direct Game Usage

```python
from game_servers.tic_tac_toe.game import TicTacToeGame, MinimaxAI

# Create a new game
game = TicTacToeGame()

# Create AI opponent
ai = MinimaxAI(bot='O', opponent='X')

# Make moves
game.make_move_2d(0, 0, 'X')  # Player moves to A1
ai_move = ai.find_best_move(game)  # AI calculates best move
if ai_move is not None:
    game.make_move(ai_move, 'O')  # AI makes move

# Check game state
print(game.get_board_string())
print(f"Winner: {game.winner}")
print(f"Game finished: {game.is_finished}")
```

## Action Format

Actions are specified using coordinate notation:
- **A1, A2, A3**: Top row (left to right)
- **B1, B2, B3**: Middle row (left to right)  
- **C1, C2, C3**: Bottom row (left to right)

Example board layout:
```
  1   2   3
A   |   |  
  ---------
B   |   |  
  ---------
C   |   |  
```

## AI Opponents

### Minimax AI
- Uses the minimax algorithm for optimal play
- Provides challenging gameplay
- Always makes the best possible move

### Random AI
- Makes random valid moves
- Useful for testing and casual play
- Provides unpredictable gameplay

## Integration with GeneralGameBench

The Tic Tac Toe implementation follows GeneralGameBench conventions:

1. **BaseEnv Interface**: Implements all required methods (`initial_obs`, `step`, `obs2text`, `text2action`, etc.)
2. **Observation/Action Classes**: Structured data classes for game state and actions
3. **Configuration System**: YAML-based configuration compatible with the framework
4. **Logging Support**: Integrated logging and step-by-step game recording
5. **Multi-modal Support**: Text and image-based observations

## Strategic Guidelines

The AI agent is provided with strategic guidelines:

1. **Win immediately** if possible
2. **Block opponent** from winning
3. **Create multiple threats** (fork strategy)
4. **Control the center** (B2) for maximum opportunities
5. **Take corners** (A1, A3, C1, C3) for strategic advantage
6. **Avoid edges** unless necessary

## Dependencies

- Python 3.7+
- PIL (Pillow) for image generation
- gymnasium (for BaseEnv interface)
- Other GeneralGameBench dependencies

## Testing

The implementation has been tested for:
- ✅ Game logic correctness
- ✅ AI opponent functionality
- ✅ Environment interface compliance
- ✅ Configuration system integration
- ✅ Prompt system compatibility

## Future Enhancements

Potential improvements:
- Advanced AI opponents (Monte Carlo Tree Search)
- Tournament mode for multiple games
- Performance analytics and statistics
- Custom board sizes (4x4, 5x5)
- Network multiplayer support
