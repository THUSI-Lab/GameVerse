"""
Snake Game - Core game logic and state management.

This module provides the SnakeGame class which manages game state and supports
two modes:
- discrete: Step-by-step execution, waiting for actions
- realtime: Continuous automatic movement with queued direction changes
"""

from copy import deepcopy
from typing import Any, Optional, List, Tuple
import numpy as np
import threading
import queue
import time
import json
import os
import pygame

from . import logic
from .render import SnakeRender


def load_constants():
    """Load game constants from constants.json"""
    constants_path = os.path.join(os.path.dirname(__file__), "constants.json")
    with open(constants_path, 'r') as f:
        return json.load(f)


CONSTANTS = load_constants()


class SnakeGame:
    """
    Snake game with support for discrete and realtime modes.
    
    In discrete mode, the game progresses step-by-step with explicit actions.
    In realtime mode, the snake moves automatically at regular intervals.
    """
    
    def __init__(
        self, 
        board_size: Optional[int] = None,
        seed: Optional[int] = None,
        num_obstacles: Optional[int] = None,
        mode: str = "discrete",
        action_timeout: Optional[float] = None,
        max_duration: Optional[float] = None
    ):
        """
        Initialize the snake game.
        
        Args:
            board_size: Size of the game board (default from constants)
            seed: Random seed for reproducibility (default from constants)
            num_obstacles: Number of obstacles on the board (default from constants)
            mode: Game mode - "discrete" or "realtime"
            action_timeout: Timeout for LLM action in realtime mode (seconds)
            max_duration: Maximum game duration in realtime mode (default from constants)
        """
        # Load defaults from constants
        game_params = CONSTANTS.get("game_params", {})
        realtime_params = CONSTANTS.get("realtime_params", {})
        
        self.B = board_size or CONSTANTS.get("board_size", 8)
        seed = seed if seed is not None else game_params.get("default_seed", 42)
        self.true_seed = seed % 1000
        self.random = np.random.RandomState(self.true_seed)
        self.num_obstacle = num_obstacles if num_obstacles is not None else game_params.get("default_num_obstacles", 0)
        
        # Game state
        self.snake: List[Tuple[int, int]] = []
        self.obstacle: List[Tuple[int, int]] = []
        self.food: List[Tuple[int, int]] = []
        self.food_attributes: List[List[Tuple[int, int]]] = []
        self.coords: List[Tuple[int, int]] = []
        self.dir = "L"  # Initial direction: Left
        self.game_turn = 0
        self.reward = 0
        self.terminal = False
        self.idx = 0
        
        # Game parameters
        self.death_penalty = game_params.get("death_penalty", -1)
        self.food_spawn_interval = game_params.get("food_spawn_interval", 3)
        self.food_lifespan = game_params.get("food_lifespan", 10)
        self.food_value = game_params.get("food_value", 1)
        self.max_turns = game_params.get("max_turns_discrete", 100)
        
        # Mode and realtime settings
        self.mode = mode
        self.action_timeout = action_timeout or realtime_params.get("action_timeout", 20.0)
        self.max_duration = max_duration or realtime_params.get("max_duration", 60.0)
        
        # Realtime mode attributes
        self.game_thread: Optional[threading.Thread] = None
        self.running = False
        self.game_lock = threading.Lock()
        action_queue_size = realtime_params.get("action_queue_size", 10)
        self.action_queue: queue.Queue = queue.Queue(maxsize=action_queue_size)
        
        # Realtime timing
        self.start_time = 0.0
        self.real_time_elapsed = 0.0
        self.auto_move_count = 0
        
        # Pygame window management (for GUI mode)
        self.screen = None
        self.renderer = None
        self.clock = None
        self.window_title = "Snake Game"
        self._game_started = False
        
    def reset(self):
        """Reset the game to initial state"""
        # Stop realtime thread if running
        self.stop_game_loop()
        
        # Initialize snake at center
        center_offset = CONSTANTS.get("game_params", {}).get("initial_snake_pos_offset", 1)
        initial_pos = (self.B // 2 - center_offset, self.B // 2 - center_offset)
        self.snake = [initial_pos]
        
        # Generate obstacles
        self.obstacle = logic.generate_obstacles(
            self.B, self.num_obstacle, self.snake, self.random
        )
        
        # Initialize available coordinates for food spawning
        self.coords = logic.initialize_game_coords(self.B, self.snake, self.obstacle)
        
        # Shuffle coords for randomness
        self.random.shuffle(self.coords)
        self.random.shuffle(self.coords)
        
        # Initialize food
        self.food = []
        self.food_attributes = [[( 0, 0) for _ in range(self.B)] for _ in range(self.B)]
        self.idx = 0
        
        # Reset game state
        self.dir = "L"
        self.game_turn = 0
        self.reward = 0
        self.terminal = False
        self.auto_move_count = 0
        self.real_time_elapsed = 0.0
        
        # Clear action queue
        while not self.action_queue.empty():
            try:
                self.action_queue.get_nowait()
            except queue.Empty:
                break
        
        # Spawn initial food
        self._spawn_food()
        self._spawn_food()
        self._spawn_food()
        
        # 不在环境初始化的时候启动游戏循环，在env内手动启动
        # if self.mode == "realtime":
        #     self.start_game_loop()
    
    def start(self, window_title: Optional[str] = None):
        """Start the game with pygame window (for GUI environment)"""
        if self._game_started:
            return
        
        # Initialize pygame
        if not pygame.get_init():
            pygame.init()
        
        # Set window title
        if window_title:
            self.window_title = window_title
        else:
            self.window_title = f"Snake Game - {self.mode.title()} Mode"
        
        # Calculate window size
        cell_size = 500 // self.B
        self.renderer = SnakeRender(cell_size=cell_size, board_size=self.B)
        
        width = self.B * cell_size
        height = width + self.renderer.ui_panel_height
        
        # Create pygame window
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(self.window_title)
        self.clock = pygame.time.Clock()
        
        # Reset and start game
        self.reset()
        
        self._game_started = True
        
        # Initial render
        self._render()
    
    def stop(self):
        """Stop the game and close pygame window"""
        if not self._game_started:
            return
        
        # Stop game loop if running (for realtime mode)
        self.stop_game_loop()
        
        # Close pygame
        if pygame.get_init():
            pygame.quit()
        
        self._game_started = False
    
    def _render(self):
        """Render the game state to the pygame window"""
        if not self._game_started or self.screen is None or self.renderer is None:
            return
        
        # Render game
        rendered_surface = self.renderer.render(self)
        self.screen.blit(rendered_surface, (0, 0))
        pygame.display.flip()
        
        if self.clock:
            self.clock.tick(30)
    
    def process_events(self) -> bool:
        """Process pygame events (for keyboard input in GUI mode)
        
        Returns:
            True if game should continue, False if quit requested
        """
        if not self._game_started:
            return True
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                # Handle keyboard input in discrete mode
                if self.mode == "discrete" and not self.terminal:
                    action = None
                    if event.key == pygame.K_LEFT:
                        action = "L"
                    elif event.key == pygame.K_RIGHT:
                        action = "R"
                    elif event.key == pygame.K_UP:
                        action = "U"
                    elif event.key == pygame.K_DOWN:
                        action = "D"
                    elif event.key == pygame.K_SPACE:
                        action = "W"
                    
                    if action:
                        self.step(action)
                        self._render()
                # In realtime mode, queue direction changes
                elif self.mode == "realtime" and not self.terminal:
                    if event.key == pygame.K_LEFT:
                        self.queue_direction("L")
                    elif event.key == pygame.K_RIGHT:
                        self.queue_direction("R")
                    elif event.key == pygame.K_UP:
                        self.queue_direction("U")
                    elif event.key == pygame.K_DOWN:
                        self.queue_direction("D")
        
        # Auto-render in realtime mode
        if self.mode == "realtime":
            self._render()
        
        return True
    
    def _spawn_food(self) -> None:
        """Spawn a new food item on the board"""
        self.food, self.food_attributes, self.idx = logic.spawn_food(
            self.coords,
            self.idx,
            self.food,
            self.food_attributes,
            self.food_lifespan,
            self.food_value
        )
    
    def start_game_loop(self):
        """Start the realtime game loop in a separate thread"""
        if self.mode != "realtime":
            return
        
        if self.running:
            return  # Already running
        
        self.running = True
        self.start_time = time.time()
        self.game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_thread.start()
    
    def stop_game_loop(self):
        """Stop the realtime game loop"""
        if self.running:
            self.running = False
            # Put a sentinel value to unblock waiting thread
            try:
                self.action_queue.put_nowait(None)
            except queue.Full:
                pass
            if self.game_thread and self.game_thread.is_alive():
                self.game_thread.join(timeout=2.0)
    
    def _game_loop(self):
        """Main game loop for realtime mode (runs in separate thread)
        
        New behavior: Wait for LLM action with timeout. If action received,
        execute immediately. If timeout, execute move with current direction.
        """
        while self.running and not self.terminal:
            # Update elapsed time
            current_time = time.time()
            self.real_time_elapsed = current_time - self.start_time
            
            # Check time limit first
            if self.real_time_elapsed >= self.max_duration:
                with self.game_lock:
                    self.terminal = True
                break
            
            # Wait for action with timeout (blocking)
            new_direction = None
            try:
                # Block until action received or timeout
                new_direction = self.action_queue.get(timeout=self.action_timeout)
                
                # Check for sentinel value (for clean shutdown)
                if new_direction is None:
                    break
                    
            except queue.Empty:
                # Timeout: no action received, use current direction
                new_direction = self.dir
                self.auto_move_count += 1
            
            # Update direction if valid
            if new_direction and logic.is_valid_direction_change(self.dir, new_direction):
                with self.game_lock:
                    self.dir = new_direction
            
            # Execute move
            with self.game_lock:
                self._execute_move(self.dir)
                
        # Clean up: drain the queue
        while not self.action_queue.empty():
            try:
                self.action_queue.get_nowait()
            except queue.Empty:
                break
    
    def queue_direction(self, direction: str):
        """
        Queue a direction change for realtime mode.
        
        Args:
            direction: Direction to queue ("L", "R", "U", "D", "W")
        """
        if self.mode != "realtime":
            return
        
        if direction in ["L", "R", "U", "D", "W"]:
            try:
                self.action_queue.put_nowait(direction)
            except queue.Full:
                pass  # Queue full, skip this action
    
    def _execute_move(self, action: str) -> float:
        """
        Execute one move (internal method, assumes lock is held in realtime mode).
        
        Args:
            action: Direction to move ("L", "R", "U", "D", "W")
        
        Returns:
            Reward for this move
        """
        step_reward = 0
        self.game_turn += 1
        
        # Handle wait action
        if action == "W":
            # Don't move, just update food and check spawn
            self._update_food_lifecycle()
            if logic.should_spawn_food(self.game_turn, self.food_spawn_interval):
                self._spawn_food()
            return step_reward
        
        # Update direction
        if action in ["L", "R", "U", "D"]:
            self.dir = action
        
        # Calculate new head position
        head = self.snake[-1]
        new_head = logic.calculate_new_head(head, self.dir)
        
        # Check for collision
        if logic.check_collision(new_head, self.snake, self.obstacle, self.B):
            # Don't apply death penalty to avoid negative final score
            # step_reward = self.death_penalty
            # self.reward += step_reward
            self.terminal = True
            return step_reward
        
        # Check if food is eaten
        ate_food, food_value = logic.check_food_collision(
            new_head, self.food, self.food_attributes
        )
        
        if ate_food:
            step_reward += food_value
            self.food, self.food_attributes = logic.remove_food(
                self.food, self.food_attributes, new_head
            )
        
        # Move snake
        self.snake = logic.move_snake(self.snake, new_head, ate_food)
        
        # Update food lifespans
        self._update_food_lifecycle()
        
        # Spawn new food periodically
        if logic.should_spawn_food(self.game_turn, self.food_spawn_interval):
            self._spawn_food()
        
        self.reward += step_reward
        
        # Check turn limit (only in discrete mode)
        if self.mode == "discrete" and self.game_turn >= self.max_turns:
            self.terminal = True
        
        return step_reward
    
    def _update_food_lifecycle(self):
        """Update food lifespans and remove expired food"""
        self.food, self.food_attributes = logic.update_food_lifespans(
            self.food, self.food_attributes
        )
    
    def step(self, action: str) -> Tuple[float, bool]:
        """
        Execute one step in the game (discrete mode only).
        
        Args:
            action: Direction to move ("L", "R", "U", "D", "W")
            
        Returns:
            Tuple of (reward, terminal)
        """
        if self.mode == "realtime":
            raise RuntimeError(
                "step() should not be called in realtime mode. Use queue_direction() instead."
            )
        
        # Validate and adjust action if it's a reverse move
        if not logic.is_valid_direction_change(self.dir, action):
            action = self.dir  # Keep current direction if invalid
        
        # Execute move
        step_reward = self._execute_move(action)
        
        return step_reward, self.terminal
    
    def get_state(self) -> dict[str, Any]:
        """Get a thread-safe snapshot of the current game state"""
        if self.mode == "realtime":
            with self.game_lock:
                return self._build_state_snapshot()
        else:
            return self._build_state_snapshot()
    
    def _build_state_snapshot(self) -> dict[str, Any]:
        """Build state snapshot (must be called with lock in realtime mode)"""
        snake = deepcopy(self.snake[::-1])  # Reverse: head to tail
        foods = []
        for x, y in self.food:
            lifespan, value = self.food_attributes[x][y]
            foods.append((x, y, lifespan, value))
        
        return {
            "snake_dir": self.dir,
            "internal_obstacles": self.obstacle,
            "foods": foods,
            "snake": snake,
            "size": self.B,
            "game_turn": self.game_turn,
            "terminal": self.terminal,
            "reward": self.reward,
            "mode": self.mode,
            "real_time_elapsed": self.real_time_elapsed,
            "auto_move_count": self.auto_move_count,
            "action_timeout": self.action_timeout,
        }
    
    def state_string(self) -> str:
        """Generate a string representation of the game state"""
        grid_string = ""
        snake_length = len(self.snake)
        
        for i in range(self.B):
            for j in range(self.B):
                output = ""
                x, y = j, self.B - 1 - i
                
                # Check boundaries (walls)
                if x == 0 or x == self.B - 1 or y == 0 or y == self.B - 1:
                    output += "#"
                
                # Check obstacles
                if (x, y) in self.obstacle:
                    output += "#"
                
                # Check snake
                if (x, y) in self.snake:
                    snake_idx = self.snake.index((x, y))
                    output += chr(ord("a") + snake_length - 1 - snake_idx)
                
                # Check food
                if (x, y) in self.food:
                    lifespan, value = self.food_attributes[x][y]
                    if value > 0:
                        output += "+"
                    else:
                        output += "-"
                    output += str(lifespan)
                
                if output == "":
                    output = "."
                
                grid_string += output + " " * (6 - len(output))
            grid_string += "\n"
        
        return grid_string
    
    def get_possible_actions(self) -> List[str]:
        """Get list of possible actions (excluding reverse direction)"""
        return logic.get_possible_actions(self.dir)
    
    def state_builder(self) -> dict[str, Any]:
        """Build a structured state representation"""
        return self.get_state()
