# Angry Birds

## 1. Getting Started

### Prerequisites

- Download Angry Birds iOS version from the official website
- Install an iOS simulator (e.g., iPadian, Smartface) to run the game
- Game window visible on screen

### Setup Steps

1. **Launch Angry Birds**

   Open Angry Birds in the iOS simulator and navigate to a level (e.g., Scene 1, Level 1).
2. **Ensure Game Window is Ready**

   - Game window title should contain `"Angry Birds"`
   - Game window should be fully visible (not minimized or obscured)
   - Wait on the level screen before shooting
3. **Run the Agent**

   ```bash
   python scripts/play_game.py --config ./src/agent_client/configs/angry_birds/config.yaml
   ```

### Configuration

Adjust behavior in `config.yaml`:

```yaml
runner:
  max_steps: 15  # Maximum shots per level

env:
  action_mode: "semantic"      # "semantic" or "gui"
  
  # Slingshot configuration (backup values if auto-detection fails)
  slingshot_pos_x: 0.15        # Relative X position (0-1)
  slingshot_pos_y: 0.65        # Relative Y position (0-1)
  
  # Shooting parameters
  slingshot_pull_ratio: 1.8    # Pull distance = slingshot_height × ratio
  max_pull_distance: 0.15      # Fallback if height not detected
  wait_after_shot: 5.0         # Wait time after shot (seconds)
  
  # Level selection
  scene: 1
  level: 1
```

---

## 2. Slingshot Detection Details

The framework uses **automatic template matching** to detect the slingshot position at the start of each game.

### How It Works

**Detection Priority:**

1. **Primary**: Detects `bird_on_slingshot.png` - the bird sitting on the slingshot (most accurate)
2. **Fallback**: Detects `slingshot.png` - the slingshot structure itself
3. **Backup**: Uses `slingshot_pos_x/y` from config if both fail

**Template Matching Process:**

```python
# Located in: src/game_servers/angry_birds/game/slingshot_detector.py

1. Load templates: bird_on_slingshot.png and slingshot.png
2. Convert screenshot to grayscale
3. Multi-scale template matching:
   - Scale range: 0.5x to 1.5x (20 steps)
   - Match method: Normalized cross-correlation
   - Threshold: 0.6 (minimum confidence)
4. Return best match above threshold
5. Calculate slingshot height from detected template size
```

**Why Detection is Important:**

- **Accurate pull calculation**: Uses detected `slingshot_height` to calculate pull distance:
  ```python
  max_pull_pixels = slingshot_height × slingshot_pull_ratio
  # Example: height=100px, ratio=1.8 → max_pull=180px
  ```
- **Resolution independent**: Works across different window sizes
- **Adaptive**: Automatically adjusts to in-game zoom level

### Detection Parameters

Key parameters in `src/game_servers/angry_birds/game/slingshot_detector.py`:

```python
# Template matching
threshold = 0.6              # Match confidence (0-1)
scale_range = (0.5, 1.5)     # Template scale range
scale_steps = 20             # Number of scales to test
prefer_bird = True           # Prioritize bird_on_slingshot

# Template locations
bird_template = "src/game_servers/angry_birds/images/bird_on_slingshot.png"
slingshot_template = "src/game_servers/angry_birds/images/slingshot.png"
```

### Detection Output

When successful, detection provides:

- **Position**: `(rel_x, rel_y)` - Relative coordinates (0.0-1.0)
- **Height**: `slingshot_height` - Template height in pixels (used for pull distance)
- **Type**: `'bird'` or `'slingshot'` - Which template matched
- **Visualization**: Saved to `logs/.../slingshot_detection.png`

**Example log output:**

```
Slingshot position updated (using bird):
  Old: (0.150, 0.650), height=0px
  New: (0.147, 0.623), height=98px
Match score: 0.812, scale: 1.05
```

### Visualization

The detection result is automatically saved with visual markers:

- **Green circle + crosshair**: Bird on slingshot detected
- **Orange circle + crosshair**: Slingshot structure detected
- **Label**: Shows coordinates and detected height

Check `logs/<your_run>/slingshot_detection.png` to verify detection accuracy.

### Troubleshooting

**Issue: "Slingshot not found" or low match score**

**Solutions:**

1. **Check visibility**: Ensure game window is fully visible and not obscured
2. **Check zoom level**: The automatic zoom-out should run first; verify it completed
3. **Adjust threshold**: Lower the detection threshold in code if needed:
   ```python
   # In angry_birds_env.py, _detect_and_update_slingshot()
   result = self.slingshot_detector.detect(image, threshold=0.5)  # Lower from 0.6
   ```
4. **Update templates**: Capture new `bird_on_slingshot.png` and `slingshot.png` from your game
5. **Check visualization**: Open `slingshot_detection.png` to see what was detected

**Issue: Shots are inaccurate despite detection**

**Solutions:**

1. **Verify slingshot height**: Check logs for detected height in pixels
2. **Adjust pull ratio**: Increase/decrease `slingshot_pull_ratio` in config:
   ```yaml
   env:
     slingshot_pull_ratio: 2.0  # Increase for stronger pulls
   ```
3. **Manual override**: Set exact position in config if detection is unreliable:
   ```yaml
   env:
     slingshot_pos_x: 0.15  # Manually measured
     slingshot_pos_y: 0.65
     max_pull_distance: 0.20  # Manual max pull distance
   ```

### Creating Custom Templates

If default templates don't work for your game version:

1. **Take a clear screenshot** at the level start screen
2. **Crop the bird on slingshot** (include the bird and top of slingshot)
3. **Save as** `src/game_servers/angry_birds/images/bird_on_slingshot.png`
4. **Crop just the slingshot structure** (Y-shaped part)
5. **Save as** `src/game_servers/angry_birds/images/slingshot.png`
6. **Restart** the framework to use new templates
