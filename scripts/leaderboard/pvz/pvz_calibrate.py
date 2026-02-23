"""
PvZ coordinate calibration tool.

Run this script to collect true pixel coordinates for game elements and
automatically update constants.py.

Usage:
1. Launch Plants vs. Zombies.
2. Enter a level and pause (Back to Game button is visible).
3. Run this script: python scripts/pvz_calibrate.py
4. The script will:
     - Capture and save a screenshot to logs/pvz_calibrate/
     - Open an interactive window and ask you to click, in order:
         * Center of Back to Game button
         * Center of slot 0
         * Center of slot 1
         * Center of slot 2
         * Center of top-left lawn cell (0,0)
         * Center of bottom-right lawn cell (4,8)
     - Compute coordinate configuration
     - Auto-update src/game_servers/pvz/game/constants.py
     - Create a constants.py.backup file

Notes:
- tkinter is required (conda install tk or pip install tkinter)
- If tkinter is unavailable, inspect the screenshot and edit constants.py manually
- Calibration is based on client-area coordinates (excluding title bar and borders)
- A backup of constants.py is created before each update
"""

import os
import sys
import time
from datetime import datetime

# Add src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(script_dir), "src")
sys.path.insert(0, src_dir)

from game_servers.GUI.GUI_manager import GUIManager
from PIL import Image


def find_pvz_window():
    """Find the PvZ game window."""
    gui = GUIManager()
    
    # Try different window titles
    possible_titles = [
        "Plants vs. Zombies",
        "植物大战僵尸",
        "PlantsVsZombies",
        "Zombies",
        "Plants",
    ]
    
    for title in possible_titles:
        window = gui.find_window(title)
        if window:
            print(f"✅ Game window found: {window.title}")
            print(f"   Position: ({window.left}, {window.top})")
            print(f"   Size: {window.width} x {window.height}")
            return gui, window
    
    # List windows to help user identify target
    print("❌ PvZ window not found. Current windows:")
    all_windows = gui._window_manager.list_all_windows()
    for i, w in enumerate(all_windows[:20]):  # Show only first 20
        print(f"   {i+1}. {w.title}")
    
    return gui, None


