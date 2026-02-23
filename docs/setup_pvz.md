# Plants vs. Zombies

## 1. Getting Started

### Prerequisites

- Purchase and install Plants vs. Zombies: Game of the Year from Steam
- Python environment with required dependencies
- Game resolution: **800×600 (recommended)** or custom (requires calibration)

### Setup Steps

1. **Launch Plants vs. Zombies**

   Start the game manually and ensure the game window title is `"Plants vs. Zombies"`.
2. **Navigate to a Level**

   Select a level (e.g., the first level) and enter the game.
3. **Pause the Game**

   - **Press ESC or click the pause button** to enter the pause screen
   - **Ensure the "Back to Game" button is visible**
   - **Do not click "Back to Game" - stay on the pause screen**

   **Why pause?** The framework will automatically click the "Back to Game" button to start the game. This ensures synchronized timing and prevents missing the initial game state.
4. **Run the Test**

   Use the following command to start the agent:

   ```bash
   python scripts/play_game.py --config ./src/agent_client/configs/pvz/config.yaml
   ```

### What Happens During Testing

The agent performs the following loop for `max_steps` iterations:

1. Automatically clicks "Back to Game" button (on first step only)
2. Captures screenshot every `screenshot_interval` seconds
3. Sends image to the vision-language model (LLM)
4. Parses LLM output into semantic actions:
   - `plant <slot> at (<row>, <col>)` - Plant from slot at grid position
   - `collect` - Collect visible sunlight
   - `wait` - Wait and observe
5. Executes actions via simulated mouse clicks
6. Runs for exactly `max_steps` iterations (no early termination)

### Configuration

Control test behavior in `config.yaml`:

```yaml
runner:
  max_steps: 50  # Test duration (number of agent steps)

env:
  screenshot_interval: 0.5  # Screenshot frequency (seconds)
  action_mode: "semantic"   # "semantic" or "gui"
```

---

## 2. Technical Details

### Coordinate System

The game uses a **5×9 grid** system for the lawn:

- **5 rows** (top to bottom, 1-indexed for LLM: 1-5, 0-indexed internally: 0-4)
- **9 columns** (left to right, 1-indexed for LLM: 1-9, 0-indexed internally: 0-8)
- House on the left, zombies enter from the right

**Default Coordinates (800×600 resolution):**

The coordinates are defined in `src/game_servers/pvz/game/constants.py`:

```python
# Grid configuration
GRID_ROWS = 5
GRID_COLS = 9
GRID_CELL_WIDTH = 81    # Cell width (pixels)
GRID_CELL_HEIGHT = 99   # Cell height (pixels)
GRID_OFFSET_X = 37      # Lawn top-left X offset
GRID_OFFSET_Y = 78      # Lawn top-left Y offset

# Plant slot configuration
PLANT_SLOT_WIDTH = 58   # Distance between plant card slots
NUM_PLANT_SLOTS = 8     # Number of available plant slots

# Back to Game button (automatically clicked on start)
BACK_TO_GAME_X = 400    # Button center X
BACK_TO_GAME_Y = 500    # Button center Y
```

**Coordinate Conversion:**

Grid positions are converted to screen coordinates using:

```python
def grid_to_screen(row, col):
    x = GRID_OFFSET_X + col * GRID_CELL_WIDTH + GRID_CELL_WIDTH // 2
    y = GRID_OFFSET_Y + row * GRID_CELL_HEIGHT + GRID_CELL_HEIGHT // 2
    return (x, y)

def get_plant_slot_position(slot_index):
    x = 121 + slot_index * PLANT_SLOT_WIDTH
    y = 43  # Fixed Y position for all slots
    return (x, y)
```

### Sunlight Detection

**Method: Color and Shape Detection**

The system uses OpenCV-based detection (no YOLO model required):

1. **HSV Color Filtering**

   - Detects bright yellow regions (H: 18-42, S: 80-255, V: 180-255)
2. **Shape Filtering**

   - Area range: 1500-4500 pixels
   - Circularity threshold: >0.38 (distinguishes sun from sunflowers)
3. **Region Exclusion**

   - Excludes top-left sun counter UI
   - Excludes top plant card area
   - Only detects in game play area

**Key Parameters (in `pvz_env.py`):**

```python
SUN_MIN_AREA = 1500            # Minimum sun area (pixels)
SUN_MAX_AREA = 4500            # Maximum sun area (pixels)
SUN_MIN_CIRCULARITY = 0.38     # Circularity threshold
GAME_AREA_TOP = 90             # Exclude top UI area
SUN_COUNTER_X_MAX = 75         # Exclude sun counter
SUN_COUNTER_Y_MAX = 95
```

**Why This Works:**

- Sunlight is nearly circular (circularity ~0.4-0.7)
- Sunflowers have petals (circularity ~0.25-0.35)
- Bright yellow HSV values are distinctive

### Calibrating for Different Resolutions

If your game runs at a **different resolution than 800×600**, you need to adjust the coordinates in `constants.py`.

**Manual Calibration Method:**

1. **Take a screenshot** of the pause screen and a gameplay screen
2. **Measure pixel coordinates** using an image editor (e.g., Paint, GIMP, Photoshop):

   - Center of "Back to Game" button → `BACK_TO_GAME_X`, `BACK_TO_GAME_Y`
   - Centers of plant slots 1, 2, 3 → Calculate `PLANT_SLOT_WIDTH`
   - Center of grid cell (1,1) (top-left) → Calculate `GRID_OFFSET_X`, `GRID_OFFSET_Y`
   - Center of grid cell (1,2) (second column) → Calculate `GRID_CELL_WIDTH`
   - Center of grid cell (2,1) (second row) → Calculate `GRID_CELL_HEIGHT`
3. **Update `constants.py`** with your measured values:

   ```python
   # Example for 1280×720 resolution (adjust based on your measurements)
   GRID_CELL_WIDTH = 130
   GRID_CELL_HEIGHT = 158
   GRID_OFFSET_X = 60
   GRID_OFFSET_Y = 125
   PLANT_SLOT_WIDTH = 93
   BACK_TO_GAME_X = 640
   BACK_TO_GAME_Y = 600
   ```
4. **Test** by running the agent and verifying clicks land correctly

**Tips:**

- Measure from cell/button **centers**, not edges
- Use the pause screen screenshot for "Back to Game" button
- Use a gameplay screenshot for grid and plant slots
- Test with a single plant action to verify accuracy before full runs
