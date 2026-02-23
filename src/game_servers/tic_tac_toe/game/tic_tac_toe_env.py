import json
import re
import logging
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import time
import os

from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional
from game_servers.tic_tac_toe.game.tic_tac_toe_game import TicTacToeGame, MinimaxAI, RandomAI
from game_servers.tic_tac_toe.game.tic_tac_toe_ui import TicTacToeUIManager

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.utils.coordinate import transform_coordinate

logger = logging.getLogger(__name__)


@dataclass
class TicTacToeObs(Obs):
    image: Optional[Image.Image]
    board: List[List[str]]
    current_player: str
    terminated: bool
    winner: Optional[str] = None
    valid_moves: List[tuple] = field(default_factory=list)

    def to_text(self):
        """将观察转换为文本描述"""
        board_str = "Current board state:\n"
        board_str += "  1   2   3\n"
        for i, row in enumerate(self.board):
            row_str = chr(65 + i) + " "  # A, B, C
            for j, cell in enumerate(row):
                if j > 0:
                    row_str += " | "
                row_str += cell if cell != ' ' else ' '
            board_str += row_str + "\n"
            if i < 2:
                board_str += "  ---------\n"
        
        if self.terminated:
            if self.winner:
                board_str += f"\nGame over! Winner: {self.winner}"
            else:
                board_str += "\nGame over! It's a tie!"
        else:
            board_str += f"\nCurrent player: {self.current_player}"
            if self.valid_moves:
                moves_str = ", ".join([f"{chr(65+row)}{col+1}" for row, col in self.valid_moves])
                board_str += f"\nValid moves: {moves_str}"
        
        logger.info(f"{board_str}")
        return board_str


@dataclass
class TicTacToeAction(Action):
    actions: List[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[str]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> str:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)

    def to_json(self) -> str:
        return json.dumps(self.actions)


@dataclass
class TicTacToeGUIAction(Action):
    """GUI action for tic-tac-toe: mouse click coordinates"""
    x: int = -1  # X coordinate of click
    y: int = -1  # Y coordinate of click

    def to_json(self) -> str:
        return json.dumps({"x": self.x, "y": self.y})
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TicTacToeGUIAction':
        """从字典创建 TicTacToeGUIAction"""
        # 支持两种格式:
        # 1. {"x": 250, "y": 250}
        # 2. {"action_type": "CLICK", "parameters": {"x": 250, "y": 250}}
        if "parameters" in data:
            params = data["parameters"]
            return cls(x=params.get("x", -1), y=params.get("y", -1))
        else:
            return cls(x=data.get("x", -1), y=data.get("y", -1))