def capture_and_save(gui, window, output_dir):
    """Capture screenshot and save it."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Activate window
    gui.activate(window)
    time.sleep(5)
    
    # Refresh window info
    window = gui.refresh_window(window)
    
    # Capture screenshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(output_dir, f"pvz_screenshot_{timestamp}.png")
    
    screenshot = gui.capture(window, save_path)
    print(f"✅ Screenshot saved: {save_path}")
    print(f"   Image size: {screenshot.width} x {screenshot.height}")
    
    return screenshot, save_path


def interactive_calibration(image_path):
    """Interactive calibration - click image to collect coordinates."""
    try:
        import tkinter as tk
        from PIL import ImageTk
    except ImportError:
        print("\n⚠️ tkinter is not installed; interactive calibration is unavailable")
        print("Please open the screenshot manually and measure coordinates")
        return None
    
    print("\n" + "="*60)
    print("Interactive Calibration Mode")
    print("="*60)
    print("Click the following positions in order (one click each):")
    print("1. Center of Back to Game button")
    print("2. Center of first slot (slot 0)")
    print("3. Center of second slot (slot 1)")
    print("4. Center of third slot (slot 2)")
    print("5. Center of lawn cell (0,0)")
    print("6. Center of lawn cell (4,8)")
    print("\nPress 'r' to restart, 'q' to quit")
    print("="*60)
    
    img = Image.open(image_path)
    
    root = tk.Tk()
    root.title("PvZ Coordinate Calibration - Click Marked Positions")
    
    # Resize for display if image is too large
    max_width, max_height = 1200, 800
    scale = min(max_width / img.width, max_height / img.height, 1.0)
    display_width = int(img.width * scale)
    display_height = int(img.height * scale)
    
    if scale < 1.0:
        display_img = img.resize((display_width, display_height), Image.LANCZOS)
    else:
        display_img = img
    
    photo = ImageTk.PhotoImage(display_img)
    
    canvas = tk.Canvas(root, width=display_width, height=display_height)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    
    clicks = []
    labels = [
        "Back to Game button center",
        "Slot 0 center",
        "Slot 1 center",
        "Slot 2 center",
        "Cell (0,0) center",
        "Cell (4,8) center",
    ]
    
    status_label = tk.Label(root, text=f"Please click: {labels[0]}", font=('Arial', 12))
    status_label.pack()
    
    coords_label = tk.Label(root, text="Recorded coordinates: none", font=('Arial', 10))
    coords_label.pack()
    
    def on_click(event):
        # Convert back to original image coordinates
        real_x = int(event.x / scale)
        real_y = int(event.y / scale)
        
        clicks.append((real_x, real_y))
        
        # Mark on canvas
        canvas.create_oval(event.x-5, event.y-5, event.x+5, event.y+5, 
                          fill='red', outline='white', width=2)
        canvas.create_text(event.x+10, event.y, text=f"{len(clicks)}", 
                          fill='yellow', font=('Arial', 10, 'bold'))
        
        # Update status
        coords_label.config(text=f"Click {len(clicks)}: ({real_x}, {real_y})")
        
        if len(clicks) < len(labels):
            status_label.config(text=f"Please click: {labels[len(clicks)]}")
        else:
            status_label.config(text="Calibration complete! Press 'q' to quit and view results")
    
    def on_key(event):
        if event.char == 'q':
            root.quit()
        elif event.char == 'r':
            clicks.clear()
            canvas.delete("all")
            canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            status_label.config(text=f"Please click: {labels[0]}")
            coords_label.config(text="Recorded coordinates: none")
    
    canvas.bind("<Button-1>", on_click)
    root.bind("<Key>", on_key)
    
    root.mainloop()
    root.destroy()
    
    return clicks


def calculate_coordinates(clicks, window_width, window_height):
    """Compute coordinate config from clicks using the first 3 plant slots."""
    if len(clicks) < 6:
        print("❌ Insufficient click data: 6 points required")
        return None
    
    # Back to Game button + first 3 slot centers
    back_to_game_x, back_to_game_y = clicks[0]
    slot0_x, slot0_y = clicks[1]
    slot1_x, slot1_y = clicks[2]
    slot2_x, slot2_y = clicks[3]
    grid_00_x, grid_00_y = clicks[4]
    grid_48_x, grid_48_y = clicks[5]
    
    # Compute width from adjacent slots (average improves robustness)
    slot_width_01 = slot1_x - slot0_x
    slot_width_12 = slot2_x - slot1_x
    slot_width = (slot_width_01 + slot_width_12) / 2
    
    print(f"\nSlot width calculation:")
    print(f"  Slot 0->1 width: {slot_width_01}")
    print(f"  Slot 1->2 width: {slot_width_12}")
    print(f"  Average width: {slot_width:.1f}")
    
    # Average Y of slot centers
    slot_center_y = int((slot0_y + slot1_y + slot2_y) / 3)
    
    # Assume 8 slots (0-7)
    num_slots = 8
    
    # Compute plant bar parameters
    plant_bar_offset_x = int(slot0_x - slot_width / 2)
    plant_bar_offset_y = int(slot_center_y - 30)  # Approximate vertical offset
    plant_slot_width = int(slot_width)
    plant_slot_height = 60  # Default height
    
    # Validate estimate: infer slot 2 position
    predicted_slot2_x = slot0_x + 2 * slot_width
    print(f"\nValidation: third slot (slot 2)")
    print(f"  Actual click x: {slot2_x}")
    print(f"  Estimated x: {predicted_slot2_x:.1f}")
    print(f"  Error: {abs(slot2_x - predicted_slot2_x):.1f} px")
    
    # Compute lawn grid parameters (5 rows x 9 cols)
    grid_rows = 5
    grid_cols = 9
    grid_cell_width = int((grid_48_x - grid_00_x) / (grid_cols - 1))
    grid_cell_height = int((grid_48_y - grid_00_y) / (grid_rows - 1))
    grid_offset_x = int(grid_00_x - grid_cell_width / 2)
    grid_offset_y = int(grid_00_y - grid_cell_height / 2)
    
    config = {
        "window_size": (window_width, window_height),
        "back_to_game_x": back_to_game_x,
        "back_to_game_y": back_to_game_y,
        "plant_bar_offset_x": plant_bar_offset_x,
        "plant_bar_offset_y": plant_bar_offset_y,
        "plant_slot_width": plant_slot_width,
        "plant_slot_height": plant_slot_height,
        "num_plant_slots": num_slots,
        "grid_offset_x": grid_offset_x,
        "grid_offset_y": grid_offset_y,
        "grid_cell_width": grid_cell_width,
        "grid_cell_height": grid_cell_height,
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        # Extra metadata
        "slot_center_y": slot_center_y,
        "slot0_center": (slot0_x, slot0_y),
        "slot1_center": (slot1_x, slot1_y),
        "slot2_center": (slot2_x, slot2_y),
    }
    
    return config


def print_config(config):
    """Print configuration."""
    print("\n" + "="*60)
    print("📋 Calibration Result - apply to constants.py")
    print("="*60)
    print(f"""
