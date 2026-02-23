import re

def construct_init_map(x_max, y_max, map_screen_raw):
    width, height = x_max + 1, y_max + 1

    # 1. Initialize empty map
    maps = [['?' for _ in range(width)] for _ in range(height)]

    # 2. Extract coordinates and symbols from map_screen_raw
    if map_screen_raw:
        map_lines = map_screen_raw.strip().split('\n')
        for line in map_lines:
            tile_matches = re.findall(r"\(\s*(\d+),\s*(\d+)\):\s*([^\s]+)", line)
            for x_str, y_str, val in tile_matches:
                x, y = int(x_str), int(y_str)
                if 0 <= x < width and 0 <= y < height:
                    maps[y][x] = val

    return maps

def refine_current_map(maps, x_max, y_max, map_screen_raw):
    width, height = x_max + 1, y_max + 1

    if map_screen_raw:
        map_lines = map_screen_raw.strip().split('\n')
        sprite_positions = []

        for line in map_lines:
            tile_matches = re.findall(r"\(\s*(\d+),\s*(\d+)\):\s*([^\s]+)", line)
            for x_str, y_str, val in tile_matches:
                x, y = int(x_str), int(y_str)
                if 0 <= x < width and 0 <= y < height:
                    if val.startswith("SPRITE_"):
                        sprite_positions.append((x, y, val))
                    else:
                        maps[y][x] = val

        # Seperately process SPRITEs
        for x, y, sprite_val in sprite_positions:
            for row in range(height):
                for col in range(width):
                    if maps[row][col] == sprite_val and (col != x or row != y):
                        maps[row][col] = '?'
            maps[y][x] = sprite_val

    return maps

def parse_game_state(text):
    result = {}

    # 1. State
    state_match = re.search(r"State:\s*(\w+)", text)
    result['state'] = state_match.group(1) if state_match else None

    # 2. Filtered Screen Text
    filtered_text = re.search(r"\[Filtered Screen Text\]\n(.*?)(?=\[Selection Box Text\])", text, re.DOTALL)
    text_tmp = filtered_text.group(1).strip()
    result['filtered_screen_text'] = text_tmp if text_tmp != "" else "N/A"

    # 3. Selection Box Text
    selection_box = re.search(r"\[Selection Box Text\]\n(.*?)(?=\[Enemy Pokemon\])", text, re.DOTALL)
    text_tmp = selection_box.group(1).strip()
    result['selection_box_text'] = text_tmp if text_tmp != "" else "N/A"

    # 4. Enemy Pokemon
    enemy_pokemon = {}
    enemy_section = re.search(r"\[Enemy Pokemon\]\n(.*?)(?=\[Current Party\])", text, re.DOTALL)
    if enemy_section:
        for line in enemy_section.group(1).splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                enemy_pokemon[key.strip()] = value.strip()
    result['enemy_pokemon'] = enemy_pokemon

    # 5. Your Party
    party_match = re.search(r"\[Current Party\]\n(.*?)(?=\[Badge List\])", text, re.DOTALL)
    result['your_party'] = party_match.group(1).strip() if party_match else ""

    # 6. Badge List
    badge_match = re.search(r"\[Badge List\]\n(.*?)(?=\[Bag\])", text, re.DOTALL)
    result['badge_list'] = badge_match.group(1).strip() if badge_match else ""

    # 7. Inventory
    inventory_match = re.search(r"\[Bag\]\n(.*?)(?=\[Current Money\])", text, re.DOTALL)
    result['inventory'] = inventory_match.group(1).strip() if inventory_match else ""

    # 8. Current Money
    money_match = re.search(r"\[Current Money\]:\s*¥(\d+)", text)
    result['money'] = int(money_match.group(1)) if money_match else 0

    # 9. Map Info
    map_info = {}
    map_section = re.search(r"\[Map Info\]\n(.*)", text, re.DOTALL)
    if map_section:
        map_text = map_section.group(1)
        map_name_match = re.search(r"Map Name:\s*(.*?),", map_text)
        map_info['map_name'] = map_name_match.group(1) if map_name_match else None

        map_type_match = re.search(r"Map type:\s*(.*)", map_text)
        map_info['map_type'] = map_type_match.group(1).strip() if map_type_match else None

        expansion_match = re.search(r"Expansion direction:\s*(.*)", map_text)
        map_info['expansion_direction'] = expansion_match.group(1).strip() if expansion_match else None

        coords_match = re.search(r"\(x_max , y_max\):\s*\((\d+),\s*(\d+)\)", map_text)
        map_info['x_max'] = int(coords_match.group(1)) if coords_match else None
        map_info['y_max'] = int(coords_match.group(2)) if coords_match else None

        pos_match = re.search(r"Your position \(x, y\): \((\d+), (\d+)\)", map_text)
        map_info['player_pos_x'] = int(pos_match.group(1)) if pos_match else None
        map_info['player_pos_y'] = int(pos_match.group(2)) if pos_match else None

        facing_match = re.search(r"Your facing direction:\s*(\w+)", map_text)
        map_info['facing'] = facing_match.group(1) if facing_match else None

        try:
            # Optional: extract action instructions and screen map
            map_info['map_screen_raw'] = re.search(r"Map on Screen:\n(.+)", map_text, re.DOTALL).group(1).strip()
        except:
            map_info['map_screen_raw'] = None

    result['map_info'] = map_info

    return result