class TicTacToeEnv(BaseEnv):
    @dataclass
    class Config:
        task: str
        log_path: str
        ai_opponent: str = "minimax"  # "minimax", "random", or "none"
        player_mark: str = "X"  # "X" or "O"
        action_mode: str = "semantic"  # "semantic" (high-level) or "gui" (low-level)
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)

    cfg: Config

    def configure(self):
        self.ai_opponent_type = self.cfg.ai_opponent
        self.player_mark = self.cfg.player_mark
        self.ai_mark = 'O' if self.player_mark == 'X' else 'X'
        self.log_path = self.cfg.log_path
        self.action_mode = self.cfg.action_mode  # "action" or "gui"

        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        
        # 初始化游戏
        self.game = TicTacToeGame(first_player='X')  # X总是先手
        
        # 初始化AI对手
        if self.ai_opponent_type == "minimax":
            self.ai_opponent = MinimaxAI(bot=self.ai_mark, opponent=self.player_mark)
        elif self.ai_opponent_type == "random":
            self.ai_opponent = RandomAI(bot=self.ai_mark, opponent=self.player_mark)
        else:
            self.ai_opponent = None
        
        self.step_count = 0
        
        # 初始化UI管理器
        self.ui_manager = None
        try:
            self.ui_manager = TicTacToeUIManager(self.game, self.player_mark)
            self.ui_manager.start_ui()
            logger.info("UI started successfully")
        except Exception as e:
            logger.warning(f"Failed to start UI: {e}")
            self.ui_manager = None

    def create_board_image(self) -> Image.Image:
        """创建棋盘图像"""
        # 创建500x500的白色图像
        img = Image.new('RGB', (500, 500), color='white')
        draw = ImageDraw.Draw(img)
        
        # 绘制网格线
        cell_size = 150
        margin = 50
        
        # 垂直线
        for i in range(1, 3):
            x = margin + i * cell_size
            draw.line([(x, margin), (x, margin + 3 * cell_size)], fill='black', width=3)
        
        # 水平线
        for i in range(1, 3):
            y = margin + i * cell_size
            draw.line([(margin, y), (margin + 3 * cell_size, y)], fill='black', width=3)
        
        # 绘制坐标标签（放大字号，方便视觉模型读取）
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
            except:
                font = ImageFont.load_default()
        
        for i in range(3):
            # 行标签 (A, B, C)
            draw.text(
                (20, margin + i * cell_size + cell_size // 2 - 12),
                chr(65 + i),
                fill='black',
                font=font,
            )
            # 列标签 (1, 2, 3)
            draw.text(
                (margin + i * cell_size + cell_size // 2 - 12, 20),
                str(i + 1),
                fill='black',
                font=font,
            )
        
        # 绘制棋子
        board_2d = self.game.get_board_2d()
        for i in range(3):
            for j in range(3):
                cell_value = board_2d[i][j]
                if cell_value != ' ':
                    x = margin + j * cell_size + cell_size // 2
                    y = margin + i * cell_size + cell_size // 2
                    
                    try:
                        piece_font = ImageFont.truetype("arial.ttf", 60)
                    except:
                        try:
                            piece_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 60)
                        except:
                            piece_font = ImageFont.load_default()
                    
                    if cell_value == 'X':
                        draw.text((x - 20, y - 30), 'X', fill='red', font=piece_font)
                    elif cell_value == 'O':
                        draw.text((x - 20, y - 30), 'O', fill='blue', font=piece_font)
        
        return img

    def initial_obs(self) -> Obs:
        """获取初始观察"""
        # 如果当前轮到 AI 先手（例如玩家选择 O，AI 是 X），
        # 先让 AI 完成它的第一步，然后再把状态作为初始观察返回，
        # 这样 Agent 收到的第一张图片一定是“轮到自己下棋之前”的状态。
        if (
            self.ai_opponent
            and not self.game.is_finished
            and self.game.current_player == self.ai_mark
            and self.player_mark != self.ai_mark
        ):
            ai_move = self.ai_opponent.find_best_move(self.game)
            if ai_move is not None:
                self.game.make_move(ai_move, self.ai_mark)
                # 更新 UI 显示 AI 的落子信息
                if self.ui_manager and self.ui_manager.is_ui_running():
                    ai_row = ai_move // 3
                    ai_col = ai_move % 3
                    ai_move_str = f"{chr(65+ai_row)}{ai_col+1}"
                    self.ui_manager.show_move_info(ai_move_str, self.ai_mark)

        board_2d = self.game.get_board_2d()
        valid_moves = self.game.get_valid_moves_2d()
        
        image = self.create_board_image()

        obs = TicTacToeObs(
            image=image,
            board=board_2d,
            current_player=self.game.current_player,
            terminated=self.game.is_finished,
            winner=self.game.winner,
            valid_moves=valid_moves,
        )
        
        # 更新UI显示
        if self.ui_manager and self.ui_manager.is_ui_running():
            self.ui_manager.update_display(0)
        
        return obs

    def obs2text(self, obs: Obs) -> str:
        """将观察转换为文本"""
        return obs.to_text()

    def parse_action(self, text: str) -> Action:
        """
        解析 LLM 输出文本为动作
        
        Args:
            text: LLM 输出的文本
            
        Returns:
            TicTacToeAction 或 GUI_action 对象
        """
        if self.action_mode == "semantic":
            # 语义模式：匹配格式如 A1, B2, C3 等
            matches = re.findall(r'([A-C])([1-3])', text.upper())
            actions = []
            for match in matches:
                row_letter, col_number = match
                actions.append(f"{row_letter}{col_number}")
            
            # 如果没有找到标准格式，尝试匹配其他格式
            if not actions:
                # 匹配 (row, col) 格式
                coord_matches = re.findall(r'\((\d+),\s*(\d+)\)', text)
                for match in coord_matches:
                    row, col = int(match[0]), int(match[1])
                    if 0 <= row < 3 and 0 <= col < 3:
                        actions.append(f"{chr(65+row)}{col+1}")
                
                # 匹配单独的数字（1-9）
                if not actions:
                    number_matches = re.findall(r'\b([1-9])\b', text)
                    for match in number_matches:
                        index = int(match) - 1
                        if 0 <= index < 9:
                            row = index // 3
                            col = index % 3
                            actions.append(f"{chr(65+row)}{col+1}")
            
            return TicTacToeAction(actions=actions)
        
        elif self.action_mode == "gui":
            # GUI 模式: 解析 JSON 格式的点击坐标
            # 支持格式:
            # 1. {"x": 250, "y": 250}
            # 2. {"action_type": "CLICK", "parameters": {"x": 250, "y": 250}}
            try:
                # 尝试从文本中提取 JSON（在 ```json ``` 代码块中）
                json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # 尝试直接查找 JSON 对象
                    # 先尝试嵌套格式
                    json_match = re.search(r'\{\s*"action_type"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{[^}]*\}\s*\}', text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        # 尝试简单格式 {"x": ..., "y": ...}
                        json_match = re.search(r'\{\s*"x"\s*:\s*\d+\s*,\s*"y"\s*:\s*\d+\s*\}', text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            json_str = text
                
                data = json.loads(json_str)
                gui_action = TicTacToeGUIAction.from_dict(data)
                
                # 坐标转换逻辑 (如果启用)
                if self.cfg.coor_trans:
                    # TicTacToe 使用固定的 500x500 窗口
                    width, height = 500, 500
                    if gui_action.x is not None and gui_action.x >= 0:
                        original_x = gui_action.x
                        new_x = transform_coordinate(original_x, width)
                        gui_action.x = new_x
                        logger.info(f"X coordinate transformed: {original_x} -> {new_x} (Window Width: {width})")
                    
                    if gui_action.y is not None and gui_action.y >= 0:
                        original_y = gui_action.y
                        new_y = transform_coordinate(original_y, height)
                        gui_action.y = new_y
                        logger.info(f"Y coordinate transformed: {original_y} -> {new_y} (Window Height: {height})")
                
                return gui_action
                
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to parse GUI action from text: {e}")
                # 返回无效的 TicTacToeGUIAction（会在 step 中判负）
                return TicTacToeGUIAction(x=-1, y=-1)
        
        # 默认返回空动作
        return TicTacToeAction(actions=[])

    def step(self, action: Action) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """执行一步动作"""
        reward = 0
        last_move = None
        
        # 增加步数计数
        self.step_count += 1
        
        # 安全检查：井字棋最多9步，如果超过说明有问题
        if self.step_count > 9:
            logger.error(f"Game exceeded maximum steps (9)! Current step: {self.step_count}")
            self.game.is_finished = True
            self.game.winner = self.ai_mark  # 判玩家负
            reward = 0.0
        
        # 处理GUI动作（低维度动作）
        if isinstance(action, TicTacToeGUIAction) and not self.game.is_finished:
            # 从 TicTacToeGUIAction 中获取坐标
            x = action.x
            y = action.y
            
            # 将点击坐标转换为棋盘位置
            cell_size = 150
            margin = 50
            
            # 计算点击位置对应的行列
            col = (x - margin) // cell_size
            row = (y - margin) // cell_size
            
            # 检查是否在棋盘外或无效坐标
            if not (0 <= row < 3 and 0 <= col < 3) or x < 0 or y < 0:
                # 点击在棋盘外，直接判负
                logger.warning(f"Click outside board: ({x}, {y})")
                self.game.is_finished = True
                self.game.winner = self.ai_mark
                reward = 0.0
            elif self.game.current_player == self.player_mark:
                # 检查位置是否已被占用
                board_2d = self.game.get_board_2d()
                if board_2d[row][col] != ' ':
                    # 重复下棋，直接判负
                    logger.warning(f"Position already occupied: ({x}, {y}) -> ({row}, {col})")
                    self.game.is_finished = True
                    self.game.winner = self.ai_mark
                    reward = 0.0
                else:
                    # 执行玩家移动
                    success = self.game.make_move_2d(row, col, self.player_mark)
                    if success:
                        action_str = f"{chr(65+row)}{col+1}"
                        last_move = action_str
                        if self.ui_manager and self.ui_manager.is_ui_running():
                            self.ui_manager.show_move_info(action_str, self.player_mark)
        
        # 解析玩家动作（高维度动作）
        elif isinstance(action, TicTacToeAction) and action.actions and not self.game.is_finished:
            action_str = action.actions[0]
            if len(action_str) == 2 and action_str[0] in 'ABC' and action_str[1] in '123':
                row = ord(action_str[0]) - ord('A')
                col = int(action_str[1]) - 1
                
                # 执行玩家移动
                if self.game.current_player == self.player_mark:
                    success = self.game.make_move_2d(row, col, self.player_mark)
                    if success:
                        last_move = action_str
                        # 更新UI显示玩家移动
                        if self.ui_manager and self.ui_manager.is_ui_running():
                            self.ui_manager.show_move_info(action_str, self.player_mark)
                    else:
                        # 无效移动（下在已有棋子的位置），立即终止游戏并判负
                        logger.warning(f"Invalid move attempted: {action_str} - position already occupied!")
                        self.game.is_finished = True
                        self.game.winner = self.ai_mark  # AI获胜
                        reward = 0.0  # 玩家输掉
                        
                        # 更新UI显示无效移动
                        if self.ui_manager and self.ui_manager.is_ui_running():
                            self.ui_manager.show_move_info(f"INVALID: {action_str}", self.player_mark)
            else:
                # 无效的动作格式，立即终止游戏并判负
                logger.warning(f"Invalid action format: {action_str} - expected format like A1, B2, C3")
                self.game.is_finished = True
                self.game.winner = self.ai_mark  # AI获胜
                reward = 0.0  # 玩家输掉
                
                # 更新UI显示无效动作
                if self.ui_manager and self.ui_manager.is_ui_running():
                    self.ui_manager.show_move_info(f"INVALID FORMAT: {action_str}", self.player_mark)

        elif isinstance(action, TicTacToeAction) and not action.actions and not self.game.is_finished:
            # 没有提供动作，立即终止游戏并判负
            logger.warning("No action provided by player!")
            self.game.is_finished = True
            self.game.winner = self.ai_mark  # AI获胜
            reward = 0.0  # 玩家输掉
            
            # 更新UI显示无动作
            if self.ui_manager and self.ui_manager.is_ui_running():
                self.ui_manager.show_move_info("NO ACTION", self.player_mark)
        
        # AI对手移动（如果游戏未结束且轮到AI）
        if not self.game.is_finished and self.game.current_player == self.ai_mark and self.ai_opponent:
            ai_move = self.ai_opponent.find_best_move(self.game)
            if ai_move is not None:
                self.game.make_move(ai_move, self.ai_mark)
                # 转换AI移动为坐标格式
                ai_row = ai_move // 3
                ai_col = ai_move % 3
                ai_move_str = f"{chr(65+ai_row)}{ai_col+1}"
                
                # 更新UI显示AI移动
                if self.ui_manager and self.ui_manager.is_ui_running():
                    self.ui_manager.show_move_info(ai_move_str, self.ai_mark)
        
        # 计算奖励
        if self.game.is_finished:
            if self.game.winner == self.player_mark:
                reward = 2.0  # 玩家获胜
            elif self.game.winner == self.ai_mark:
                reward = 0.0  # AI获胜（玩家输掉）
            else:
                reward = 1.0  # 平局
        
        # 创建观察
        board_2d = self.game.get_board_2d()
        valid_moves = self.game.get_valid_moves_2d()
        
        image = self.create_board_image()
        image_path = f"{self.log_path}/obs_images/step_{self.step_count:04d}.png"
        image.save(image_path)

        obs = TicTacToeObs(
            board=board_2d,
            current_player=self.game.current_player,
            terminated=self.game.is_finished,
            winner=self.game.winner,
            valid_moves=valid_moves,
            image=image,
        )
        
        # 最终更新UI显示
        if self.ui_manager and self.ui_manager.is_ui_running():
            self.ui_manager.update_display(self.step_count)

        return obs, reward, obs.terminated, False, None

    def evaluate(self, obs: Obs):
        """评估当前状态"""
        done = obs.terminated
        if done:
            if obs.winner == self.player_mark:
                score = 2.0  # 玩家获胜
            elif obs.winner == self.ai_mark:
                score = 0.0  # AI获胜（玩家输掉）
            else:
                score = 1.0  # 平局
        else:
            score = 0.0  # 游戏进行中
        
        return score, done

    def get_game_info(self) -> dict:
        """获取游戏信息"""
        return {
            "prev_state_str": None,
            "task_description": f"Play Tic Tac Toe as player {self.player_mark}. Make moves by specifying coordinates like A1, B2, C3."
        }
    
    def __del__(self):
        """析构函数 - 确保UI正确关闭"""
        if hasattr(self, 'ui_manager') and self.ui_manager:
            try:
                self.ui_manager.stop_ui()
            except:
                pass