# Game window size
DEFAULT_WINDOW_WIDTH = {config['window_size'][0]}
DEFAULT_WINDOW_HEIGHT = {config['window_size'][1]}

# Back to Game button position (used for auto-click resume)
BACK_TO_GAME_X = {config['back_to_game_x']}
BACK_TO_GAME_Y = {config['back_to_game_y']}

# Lawn grid configuration
GRID_ROWS = {config['grid_rows']}
GRID_COLS = {config['grid_cols']}
GRID_CELL_WIDTH = {config['grid_cell_width']}
GRID_CELL_HEIGHT = {config['grid_cell_height']}
GRID_OFFSET_X = {config['grid_offset_x']}
GRID_OFFSET_Y = {config['grid_offset_y']}

# Plant selection bar configuration
PLANT_BAR_OFFSET_X = {config['plant_bar_offset_x']}
PLANT_BAR_OFFSET_Y = {config['plant_bar_offset_y']}
PLANT_SLOT_WIDTH = {config['plant_slot_width']}
PLANT_SLOT_HEIGHT = {config['plant_slot_height']}
NUM_PLANT_SLOTS = {config['num_plant_slots']}

# Slot-center Y coordinate (used by get_plant_slot_position)
SLOT_CENTER_Y = {config.get('slot_center_y', config['plant_bar_offset_y'] + 30)}
""")
    # Print slot center positions for verification
    if 'slot0_center' in config:
        print("# Calibration reference points:")
        print(f"# Slot 0 center: {config['slot0_center']}")
        print(f"# Slot 1 center: {config['slot1_center']}")
        print(f"# Slot 2 center: {config['slot2_center']}")
        print()
    print("="*60)


def update_constants_file(config):
    """Auto-update constants.py."""
    # Find constants.py path
    constants_path = os.path.join(src_dir, "game_servers", "pvz", "game", "constants.py")
    
    if not os.path.exists(constants_path):
        print(f"\n❌ constants.py not found: {constants_path}")
        return False
    
    print(f"\n📝 Preparing to update constants.py...")
    
    # Create backup
    backup_path = constants_path + ".backup"
    try:
        import shutil
        shutil.copy2(constants_path, backup_path)
        print(f"   Backup created: {backup_path}")
    except Exception as e:
        print(f"   ⚠️ Backup failed: {e}")
    
    # Read existing file
    with open(constants_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Prepare new constant values
    from datetime import datetime
    calibration_time = datetime.now().strftime("%Y-%m-%d")
    
    new_values = {
        'DEFAULT_WINDOW_WIDTH': config['window_size'][0],
        'DEFAULT_WINDOW_HEIGHT': config['window_size'][1],
        'BACK_TO_GAME_X': config['back_to_game_x'],
        'BACK_TO_GAME_Y': config['back_to_game_y'],
        'GRID_ROWS': config['grid_rows'],
        'GRID_COLS': config['grid_cols'],
        'GRID_CELL_WIDTH': config['grid_cell_width'],
        'GRID_CELL_HEIGHT': config['grid_cell_height'],
        'GRID_OFFSET_X': config['grid_offset_x'],
        'GRID_OFFSET_Y': config['grid_offset_y'],
        'PLANT_SLOT_WIDTH': config['plant_slot_width'],
        'NUM_PLANT_SLOTS': config['num_plant_slots'],
        'SLOT_CENTER_Y': config.get('slot_center_y', config['plant_bar_offset_y'] + 30),
    }
    
    # Update file content
    updated_lines = []
    updated_count = 0
    
    for line in lines:
        line_stripped = line.strip()
        
        # Update calibration-time comment
        if line_stripped.startswith('# 校准时间:'):
            updated_lines.append(f"# Calibration time: {calibration_time} (client-area coordinates, title bar excluded)\n")
            updated_count += 1
            continue
        
        # Update constant values
        updated = False
        for const_name, const_value in new_values.items():
            if line_stripped.startswith(f'{const_name} ='):
                # Preserve existing inline comments
                if '#' in line:
                    comment = line[line.index('#'):]
                    updated_lines.append(f"{const_name} = {const_value}  {comment}")
                else:
                    updated_lines.append(f"{const_name} = {const_value}\n")
                updated = True
                updated_count += 1
                print(f"   ✓ Updated {const_name} = {const_value}")
                break
        
        if not updated:
            # Update calibration point references in comments
            if 'Slot 0 中心:' in line and '#' in line:
                slot0 = config.get('slot0_center', (0, 0))
                updated_lines.append(f"# Slot 0 center: ({slot0[0]}, {slot0[1]})\n")
                updated_count += 1
            elif 'Slot 1 中心:' in line and '#' in line:
                slot1 = config.get('slot1_center', (0, 0))
                updated_lines.append(f"# Slot 1 center: ({slot1[0]}, {slot1[1]})\n")
                updated_count += 1
            elif 'Slot 2 中心:' in line and '#' in line:
                slot2 = config.get('slot2_center', (0, 0))
                updated_lines.append(f"# Slot 2 center: ({slot2[0]}, {slot2[1]})\n")
                updated_count += 1
            elif 'slot 0 中心x' in line_stripped and '#' in line:
                # Update comment in get_plant_slot_position()
                slot0_x = config.get('slot0_center', (0, 0))[0]
                indent = len(line) - len(line.lstrip())
                updated_lines.append(f"{' ' * indent}# Direct measurement formula: slot 0 center x = {slot0_x}, slot width = {config['plant_slot_width']}\n")
                updated_count += 1
            elif 'x =' in line and 'slot_index * PLANT_SLOT_WIDTH' in line:
                # Update formula in get_plant_slot_position()
                slot0_x = config.get('slot0_center', (0, 0))[0]
                indent = len(line) - len(line.lstrip())
                updated_lines.append(f"{' ' * indent}x = {slot0_x} + slot_index * PLANT_SLOT_WIDTH\n")
                updated_count += 1
            else:
                updated_lines.append(line)
    
    # Write back file
    with open(constants_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)
    
    print(f"\n✅ constants.py updated automatically ({updated_count} changes)")
    print(f"   File path: {constants_path}")
    return True


def main():
    print("="*60)
    print("🌻 PvZ Coordinate Calibration Tool 🧟")
    print("="*60)
    
    # 1. Find game window
    gui, window = find_pvz_window()
    
    if window is None:
        print("\nPlease start Plants vs. Zombies first, then run this script again")
        return
    
    # 2. Capture screenshot
    output_dir = os.path.join(os.path.dirname(script_dir), "logs", "pvz_calibrate")
    screenshot, save_path = capture_and_save(gui, window, output_dir)
    
    # 3. Interactive calibration
    print("\nStarting interactive calibration...")
    clicks = interactive_calibration(save_path)
    
    if clicks and len(clicks) >= 6:
        # 4. Compute configuration
        config = calculate_coordinates(clicks, screenshot.width, screenshot.height)
        
        if config:
            print_config(config)
            
            # Save config to file
            config_path = os.path.join(output_dir, "calibration_result.txt")
            with open(config_path, 'w') as f:
                f.write("PvZ Calibration Result\n")
                f.write("="*40 + "\n")
                for k, v in config.items():
                    f.write(f"{k} = {v}\n")
            print(f"\n✅ Configuration saved to: {config_path}")
            
            # 5. Auto-update constants.py
            update_constants_file(config)
    else:
        print("\nCalibration not completed or was canceled")
        print(f"You can manually inspect the screenshot: {save_path}")
        print("Then measure coordinates with an image editor")


if __name__ == "__main__":
    main()
