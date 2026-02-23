# Scene Investigator Demo Game for GeneralGameBench

This directory contains the implementation of Scene Investigator Demo game integrated with the GeneralGameBench framework using GUI mode.

## Game Overview

Scene Investigators (Demo) is an investigation game where you explore scenes, interact with objects, and solve puzzles. You control a character that can move around, examine objects, and interact with the environment.

## Features

- **GUI-based Control**: Full mouse and keyboard control through GUIManager
- **Multiple Input Modalities**: Support for keyboard and mouse actions
- **Visual Analysis**: Screenshot-based observation for LLM decision making
- **Complex Interactions**: Support for movement, examination, object rotation, and more

## File Structure

```
scene_investigator_demo/
├── config.yaml                    # Game server configuration
├── game/
│   ├── __init__.py                # Module initialization
│   └── scene_investigator_demo_env.py  # GeneralGameBench environment wrapper
└── README.md                      # This file
```

## Game Configuration

The game can be configured through `config.yaml`:

```yaml
env:
  task: "Investigate the scene and solve the puzzle"
  action_mode: "gui"  # GUI mode only
  window_title: "Scene Investigators (Demo)"
```

## Action Space

The game supports the following actions:

### Movement Controls:
- **W**: Move forward
- **A**: Move left
- **S**: Move backward
- **D**: Move right
- **Ctrl**: Crouch/Stand up (toggle)

### Interaction Controls:
- **F**: Toggle flashlight on/off
- **E**: Examine/Check objects
- **R**: Read (in certain scenarios)
- **Q**: Return/Go back
- **ESC**: Cancel/Exit

### Mouse Controls:
- **Left Click**: Interact with objects (when close enough, a dotted circle becomes solid)
- **Right Click**: Rotate objects
- **Mouse Movement**: Rotate camera/view (move in pixels to turn character's view)

## Usage

### Running with GeneralGameBench

```bash
python scripts/play_game.py --config src/agent_client/configs/scene_investigator_demo/config.yaml
```

### Prerequisites

1. **Start the game manually** before running the script
2. Ensure the game window title matches "Scene Investigators (Demo)"
3. The game should be in a playable state (not paused or in menu)

## Implementation Details

- **Window Detection**: Uses GUIManager to find and activate the game window
- **Screenshot Capture**: Automatically captures game screenshots for LLM analysis
- **Action Execution**: Supports multiple sequential GUI actions in a single step
- **Action Types**: Uses GUI_action with types like PRESS, CLICK, RIGHT_CLICK, MOVE_TO, HOTKEY, WAIT

## Notes

- All coordinates (x, y) are relative to the game window
- The center of the screen is typically at (window_width/2, window_height/2)
- Mouse movement for view rotation uses absolute coordinates (MOVE_TO)
- The game does not require mods - it uses pure GUI automation

