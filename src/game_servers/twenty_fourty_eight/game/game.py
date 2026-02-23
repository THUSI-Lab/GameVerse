import json
import sys
import time
from copy import deepcopy

import pygame
from pygame.locals import *

from game_servers.twenty_fourty_eight.game.logic import *
import os
import yaml

base_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(base_dir)
config_path = os.path.join(base_dir, "config.yaml")

with open(config_path, "r") as file:
    config = yaml.safe_load(file)

if config.get("env", {}).get("show_graphic", True):
    # show_graphic
    # set up pygame for main gameplay
    pygame.init()
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    constants_path = os.path.join(BASE_DIR, "constants.json")
    c = json.load(open(constants_path, "r"))
    screen = pygame.display.set_mode(
        (c["size"], c["size"]))
    my_font = pygame.font.SysFont(c["font"], c["font_size"], bold=True)
    WHITE = (255, 255, 255)

def winCheck(board, status, theme, text_col, size):
    """
    Check game status and display win/lose result.

    Parameters:
        board (list): game board
        status (str): game status
        theme (str): game interface theme
        text_col (tuple): text colour
        size (tuple): (width, height) of the game window
    Returns:
        board (list): updated game board
        status (str): game status
    """
    if status != "PLAY":
        # Create a transparent overlay
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill(c["colour"][theme]["over"])
        screen.blit(s, (0, 0))

        # Dynamically adjust font sizes
        title_font_size = max(size[0] // 10, 36)  # Scale with screen width
        subtitle_font_size = max(size[0] // 20, 24)  # Slightly smaller for prompts

        title_font = pygame.font.SysFont(c["font"], title_font_size, bold=True)
        subtitle_font = pygame.font.SysFont(c["font"], subtitle_font_size, bold=True)

        # Display win/lose message
        msg = "YOU WIN!" if status == "WIN" else "GAME OVER!"
        title_text = title_font.render(msg, True, text_col)

        # Calculate centered positions
        title_x = (size[0] - title_text.get_width()) // 2
        title_y = size[1] // 3  # Position at 1/3 height of screen

        # Render restart instructions
        restart_text = subtitle_font.render("Play again? (Y/N)", True, text_col)
        restart_x = (size[0] - restart_text.get_width()) // 2
        restart_y = title_y + title_text.get_height() + 20  # Below title

        # Blit text to screen
        screen.blit(title_text, (title_x, title_y))
        screen.blit(restart_text, (restart_x, restart_y))

        pygame.display.update()

        while True:
            for event in pygame.event.get():
                if event.type == QUIT or \
                        (event.type == pygame.KEYDOWN and event.key == pygame.K_n):
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN and event.key == pygame.K_y:
                    # 'Y' is pressed to start a new game
                    board = newGame(theme, text_col, size)
                    return board, "PLAY"

    return board, status



def newGame(theme, text_col, size, show_graphic = True):
    """
    Start a new game by resetting the board.

    Parameters:
        theme (str): game interface theme
        text_col (tuple): text colour
        size (tuple): (width, height) of the game window
    Returns:
        board (list): new game board
    """
    # Clear the board to start a new game
    board = [[0] * 4 for _ in range(4)]
    if show_graphic:

        display(board, theme, size)

        # Dynamically adjust font size based on window size
        font_size = max(size[0] // 15, 24)  # Scales with screen width, min size 24
        title_font = pygame.font.SysFont(c["font"], font_size, bold=True)

        # Render "NEW GAME!" text
        new_game_text = title_font.render("NEW GAME!", True, text_col)

        # Calculate centered position
        text_x = (size[0] - new_game_text.get_width()) // 2
        text_y = (size[1] - new_game_text.get_height()) // 2

        # Blit text to screen at centered position
        screen.blit(new_game_text, (text_x, text_y))
        pygame.display.update()

        # Wait for 1 second before starting game
        time.sleep(1)

    # Fill two random tiles at the beginning
    board = fillTwoOrFour(board, iter=2)
    if show_graphic:
        display(board, theme, size)

    return board


def restart(board, theme, text_col, size):
    """
    Restart the game immediately when 'N' is pressed.
    """
    print("Restarting game...")  # Debugging output
    return newGame(theme, text_col, size)

def display(board, theme, size):
    """
    Display the board 'matrix' on the game window.

    Parameters:
        board (list): game board
        theme (str): game interface theme
        size (tuple): (width, height) of the game window
    """
    screen.fill(tuple(c["colour"][theme]["background"]))
    
    grid_size = 4  # 2048 is a 4x4 grid
    box = size[0] // grid_size  # Adjust tile size dynamically based on window size
    padding = box // 10  # Set padding relative to box size

    # Update font size dynamically based on tile size
    font_size = max(box // 3, 24)  # Ensure font is proportional but not too small
    my_font = pygame.font.SysFont(c["font"], font_size, bold=True)

    for i in range(grid_size):
        for j in range(grid_size):
            colour = tuple(c["colour"][theme][str(board[i][j])])
            pygame.draw.rect(screen, colour, (j * box + padding,
                                              i * box + padding,
                                              box - 2 * padding,
                                              box - 2 * padding), 0)

            if board[i][j] != 0:
                if board[i][j] in (2, 4):
                    text_colour = tuple(c["colour"][theme]["dark"])
                else:
                    text_colour = tuple(c["colour"][theme]["light"])

                # Render number text centered within tile
                text_surface = my_font.render(f"{board[i][j]}", True, text_colour)
                
                # Calculate center position dynamically
                text_x = j * box + (box - text_surface.get_width()) // 2
                text_y = i * box + (box - text_surface.get_height()) // 2
                
                screen.blit(text_surface, (text_x, text_y))
    
    pygame.display.update()


def playGame(theme, difficulty, size):
    """
    Main game loop function.

    Parameters:
        theme (str): game interface theme
        difficulty (int): game difficulty, i.e., max. tile to get
    """
    # Initialise game status
    status = "PLAY"

    # Set text colour according to theme
    text_col = (0, 0, 0) if theme == "light" else (255, 255, 255)

    board = newGame(theme, text_col, size)

    # Define movement key mappings
    movement_keys = {
        pygame.K_LEFT: "left",
        pygame.K_RIGHT: "right",
        pygame.K_UP: "up",
        pygame.K_DOWN: "down"
    }

    # 游戏分数
    score = 0

    # Main game loop
    while True:
        for event in pygame.event.get():
            # Handle Quit
        
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                print(f"Key pressed: {event.key}")  # Debugging output


                if event.key == pygame.K_LCTRL or event.key == pygame.K_RCTRL:
                    print("Restarting game...")
                    board = restart(board, theme, text_col, size)
                    score = 0
                    continue

                # Handle Movement Keys
                if event.key in movement_keys:
                    key = movement_keys[event.key]
                    print(f"Key mapped: {key}")  # Debugging output

                    # Perform move (move returns tuple: (board, score))
                    new_board, merged_score = move(key, deepcopy(board))

                    # Only update board if there was a change
                    if new_board != board:
                        board = fillTwoOrFour(new_board)
                        score += merged_score
                        display(board, theme, size)
                        
                        # 显示分数
                        print(f"Score: {score}")

                        # Update game status
                        status = checkGameStatus(board, difficulty)

                        # Check win/lose
                        board, status = winCheck(board, status, theme, text_col, size)


class Game2048:
    """
    2048 游戏类 - 在主线程中运行，支持非阻塞事件处理
    
    由于 pygame 必须在主线程中运行，此类采用非阻塞模式：
    - start() 初始化游戏窗口
    - process_events() 处理一次事件循环（非阻塞）
    - 外部通过 pygame 事件系统发送键盘事件来控制游戏（支持后台运行）
    """
    
    def __init__(self, theme="light", target_tile=2048, size=(500, 500), window_title="2048 Game"):
        self.theme = theme
        self.target_tile = target_tile
        self.size = size
        self.window_title = window_title
        self.text_col = (0, 0, 0) if theme == "light" else (255, 255, 255)
        
        # 游戏状态
        self._board = None
        self._score = 0
        self._status = "PLAY"
        self._step_count = 0
        self._running = False
        self._consecutive_no_change_count = 0  # 连续未改变状态的次数
        
        # 按键映射
        self._movement_keys = {
            pygame.K_LEFT: "left",
            pygame.K_RIGHT: "right",
            pygame.K_UP: "up",
            pygame.K_DOWN: "down"
        }
        
    def start(self):
        """初始化并启动游戏（在主线程中调用）"""
        if self._running:
            return
        
        # 初始化游戏
        self._board = newGame(self.theme, self.text_col, self.size)
        
        # 设置窗口标题
        pygame.display.set_caption(self.window_title)
        
        self._score = 0
        self._status = "PLAY"
        self._step_count = 0
        self._consecutive_no_change_count = 0
        self._running = True
        
    def process_events(self):
        """
        处理一次事件循环（非阻塞）
        
        应该在主循环中定期调用此方法来处理 pygame 事件。
        返回 False 表示游戏应该退出。
        """
        if not self._running:
            return False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
                return False
            
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
        
        return True
    
    def _handle_keydown(self, key):
        """处理按键事件"""
        # 重启游戏
        if key == pygame.K_LCTRL or key == pygame.K_RCTRL:
            self._board = restart(self._board, self.theme, self.text_col, self.size)
            self._score = 0
            self._status = "PLAY"
            self._step_count = 0
            self._consecutive_no_change_count = 0
            return
        
        # 处理移动按键
        if key in self._movement_keys:
            direction = self._movement_keys[key]
            self._execute_move(direction)
    
    def _execute_move(self, direction):
        """执行移动操作"""
        if self._status != "PLAY":
            return
        
        # 执行移动
        new_board, merged_score = move(direction, deepcopy(self._board))
        
        # 只在有变化时更新
        if new_board != self._board:
            # 状态有变化，重置连续未改变计数器
            self._consecutive_no_change_count = 0
            self._board = fillTwoOrFour(new_board)
            self._score += merged_score
            self._step_count += 1
            
            # 更新显示
            display(self._board, self.theme, self.size)
            
            # 更新游戏状态
            self._status = checkGameStatus(self._board, self.target_tile)
            
            # 检查胜负（不调用winCheck，因为它会阻塞等待用户输入）
            # 在自动化环境中，只需要更新状态即可
            if self._status != "PLAY":
                # 显示游戏结束信息（但不阻塞）
                self._display_game_over()
        else:
            # 状态没有变化，增加连续未改变计数器
            self._consecutive_no_change_count += 1
            
            # 如果连续5次状态未改变，游戏结束
            if self._consecutive_no_change_count >= 5:
                self._status = "LOSE"
                # 显示游戏结束界面（但不阻塞）
                self._display_game_over()
    
    def _display_game_over(self):
        """显示游戏结束信息（非阻塞版本）"""
        if self._status != "PLAY":
            # Create a transparent overlay
            s = pygame.Surface(self.size, pygame.SRCALPHA)
            s.fill(c["colour"][self.theme]["over"])
            screen.blit(s, (0, 0))

            # Dynamically adjust font sizes
            title_font_size = max(self.size[0] // 10, 36)
            title_font = pygame.font.SysFont(c["font"], title_font_size, bold=True)

            # Display win/lose message
            msg = "YOU WIN!" if self._status == "WIN" else "GAME OVER!"
            title_text = title_font.render(msg, True, self.text_col)

            # Calculate centered positions
            title_x = (self.size[0] - title_text.get_width()) // 2
            title_y = self.size[1] // 3

            # Blit text to screen
            screen.blit(title_text, (title_x, title_y))
            pygame.display.update()
    
    def stop(self):
        """停止游戏"""
        self._running = False
    
    def get_state(self):
        """获取当前游戏状态"""
        return {
            "board": deepcopy(self._board) if self._board else None,
            "score": self._score,
            "status": self._status,
            "step_count": self._step_count,
            "terminated": self._status != "PLAY"
        }
    
    @property
    def score(self):
        """获取当前分数"""
        return self._score
    
    @property
    def board(self):
        """获取当前棋盘"""
        return deepcopy(self._board) if self._board else None
    
    @property
    def status(self):
        """获取游戏状态"""
        return self._status
    
    @property
    def terminated(self):
        """游戏是否结束"""
        return self._status != "PLAY"
    
    @property
    def step_count(self):
        """获取步数"""
        return self._step_count
    
    @property
    def running(self):
        """游戏是否正在运行"""
        return self._running