def get_map_memory_dict(state_dict: dict, map_memory_dict: dict) -> dict:
    """
    Updates the map memory dictionary based on the current state and map information.
    """
    current_map = state_dict['map_info']['map_name']
    if not state_dict['map_info']['x_max'] == None:
        if not current_map in map_memory_dict.keys():
            map_memory_dict[current_map] = {
                "explored_map": construct_init_map(
                    state_dict['map_info']['x_max'],
                    state_dict['map_info']['y_max'],
                    state_dict['map_info']['map_screen_raw']
                    ),
                "history": [],
            }
        else:
            map_memory_dict[current_map]["explored_map"] = refine_current_map(
                map_memory_dict[current_map]["explored_map"],
                state_dict['map_info']['x_max'],
                state_dict['map_info']['y_max'],
                state_dict['map_info']['map_screen_raw']
                )
    return map_memory_dict

def replace_filtered_screen_text(text_obs: str, dialog_buffer: list) -> str:
    """
    Replaces the filtered screen text in the observation string with the dialog buffer.
    """
    if not dialog_buffer:
        return text_obs

    # Generate new section
    new_section = f"[Interacted Dialog Buffer]\n" + "\n".join(dialog_buffer) + "\n\n"

    # Find location of [Filtered Screen Text]
    match = re.search(r"(?=\[Filtered Screen Text\])", text_obs)
    if match:
        insert_index = match.start()
        new_text_obs = text_obs[:insert_index] + new_section + text_obs[insert_index:]
        return new_text_obs
    else:
        return new_section + "\n" + text_obs

