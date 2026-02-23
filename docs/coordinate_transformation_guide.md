# How to Enable Coordinate Transformation in Env

This document explains how to integrate coordinate transformation functionality in a game environment (Env). This feature converts normalized coordinates (typically based on 1000x1000) output by large models (such as Qwen-VL) to actual game window resolution coordinates and automatically handles boundary constraints.

## 1. Import Utility Functions

First, import the coordinate transformation tools in your environment file (e.g., `your_game_env.py`):

```python
from game_servers.utils.coordinate import transform_coordinate
```

## 2. Add Control Switch in Config

In the environment class's `Config` dataclass, add the `coor_trans` field so that this feature can be controlled through the configuration file:

```python
@dataclass
class Config:
    # ... other configuration items ...
    coor_trans: bool = False  # Enable coordinate transformation (1000x1000 -> actual resolution)
```

## 3. Modify the parse_action Method

In the `parse_action` method, after parsing the GUI action, check the `coor_trans` switch. If enabled, get the current window size and transform the coordinates.

```python
def parse_action(self, text: str) -> YourGameAction:
    # 1. Parse raw action
    action = self._parse_gui_action(text, YourGameAction)
    
    # 2. Coordinate transformation logic
    if self.cfg.coor_trans:
        # Get current window actual size
        width, height = self._get_window_size()
        
        if action.gui_actions:
            for i, gui_act in enumerate(action.gui_actions):
                # Transform X coordinate
                if "x" in gui_act.parameters:
                    original_x = gui_act.parameters["x"]
                    # transform_coordinate automatically scales and limits to [0, width-1] range
                    new_x = transform_coordinate(original_x, width)
                    gui_act.parameters["x"] = new_x
                    logger.info(f"Action {i} X transformed: {original_x} -> {new_x} (Width: {width})")
                
                # Transform Y coordinate
                if "y" in gui_act.parameters:
                    original_y = gui_act.parameters["y"]
                    # transform_coordinate automatically scales and limits to [0, height-1] range
                    new_y = transform_coordinate(original_y, height)
                    gui_act.parameters["y"] = new_y
                    logger.info(f"Action {i} Y transformed: {original_y} -> {new_y} (Height: {height})")
    
    return action
```
