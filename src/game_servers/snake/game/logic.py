"""
Pure functional game logic for Snake game.

This module contains stateless functions that implement the core game rules:
- Moving the snake
- Collision detection
- Food spawning and lifecycle
- Valid direction changes

These functions are designed to be testable and independent of the game state management.
"""

from typing import List, Tuple, Optional
import numpy as np


def calculate_new_head(head: Tuple[int, int], direction: str) -> Tuple[int, int]:
    """
    Calculate the new head position based on the current direction.
    
    Args:
        head: Current head position (x, y)
        direction: Direction to move ("L", "R", "U", "D")
    
    Returns:
        New head position (x, y)
    """
    head_x, head_y = head
    
    if direction == "L":
        return (head_x - 1, head_y)
    elif direction == "R":
        return (head_x + 1, head_y)
    elif direction == "D":
        return (head_x, head_y - 1)
    elif direction == "U":
        return (head_x, head_y + 1)
    else:
        raise ValueError(f"Invalid direction: {direction}")


def is_valid_direction_change(current_dir: str, new_dir: str) -> bool:
    """
    Check if a direction change is valid (not a reverse move).
    
    Args:
        current_dir: Current direction ("L", "R", "U", "D")
        new_dir: New direction to check
    
    Returns:
        True if the direction change is valid, False otherwise
    """
    if new_dir not in ["L", "R", "U", "D", "W"]:
        return False
    
    # Wait action is always valid
    if new_dir == "W":
        return True
    
    # Prevent reverse direction (can't go back on itself)
    if (new_dir == "L" and current_dir == "R") or \
       (new_dir == "R" and current_dir == "L") or \
       (new_dir == "U" and current_dir == "D") or \
       (new_dir == "D" and current_dir == "U"):
        return False
    
    return True


def check_collision(
    new_head: Tuple[int, int],
    snake: List[Tuple[int, int]],
    obstacles: List[Tuple[int, int]],
    board_size: int
) -> bool:
    """
    Check if the new head position results in a collision.
    
    Collision conditions:
    - Hit self (except tail, which will move)
    - Hit obstacle
    - Hit wall (boundary)
    
    Args:
        new_head: New head position to check
        snake: Current snake body positions (tail to head)
        obstacles: List of obstacle positions
        board_size: Size of the game board
    
    Returns:
        True if collision detected, False otherwise
    """
    x, y = new_head
    
    # Check wall collision (boundaries are walls)
    if x == 0 or y == 0 or x == board_size - 1 or y == board_size - 1:
        return True
    
    # Check self collision (excluding the tail which will move)
    # snake[1:] excludes the tail since it will move forward
    if new_head in snake[1:]:
        return True
    
    # Check obstacle collision
    if new_head in obstacles:
        return True
    
    return False


def check_food_collision(
    new_head: Tuple[int, int],
    food: List[Tuple[int, int]],
    food_attributes: List[List[Tuple[int, int]]]
) -> Tuple[bool, int]:
    """
    Check if the snake ate food and return the food value.
    
    Args:
        new_head: New head position
        food: List of food positions
        food_attributes: 2D array of food attributes (lifespan, value)
    
    Returns:
        Tuple of (ate_food, food_value)
    """
    if new_head in food:
        x, y = new_head
        _, value = food_attributes[x][y]
        return True, value
    return False, 0


def move_snake(
    snake: List[Tuple[int, int]],
    new_head: Tuple[int, int],
    ate_food: bool
) -> List[Tuple[int, int]]:
    """
    Move the snake to the new head position.
    
    Args:
        snake: Current snake body (tail to head)
        new_head: New head position
        ate_food: Whether the snake ate food (if True, tail stays)
    
    Returns:
        Updated snake body
    """
    new_snake = snake.copy()
    new_snake.append(new_head)
    
    if not ate_food:
        # Remove tail if didn't eat food
        new_snake.pop(0)
    
    return new_snake


def update_food_lifespans(
    food: List[Tuple[int, int]],
    food_attributes: List[List[Tuple[int, int]]]
) -> Tuple[List[Tuple[int, int]], List[List[Tuple[int, int]]]]:
    """
    Update food lifespans and remove expired food.
    
    Args:
        food: List of food positions
        food_attributes: 2D array of food attributes (lifespan, value)
    
    Returns:
        Tuple of (updated food list, updated food attributes)
    """
    new_food = []
    new_food_attributes = [row[:] for row in food_attributes]
    
    for food_pos in food:
        fx, fy = food_pos
        lifespan, value = food_attributes[fx][fy]
        
        # Decrease lifespan
        new_lifespan = lifespan - 1
        
        if new_lifespan <= 0:
            # Food expired, remove it
            new_food_attributes[fx][fy] = (0, 0)
        else:
            # Food still valid
            new_food.append(food_pos)
            new_food_attributes[fx][fy] = (new_lifespan, value)
    
    return new_food, new_food_attributes