def replace_map_on_screen_with_full_map(text_obs: str, map_current: list[list[str]]) -> str:
    """
    Replaces the map on screen in the observation string with the full map.
    """
    # Return original text if map_current is empty or invalid
    if not map_current or not isinstance(map_current, list) or \
        not (all(isinstance(row, list) for row in map_current) if map_current else True):
        return text_obs
    if map_current and not map_current[0]: # handles case like [[]]
            map_current = [] # Treat as empty map

    # --- 0. Remove "Map on Screen" section first ---
    # Uses the format "Map on Screen:" as per typical game state text
    processed_text_obs = re.sub(
        r"Map on Screen:(?:\n(?:\(\s*\d+,\s*\d+\): [^\n]+\n*)+)?", # Allow empty or non-existent section
        "", text_obs, flags=re.DOTALL
    )

    # --- Then, fill 'N/A' to other specified empty sections ---
    section_names = [
        "Filtered Screen Text",
        "Selection Box Text",
        "Enemy Pokemon",
        "Current Party",  # Updated
        "Badge List",
        "Bag",            # Updated
        "Current Money"   # Added
    ]
    for section in section_names:
        pattern = rf"(\[{re.escape(section)}\])\n(?=\s*\[|\Z)"
        processed_text_obs = re.sub(pattern, r"\1\nN/A\n", processed_text_obs, flags=re.MULTILINE)

    # Clean up potentially multiple blank lines left by removals/changes
    processed_text_obs = re.sub(r"\n\s*\n", "\n\n", processed_text_obs).strip()

    # --- 1. Extract player position ---
    player_x, player_y = -1, -1  # Default if not found
    player_pos_match = re.search(r"Your position \(x, y\): \((\d+), (\d+)\)", processed_text_obs)
    if player_pos_match:
        player_x = int(player_pos_match.group(1))
        player_y = int(player_pos_match.group(2))

    # --- 2. Generate the compact full map text ---
    map_grid_lines = []
    notable_objects = {} # Stores {(x, y): "char_representation: full_name"}

    if not map_current: # If map_current became empty (e.g. was [[]] or initially empty)
        full_map_text_block = "[Full Map]\n(Map data is empty or malformed)\n"
    else:
        num_rows = len(map_current)
        num_cols = len(map_current[0])
        if num_cols == 0: # Handle case where rows exist but are empty
                full_map_text_block = "[Full Map]\n(Map data has rows but no columns)\n"
                map_current = [] # Treat as empty for subsequent logic
        else:
            actual_x_max = num_cols - 1
            actual_y_max = num_rows - 1

            # --- Calculate paddings and dimensions ---
            # Width of the y-axis number (e.g., '7' is 1, '10' is 2)
            y_label_num_width = len(str(actual_y_max)) if actual_y_max >= 0 else 1
            # String for the longest y-axis label, e.g., " 7 | " or "10 | "
            # This defines the left padding for header lines.
            max_y_label_str = f"{actual_y_max:<{y_label_num_width}} | "
            header_left_padding = " " * len(max_y_label_str)

            x_axis_markers_prefix = "(x=0) "
            x_axis_markers_suffix = f" (x={actual_x_max})"
            
            # Total width of the content part of the column number line (markers + digits)
            # This width is used for centering (y=0) and (y=Y_MAX) labels.
            column_line_content_width = len(x_axis_markers_prefix) + num_cols + len(x_axis_markers_suffix)

            # --- Map Header Construction ---
            # (y=0) label
            y0_label_text = "(y=0)"
            y0_padding_count = (column_line_content_width - len(y0_label_text)) // 2
            y0_padding = " " * max(0, y0_padding_count)
            map_grid_lines.append(f"{header_left_padding}{y0_padding}{y0_label_text}")

            # Column number headers (units, tens, hundreds)
            col_headers_digits_only_list = [] # Stores just the digit strings, each num_cols long
            if num_cols > 0:
                if num_cols >= 100:
                    col_headers_digits_only_list.append("".join([str(i // 100 % 10) if i >= 100 else ' ' for i in range(num_cols)]))
                if num_cols >= 10:
                    col_headers_digits_only_list.append("".join([str(i // 10 % 10) if i >= 10 else ' ' for i in range(num_cols)]))
                col_headers_digits_only_list.append("".join([str(i % 10) for i in range(num_cols)])) # Units

            for i, digits_str in enumerate(col_headers_digits_only_list):
                if i == len(col_headers_digits_only_list) - 1: # Unit digits line (last in list) gets x-axis markers
                    line_content = f"{x_axis_markers_prefix}{digits_str}{x_axis_markers_suffix}"
                else: # Tens, Hundreds lines: pad to align digits under markers
                    line_content = f"{' ' * len(x_axis_markers_prefix)}{digits_str}{' ' * len(x_axis_markers_suffix)}"
                map_grid_lines.append(f"{header_left_padding}{line_content}")
            
            # Separator line: +--------+
            # Aligns with the num_cols part of the header
            separator_padding = " " * (len(header_left_padding) + len(x_axis_markers_prefix))
            map_grid_lines.append(f"{separator_padding}+{'-' * num_cols}+")

            # --- Map Rows Construction ---
            for y_coord in range(num_rows):
                current_y_label_str = f"{y_coord:<{y_label_num_width}} | " # e.g., "0 | ", "10| "
                line_content_chars = []
                for x_coord in range(num_cols):
                    val_at_cell = map_current[y_coord][x_coord]
                    original_char_code = '?' # Default representation

                    if val_at_cell and isinstance(val_at_cell, str):
                        if len(val_at_cell) == 1:
                            original_char_code = val_at_cell
                        else:
                            original_char_code = val_at_cell[0].upper()
                            notable_objects[(x_coord, y_coord)] = f"{val_at_cell}"
                    elif val_at_cell is None or val_at_cell == "":
                        original_char_code = '?'
                    else:
                        original_char_code = 'E' # Error for unexpected type
                        notable_objects[(x_coord, y_coord)] = f"E: Invalid_Data_Type({type(val_at_cell).__name__})"
                    
                    # Player position overrides other characters on the grid
                    # if x_coord == player_x and y_coord == player_y:
                    #     char_for_grid = 'P'
                    # else:
                    #     char_for_grid = original_char_code
                    # line_content_chars.append(char_for_grid)
                    line_content_chars.append(original_char_code)
                
                map_row_content_str = "".join(line_content_chars)
                # Map content directly follows y-axis label for compactness
                map_grid_lines.append(f"{current_y_label_str}{map_row_content_str}")

            # --- Map Footer Construction ---
            # (y=y_max) label, centered like (y=0)
            y_max_label_text = f"(y={actual_y_max})"
            y_max_padding_count = (column_line_content_width - len(y_max_label_text)) // 2
            y_max_padding = " " * max(0, y_max_padding_count)
            map_grid_lines.append(f"{header_left_padding}{y_max_padding}{y_max_label_text}")

            # --- Assemble the [Full Map] and [Notable Objects] blocks ---
            full_map_text_block = "[Full Map]\n" + "\n".join(map_grid_lines)
            if notable_objects:
                notable_list_str = "\n\n[Notable Objects]"
                sorted_notables_coords = sorted(notable_objects.keys(), key=lambda k: (k[1], k[0])) # Sort by y, then x
                for coord_key in sorted_notables_coords:
                    x_obj, y_obj = coord_key
                    notable_list_str += f"\n({x_obj:2}, {y_obj:2}) {notable_objects[coord_key]}"
                full_map_text_block += notable_list_str
    
    # --- 3. Append the full map text block to the end of processed_text_obs ---
    if processed_text_obs: # If there's other content before the map
        final_text_obs = processed_text_obs + "\n\n" + full_map_text_block
    else: # If processed_text_obs was empty (e.g., original only had removable sections)
        final_text_obs = full_map_text_block
        
    # Final cleanup of multiple newlines (e.g., >2 newlines become 2) and trailing/leading whitespace
    final_text_obs = re.sub(r"\n{3,}", "\n\n", final_text_obs).strip()
    
    return final_text_obs

