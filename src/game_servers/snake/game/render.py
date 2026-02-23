"""
Snake Game Renderer - Enhanced rendering with sprites and UI panel.

This module provides independent rendering functionality that is completely
decoupled from game logic. It reads configuration from constants.json.
"""

import os
import json
from typing import Any, Optional

import pygame
from PIL import Image


def load_constants():
    """Load rendering constants from constants.json"""
    constants_path = os.path.join(os.path.dirname(__file__), "constants.json")
    with open(constants_path, 'r') as f:
        return json.load(f)


CONSTANTS = load_constants()


class SnakeRender:
    """Enhanced snake game renderer with sprites"""
    
    def __init__(
        self, 
        cell_size: Optional[int] = None,
        board_size: Optional[int] = None
    ) -> None:
        """
        Initialize the renderer.
        
        Args:
            cell_size: Size of each cell in pixels (default from constants)
            board_size: Size of the game board (default from constants)
        """
        self.cell_size = cell_size or CONSTANTS.get("cell_size", 60)
        self.board_size = board_size or CONSTANTS.get("board_size", 8)
        
        # Get assets path from constants
        base_dir = os.path.dirname(os.path.abspath(__file__))
        assets_relative_path = CONSTANTS.get("assets_path", "assets/snake")
        self.assets_path = os.path.join(base_dir, assets_relative_path)
        
        self.width = self.board_size * self.cell_size
        self.height = self.board_size * self.cell_size
        
        # UI panel settings from constants
        self.ui_panel_height = CONSTANTS.get("ui_panel_height", 100)
        self.total_height = self.height + self.ui_panel_height
        
        # Colors from constants
        self.colors = CONSTANTS.get("colour", {})

        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()
        
        # Fonts
        font_name = CONSTANTS.get("font", "Arial")
        font_size = CONSTANTS.get("font_size", 28)
        title_font_size = CONSTANTS.get("title_font_size", 36)
        
        try:
            self.font = pygame.font.SysFont(font_name, font_size)
            self.title_font = pygame.font.SysFont(font_name, title_font_size)
        except:
            self.font = pygame.font.Font(None, font_size)
            self.title_font = pygame.font.Font(None, title_font_size)
        
        self.sprites = {}
        self.snake_sprites = {}
        self.load_sprites()

    def load_sprites(self) -> None:
        """Load all sprite images from assets directory"""
        sprite_files = CONSTANTS.get("sprite_files", {
            "apple": "apple.png",
            "wall": "brick-wall.png",
            "obstacle": "brick-wall.png",
            "head": "head.png",
        })

        for name, filename in sprite_files.items():
            filepath = os.path.join(self.assets_path, filename)
            if name == "head":
                self._load_head_sprites(filepath)
            elif os.path.exists(filepath):
                sprite = pygame.image.load(filepath)
                sprite = pygame.transform.scale(
                    sprite, (self.cell_size, self.cell_size)
                )
                self.sprites[name] = sprite
            else:
                # Fallback: create simple colored rectangle if sprite not found
                self.sprites[name] = self._create_fallback_sprite(name)

        # Load snake body/tail sprites
        self._load_snake_sprites()
    
    def _load_head_sprites(self, filepath: str) -> None:
        """Load and rotate head sprites"""
        if os.path.exists(filepath):
            head_base = pygame.image.load(filepath)
            head_base = pygame.transform.scale(
                head_base, (self.cell_size, self.cell_size)
            )
            self.sprites["head_down"] = head_base
            self.sprites["head_up"] = pygame.transform.rotate(head_base, 180)
            self.sprites["head_left"] = pygame.transform.rotate(head_base, -90)
            self.sprites["head_right"] = pygame.transform.rotate(head_base, 90)
        else:
            # Fallback head sprites
            for direction in ["up", "down", "left", "right"]:
                self.sprites[f"head_{direction}"] = self._create_fallback_sprite("head")
    
    def _load_snake_sprites(self) -> None:
        """Load snake body sprite sheet"""
        snake_path = os.path.join(self.assets_path, "snake.png")
        
        if os.path.exists(snake_path):
            snake_sheet = pygame.image.load(snake_path)
            sheet_width, sheet_height = snake_sheet.get_size()
            sprite_width = sheet_width // 2
            sprite_height = sheet_height // 2

            # Extract head sprite
            head_rect = pygame.Rect(0, 0, sprite_width, sprite_height)
            head_sprite = snake_sheet.subsurface(head_rect)
            head_sprite = pygame.transform.scale(
                head_sprite, (self.cell_size, self.cell_size)
            )

            # Extract straight body sprite
            straight_rect = pygame.Rect(sprite_width, 0, sprite_width, sprite_height)
            straight_sprite = snake_sheet.subsurface(straight_rect)
            straight_sprite = pygame.transform.scale(
                straight_sprite, (self.cell_size, self.cell_size)
            )

            # Extract tail sprite
            tail_rect = pygame.Rect(0, sprite_height, sprite_width, sprite_height)
            tail_sprite = snake_sheet.subsurface(tail_rect)
            tail_sprite = pygame.transform.scale(
                tail_sprite, (self.cell_size, self.cell_size)
            )

            # Extract turn sprite
            turn_rect = pygame.Rect(
                sprite_width, sprite_height, sprite_width, sprite_height
            )
            turn_sprite = snake_sheet.subsurface(turn_rect)
            turn_sprite = pygame.transform.scale(
                turn_sprite, (self.cell_size, self.cell_size)
            )
            
            # Generate all rotations
            self.snake_sprites["head_up"] = head_sprite
            self.snake_sprites["head_right"] = pygame.transform.rotate(head_sprite, -90)
            self.snake_sprites["head_down"] = pygame.transform.rotate(head_sprite, 180)
            self.snake_sprites["head_left"] = pygame.transform.rotate(head_sprite, 90)

            self.snake_sprites["tail_left"] = tail_sprite
            self.snake_sprites["tail_up"] = pygame.transform.rotate(tail_sprite, -90)
            self.snake_sprites["tail_right"] = pygame.transform.rotate(tail_sprite, 180)
            self.snake_sprites["tail_down"] = pygame.transform.rotate(tail_sprite, 90)
            
            self.snake_sprites["straight_vertical"] = straight_sprite
            self.snake_sprites["straight_horizontal"] = pygame.transform.rotate(
                straight_sprite, 90
            )
            self.snake_sprites["turn_up_left"] = turn_sprite
            self.snake_sprites["turn_up_right"] = pygame.transform.rotate(
                turn_sprite, -90
            )
            self.snake_sprites["turn_down_right"] = pygame.transform.rotate(
                turn_sprite, 180
            )
            self.snake_sprites["turn_down_left"] = pygame.transform.rotate(
                turn_sprite, 90
            )
        else:
            # Fallback: create simple colored snake sprites
            self._create_fallback_snake_sprites()
    
    def _create_fallback_sprite(self, sprite_type: str) -> pygame.Surface:
        """Create fallback colored sprite"""
        sprite = pygame.Surface((self.cell_size, self.cell_size))
        
        if sprite_type == "apple":
            sprite.fill(tuple(self.colors.get("food", [220, 20, 60])))
        elif sprite_type in ["wall", "obstacle"]:
            sprite.fill(tuple(self.colors.get("wall", [101, 67, 33])))
        elif sprite_type == "head":
            sprite.fill(tuple(self.colors.get("snake_head", [0, 100, 0])))
        else:
            sprite.fill((100, 100, 100))
        
        return sprite
    
    def _create_fallback_snake_sprites(self) -> None:
        """Create fallback snake sprites without sprite sheet"""
        head_color = tuple(self.colors.get("snake_head", [0, 100, 0]))
        body_color = tuple(self.colors.get("snake_body", [50, 205, 50]))
        
        for direction in ["up", "down", "left", "right"]:
            head_sprite = pygame.Surface((self.cell_size, self.cell_size))
            head_sprite.fill(head_color)
            self.snake_sprites[f"head_{direction}"] = head_sprite
            
            tail_sprite = pygame.Surface((self.cell_size, self.cell_size))
            tail_sprite.fill(body_color)
            self.snake_sprites[f"tail_{direction}"] = tail_sprite
        
        body_sprite = pygame.Surface((self.cell_size, self.cell_size))
        body_sprite.fill(body_color)
        self.snake_sprites["straight_vertical"] = body_sprite
        self.snake_sprites["straight_horizontal"] = body_sprite
        
        for turn in ["turn_up_left", "turn_up_right", "turn_down_right", "turn_down_left"]:
            self.snake_sprites[turn] = body_sprite

    def get_snake_body_sprite(
        self,
        prev_pos: Optional[tuple[int, int]],
        curr_pos: tuple[int, int],
        next_pos: Optional[tuple[int, int]],
    ) -> pygame.Surface:
        """Get the appropriate sprite for a snake body segment"""
        if prev_pos is None or next_pos is None:
            return self.snake_sprites["straight_horizontal"]

        prev_x, prev_y = prev_pos
        curr_x, curr_y = curr_pos
        next_x, next_y = next_pos
        from_dir = (prev_x - curr_x, prev_y - curr_y)
        to_dir = (next_x - curr_x, next_y - curr_y)

        # Straight segments
        if from_dir[0] == 0 and to_dir[0] == 0:  # Vertical
            return self.snake_sprites["straight_vertical"]
        elif from_dir[1] == 0 and to_dir[1] == 0:  # Horizontal
            return self.snake_sprites["straight_horizontal"]

        # Turn segments
        dirs = sorted([from_dir, to_dir])
        if dirs == [(-1, 0), (0, 1)]:
            return self.snake_sprites["turn_up_left"]
        elif dirs == [(0, 1), (1, 0)]:
            return self.snake_sprites["turn_up_right"]
        elif dirs == [(0, -1), (1, 0)]:
            return self.snake_sprites["turn_down_right"]
        elif dirs == [(-1, 0), (0, -1)]:
            return self.snake_sprites["turn_down_left"]

        return self.snake_sprites["straight_horizontal"]

    def get_snake_tail_sprite(
        self, 
        prev_pos: Optional[tuple[int, int]], 
        curr_pos: tuple[int, int]
    ) -> pygame.Surface:
        """Get the appropriate sprite for the snake tail"""
        if prev_pos is None:
            return self.snake_sprites["tail_left"]

        prev_x, prev_y = prev_pos
        curr_x, curr_y = curr_pos
        direction = (curr_x - prev_x, curr_y - prev_y)

        direction_map = {
            (1, 0): "tail_right",
            (-1, 0): "tail_left",
            (0, 1): "tail_up",
            (0, -1): "tail_down",
        }

        return self.snake_sprites.get(
            direction_map.get(direction, "tail_left"),
            self.snake_sprites["tail_left"],
        )

    def render(self, game: Any) -> pygame.Surface:
        """
        Render the game state to a pygame surface.
        
        Args:
            game: Game object with snake, food, obstacles, etc.
        
        Returns:
            pygame.Surface with rendered game and UI panel
        """
        # Create full surface with UI panel
        info_panel_bg = tuple(self.colors.get("info_panel_bg", [40, 40, 40]))
        full_surface = pygame.Surface((self.width, self.total_height))
        full_surface.fill(info_panel_bg)
        
        # Create game board surface
        bg_color = tuple(self.colors.get("background", [34, 139, 34]))
        board_surface = pygame.Surface((self.width, self.height))
        board_surface.fill(bg_color)
        
        # Draw grid background
        self._draw_grid(board_surface, game.B)
        
        # Draw walls (borders)
        self._draw_walls(board_surface, game.B)
        
        # Draw obstacles
        self._draw_obstacles(board_surface, game.obstacle, game.B)
        
        # Draw food
        self._draw_food(board_surface, game.food, game.food_attributes, game.B)
        
        # Draw snake
        self._draw_snake(board_surface, game.snake, game.dir, game.B)
        
        # Blit game board to full surface
        full_surface.blit(board_surface, (0, 0))
        
        # Draw UI panel below the game board
        self.draw_ui_panel(full_surface, game)
        
        return full_surface
    
    def _draw_grid(self, surface: pygame.Surface, board_size: int) -> None:
        """Draw checkerboard grid pattern"""
        grid_color = tuple(self.colors.get("grid_line", [46, 125, 50]))
        
        for i in range(board_size):
            for j in range(board_size):
                # Skip borders
                if i == 0 or i == board_size - 1 or j == 0 or j == board_size - 1:
                    continue
                
                pos = pygame.Rect(
                    j * self.cell_size,
                    (board_size - 1 - i) * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                )
                
                # Checkerboard pattern
                if (i + j) % 2 == 0:
                    # Slightly lighter
                    lighter = tuple(min(c + 26, 255) for c in self.colors.get("background", [34, 139, 34]))
                    surface.fill(lighter, pos)
    
    def _draw_walls(self, surface: pygame.Surface, board_size: int) -> None:
        """Draw wall borders"""
        for i in range(board_size):
            for j in range(board_size):
                if i == 0 or i == board_size - 1 or j == 0 or j == board_size - 1:
                    pos = (j * self.cell_size, (board_size - 1 - i) * self.cell_size)
                    surface.blit(self.sprites["wall"], pos)
    
    def _draw_obstacles(
        self, 
        surface: pygame.Surface, 
        obstacles: list,
        board_size: int
    ) -> None:
        """Draw obstacles"""
        for x, y in obstacles:
            pos = (x * self.cell_size, (board_size - 1 - y) * self.cell_size)
            surface.blit(self.sprites["obstacle"], pos)
    
    def _draw_food(
        self,
        surface: pygame.Surface,
        food: list,
        food_attributes: list,
        board_size: int
    ) -> None:
        """Draw food items with life bars"""
        for x, y in food:
            pos = (x * self.cell_size, (board_size - 1 - y) * self.cell_size)
            if food_attributes[x][y][1] > 0:
                surface.blit(self.sprites["apple"], pos)
                life = food_attributes[x][y][0]
                self.draw_life_bar(surface, life, 10, pos)
    
    def _draw_snake(
        self,
        surface: pygame.Surface,
        snake: list,
        direction: str,
        board_size: int
    ) -> None:
        """Draw the snake with appropriate sprites"""
        direction_map = {
            "R": "right",
            "D": "down",
            "L": "left",
            "U": "up",
        }
        
        for i, (x, y) in enumerate(snake):
            pos = (x * self.cell_size, (board_size - 1 - y) * self.cell_size)
            
            if i == len(snake) - 1:
                # Head
                dir_name = direction_map.get(direction, "up")
                if len(snake) == 1:
                    # Use fallback head sprite for single segment
                    head_sprite = self.sprites.get(f"head_{dir_name}", 
                                                   self.snake_sprites[f"head_{dir_name}"])
                else:
                    head_sprite = self.snake_sprites[f"head_{dir_name}"]
                surface.blit(head_sprite, pos)
            elif i == 0:
                # Tail
                prev_pos = snake[1] if len(snake) > 1 else None
                tail_sprite = self.get_snake_tail_sprite(prev_pos, (x, y))
                surface.blit(tail_sprite, pos)
            else:
                # Body
                prev_pos = snake[i + 1] if i < len(snake) - 1 else None
                next_pos = snake[i - 1] if i > 0 else None
                body_sprite = self.get_snake_body_sprite(prev_pos, (x, y), next_pos)
                surface.blit(body_sprite, pos)

    def draw_life_bar(
        self,
        surface: pygame.Surface,
        life: int,
        max_life: int,
        pos: tuple[int, int],
    ) -> None:
        """Draw a life bar for food items"""
        bar_width = self.cell_size - 4
        bar_height = 6
        bar_x = pos[0] + 2
        bar_y = pos[1] + 10

        # Background
        background_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(surface, (100, 0, 0), background_rect)

        # Life bar
        life_ratio = max(0, life / max_life)
        if life_ratio > 0:
            life_width = int(bar_width * life_ratio)
            life_rect = pygame.Rect(bar_x, bar_y, life_width, bar_height)

            # Color based on remaining life
            if life_ratio > 0.6:
                color = (0, 255, 0)
            elif life_ratio > 0.3:
                color = (255, 255, 0)
            else:
                color = (255, 0, 0)

            pygame.draw.rect(surface, color, life_rect)

        # Border
        pygame.draw.rect(surface, (255, 255, 255), background_rect, 1)

    def draw_ui_panel(self, surface: pygame.Surface, game: Any) -> None:
        """Draw independent UI panel below the game board"""
        panel_y = self.height
        text_color = tuple(self.colors.get("text", [255, 255, 255]))
        
        # Draw panel background with border
        panel_rect = pygame.Rect(0, panel_y, self.width, self.ui_panel_height)
        info_panel_bg = tuple(self.colors.get("info_panel_bg", [40, 40, 40]))
        pygame.draw.rect(surface, info_panel_bg, panel_rect)
        pygame.draw.rect(surface, (100, 100, 100), panel_rect, 2)  # Border
        
        # Prepare info text based on game mode
        if game.mode == "realtime":
            left_info = [
                f"Mode: Real-time",
                f"Score: {game.reward}",
            ]
            right_info = [
                f"Time: {game.real_time_elapsed:.1f}s / {game.max_duration:.0f}s",
                f"Action Timeout: {game.action_timeout:.1f}",
            ]
        else:
            left_info = [
                f"Mode: Discrete",
                f"Score: {game.reward}",
            ]
            right_info = [
                f"Turn: {game.game_turn} / {getattr(game, 'max_turns', 100)}",
                f"Length: {len(game.snake)}",
            ]
        
        # Draw left column
        y_offset = panel_y + 15
        for line in left_info:
            text_surface = self.font.render(line, True, text_color)
            surface.blit(text_surface, (15, y_offset))
            y_offset += 35
        
        # Draw right column
        y_offset = panel_y + 15
        for line in right_info:
            text_surface = self.font.render(line, True, (200, 200, 200))
            text_rect = text_surface.get_rect()
            text_rect.topright = (self.width - 15, y_offset)
            surface.blit(text_surface, text_rect)
            y_offset += 35
        
        # Draw game over overlay on the game board (not UI panel)
        if game.terminal:
            self._draw_game_over(surface, game)
    
    def _draw_game_over(self, surface: pygame.Surface, game: Any) -> None:
        """Draw game over overlay"""
        if game.mode == "realtime":
            if game.real_time_elapsed >= game.max_duration:
                end_text = f"TIME UP! SCORE: {game.reward}"
                color = (255, 165, 0)  # Orange
            else:
                end_text = f"GAME OVER! SCORE: {game.reward}"
                color = (255, 0, 0)
        else:
            max_turns = getattr(game, 'max_turns', 100)
            if game.game_turn < max_turns:
                end_text = f"GAME OVER! REWARD: {game.reward}"
                color = (255, 0, 0)
            else:
                end_text = f"COMPLETED! REWARD: {game.reward}"
                color = (0, 255, 0)

        end_surface = self.title_font.render(end_text, True, color)
        end_rect = end_surface.get_rect()
        end_rect.center = (self.width // 2, self.height // 2)

        # Semi-transparent overlay only on game board
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))
        
        # Draw game over text with shadow
        shadow_surface = self.title_font.render(end_text, True, (0, 0, 0))
        shadow_rect = shadow_surface.get_rect()
        shadow_rect.center = (end_rect.centerx + 2, end_rect.centery + 2)
        surface.blit(shadow_surface, shadow_rect)
        surface.blit(end_surface, end_rect)

    def render_to_pil(self, game: Any) -> Image.Image:
        """
        Render the game state to a PIL Image.
        
        Args:
            game: Game object
        
        Returns:
            PIL Image of the rendered game
        """
        # Ensure pygame is initialized
        if not pygame.get_init():
            pygame.init()
        
        pygame_surface = self.render(game)
        # Convert pygame surface to PIL Image
        img_string = pygame.image.tostring(pygame_surface, "RGB", False)
        img = Image.frombytes("RGB", pygame_surface.get_size(), img_string)
        return img