def spawn_food(
    coords: List[Tuple[int, int]],
    idx: int,
    food: List[Tuple[int, int]],
    food_attributes: List[List[Tuple[int, int]]],
    lifespan: int = 10,
    value: int = 1
) -> Tuple[List[Tuple[int, int]], List[List[Tuple[int, int]]], int]:
    """
    Spawn a new food item on the board.
    
    Args:
        coords: List of available coordinates (shuffled)
        idx: Current index in coords list
        food: Current list of food positions
        food_attributes: 2D array of food attributes
        lifespan: Food lifespan in turns
        value: Food value (reward)
    
    Returns:
        Tuple of (updated food list, updated food attributes, new idx)
    """
    if idx >= len(coords):
        # Wrap around if we've used all coords
        idx = idx % len(coords) if coords else 0
    
    x, y = coords[idx]
    new_idx = idx + 1
    
    # Check if position is already occupied by food
    if (x, y) in food or food_attributes[x][y] != (0, 0):
        # Try next position
        if new_idx < len(coords):
            return spawn_food(coords, new_idx, food, food_attributes, lifespan, value)
        else:
            # No available positions, return unchanged
            return food, food_attributes, new_idx
    
    # Spawn food
    new_food = food.copy()
    new_food.append((x, y))
    
    new_food_attributes = [row[:] for row in food_attributes]
    new_food_attributes[x][y] = (lifespan, value)
    
    return new_food, new_food_attributes, new_idx


def remove_food(
    food: List[Tuple[int, int]],
    food_attributes: List[List[Tuple[int, int]]],
    food_pos: Tuple[int, int]
) -> Tuple[List[Tuple[int, int]], List[List[Tuple[int, int]]]]:
    """
    Remove a food item from the board.
    
    Args:
        food: Current list of food positions
        food_attributes: 2D array of food attributes
        food_pos: Position of food to remove
    
    Returns:
        Tuple of (updated food list, updated food attributes)
    """
    new_food = [f for f in food if f != food_pos]
    new_food_attributes = [row[:] for row in food_attributes]
    
    x, y = food_pos
    new_food_attributes[x][y] = (0, 0)
    
    return new_food, new_food_attributes


def should_spawn_food(game_turn: int, spawn_interval: int = 3) -> bool:
    """
    Check if a new food should be spawned based on game turn.
    
    Args:
        game_turn: Current game turn number
        spawn_interval: Interval between food spawns
    
    Returns:
        True if food should be spawned, False otherwise
    """
    return game_turn % spawn_interval == 1


def get_possible_actions(current_dir: str) -> List[str]:
    """
    Get list of possible actions based on current direction.
    
    Args:
        current_dir: Current direction ("L", "R", "U", "D")
    
    Returns:
        List of valid directions (excluding reverse)
    """
    if current_dir == "L":
        return ["L", "U", "D", "W"]
    elif current_dir == "R":
        return ["R", "U", "D", "W"]
    elif current_dir == "U":
        return ["L", "R", "U", "W"]
    elif current_dir == "D":
        return ["L", "R", "D", "W"]
    else:
        return ["L", "R", "U", "D", "W"]


def initialize_game_coords(
    board_size: int,
    snake: List[Tuple[int, int]],
    obstacles: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """
    Initialize the list of available coordinates for food spawning.
    
    Args:
        board_size: Size of the game board
        snake: Initial snake positions
        obstacles: List of obstacle positions
    
    Returns:
        List of available coordinates (excluding snake, obstacles, and borders)
    """
    coords = [
        (x, y) 
        for x in range(1, board_size - 1) 
        for y in range(1, board_size - 1)
    ]
    
    # Remove snake positions
    for pos in snake:
        if pos in coords:
            coords.remove(pos)
    
    # Remove obstacle positions
    for pos in obstacles:
        if pos in coords:
            coords.remove(pos)
    
    return coords


def generate_obstacles(
    board_size: int,
    num_obstacles: int,
    snake: List[Tuple[int, int]],
    random_state: np.random.RandomState
) -> List[Tuple[int, int]]:
    """
    Generate random obstacles on the board.
    
    Args:
        board_size: Size of the game board
        num_obstacles: Number of obstacles to generate
        snake: Current snake positions (to avoid)
        random_state: NumPy random state for reproducibility
    
    Returns:
        List of obstacle positions
    """
    obstacles = []
    attempts = 0
    max_attempts = num_obstacles * 10  # Prevent infinite loop
    
    while len(obstacles) < num_obstacles and attempts < max_attempts:
        x = random_state.randint(1, board_size - 1)
        y = random_state.randint(1, board_size - 1)
        pos = (x, y)
        
        if pos not in snake and pos not in obstacles:
            obstacles.append(pos)
        
        attempts += 1
    
    if len(obstacles) < num_obstacles:
        raise ValueError(
            f"Could not generate enough obstacles: {len(obstacles)} < {num_obstacles}"
        )
    
    return obstacles
