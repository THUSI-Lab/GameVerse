"""
Maze Environment - 可配置大小的黑白迷宫游戏环境
"""
import json
import re
import logging
import pygame
from pygame.locals import *
import time
import os

from PIL import Image, ImageDraw
import numpy as np

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional
from game_servers.maze.game.maze_game import MazeGame

from rich import print

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.utils.coordinate import transform_coordinate

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 500
DEFAULT_HEIGHT = 500
SIZE = (DEFAULT_WIDTH, DEFAULT_HEIGHT)

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)


@dataclass
class MazeObs(Obs):
    """
    Maze 游戏观察类
    
    Attributes:
        image: 游戏截图 (传给 LLM 的主要观察)
        ball_pos: 小球位置 (用于日志)
        target_pos: 目标位置 (用于日志)
        terminated: 游戏是否结束
        best_steps: 最佳步数
    """
    image: Image.Image  # 主要观察：游戏截图
    ball_pos: tuple = (0, 0)  # 小球位置（随机生成）
    target_pos: tuple = (3, 3)  # 目标位置（随机生成，实际值由游戏状态决定）
    terminated: bool = False
    best_steps: int = -1

    def to_text(self) -> str:
        """生成日志文本（仅用于记录，不传给 LLM）"""
        obs_text = f"Maze - Ball: {self.ball_pos}, Target: {self.target_pos}, Steps: {self.best_steps}, Terminated: {self.terminated}"
        logger.info(f"{obs_text}")
        return obs_text


@dataclass
class MazeAction(Action):
    """
    Maze 游戏动作类
    
    支持两种输入模式，但最终都转换为 GUI_action 执行:
    - semantic_action 模式: LLM 输出语义动作 ["up", "down", "left", "right"]，转换为按键
    - gui 模式: LLM 直接输出 GUI_action (键盘按键操作)
    """
    # 语义动作 (用于日志和转换)
    actions: List[str] = field(default_factory=list)
    
    # GUI 动作 (最终执行的动作)
    gui_action: Optional[GUI_action] = None
    
    # 输入模式
    mode: str = "semantic"

    def __iter__(self) -> Iterator[str]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> str:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)

    def to_json(self) -> str:
        if self.gui_action:
            return json.dumps(self.gui_action.to_dict())
        return json.dumps(self.actions)
    
    def get_gui_action(self) -> Optional[GUI_action]:
        """获取 GUI 动作（如果是语义动作模式，会自动转换）"""
        if self.gui_action:
            return self.gui_action
        
        # 将语义动作转换为 GUI 动作
        if self.actions:
            semantic_action = self.actions[0].lower()
            if semantic_action in ['up', 'down', 'left', 'right']:
                return GUI_action(
                    action_type=ActionType.PRESS,
                    parameters={"key": semantic_action}
                )
        return None
    
    def get_semantic_action(self) -> Optional[str]:
        """获取语义动作"""
        if self.actions:
            return self.actions[0].lower()
        return None


class MazeEnv(BaseEnv):
    """Maze Environment - 可配置大小的黑白迷宫游戏环境"""
    """
    Maze 游戏环境
    
    游戏状态完全由 MazeGame 类管理
    env 通过 GUIManager 发送键盘事件来控制游戏。
    
    两种输入模式:
    - semantic_action: LLM 输出 "up"/"down"/"left"/"right"，env 转换为按键
    - gui: LLM 直接输出 JSON 格式的按键动作
    """
    
    @dataclass
    class Config:
        log_path: str
        task: str
        action_mode: str = "semantic"  # "semantic" or "gui"
        window_title: str = "Maze Game"  # 游戏窗口标题
        show_graphic: bool = True  # 是否显示游戏界面
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        size: int = 4  # 迷宫大小 (size×size)
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
        
    cfg: Config

    def configure(self):
        self.observations = []
        self.previous_actions = []
        self.action_mode = self.cfg.action_mode
        self.step_count = 0 
        self.log_path = self.cfg.log_path
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # 初始化pygame
        if self.cfg.show_graphic:
            pygame.init()
            self.screen = pygame.display.set_mode(SIZE)
            pygame.display.set_caption(self.cfg.window_title)
        else:
            self.screen = None
        
        # 创建游戏实例
        self.game = MazeGame(size=self.cfg.size)
        logger.info(f"Maze game started, size: {self.cfg.size}×{self.cfg.size}, best steps: {self.game.best_steps}")
        
        # 计算并保存初始蓝球到红球的距离（用于过程性评分）
        from game_servers.maze.game.maze_game import PathFinder
        initial_state = self.game.get_state()
        path_finder = PathFinder(self.game.maze, self.game.size)
        self.initial_distance = path_finder.find_best_steps(
            initial_state["ball_pos"], 
            initial_state["target_pos"]
        )
        if self.initial_distance < 0:
            # 如果无法计算初始距离（理论上不应该发生），使用 best_steps 作为备选
            self.initial_distance = initial_state["best_steps"]
        logger.info(f"Initial distance from ball to target: {self.initial_distance} steps")
        
        # 初始化 GUI 管理器（用于发送键盘事件和截图）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
        
        # 初始渲染
        if self.screen:
            self._render()
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器（可选，现在不需要激活窗口）"""
        # 由于现在直接从游戏状态生成图像和执行动作，GUIManager不再是必需的
        # 设置为None，避免激活窗口导致游戏弹到前端
        self.gui_manager = None
        self.game_window = None
        logger.info("Using direct game state access (no GUI manager activation needed)")

    def create_maze_image(self) -> Image.Image:
        """从游戏状态创建迷宫图像（不依赖屏幕截图）"""
        state = self.game.get_state()
        maze = state["maze"]
        ball_pos = state["ball_pos"]
        target_pos = state["target_pos"]
        size = self.game.size
        
        # 创建500x500的图像
        img = Image.new('RGB', SIZE, color='white')
        draw = ImageDraw.Draw(img)
        
        # 计算每个格子的尺寸（无网格线，无缝连接）
        cell_width = DEFAULT_WIDTH // size
        cell_height = DEFAULT_HEIGHT // size
        
        # 绘制迷宫
        for row in range(size):
            for col in range(size):
                x = col * cell_width
                y = row * cell_height
                
                # 绘制色块（无网格线）
                if maze[row][col] == 0:
                    # 墙（黑色）
                    draw.rectangle([x, y, x + cell_width, y + cell_height], fill='black')
                else:
                    # 路径（白色）
                    draw.rectangle([x, y, x + cell_width, y + cell_height], fill='white')
        
        # 绘制目标（红色圆形）
        target_x = target_pos[1] * cell_width + cell_width // 2
        target_y = target_pos[0] * cell_height + cell_height // 2
        radius = min(cell_width, cell_height) // 3
        draw.ellipse(
            [target_x - radius, target_y - radius, target_x + radius, target_y + radius],
            fill='red'
        )
        
        # 绘制小球（蓝色圆形）
        ball_x = ball_pos[1] * cell_width + cell_width // 2
        ball_y = ball_pos[0] * cell_height + cell_height // 2
        radius = min(cell_width, cell_height) // 4
        draw.ellipse(
            [ball_x - radius, ball_y - radius, ball_x + radius, ball_y + radius],
            fill='blue'
        )
        
        return img

    def initial_obs(self) -> MazeObs:
        """获取初始观察（从游戏状态生成图像）"""
        # 等待游戏初始化
        time.sleep(0.1)
        
        # 渲染游戏画面（用于显示，可选）
        if self.screen:
            self._render()
        
        # 从游戏状态生成图像（不依赖屏幕截图）
        image = self.create_maze_image()
        
        state = self.game.get_state()
        
        obs = MazeObs(
            image=image,
            ball_pos=state["ball_pos"],
            target_pos=state["target_pos"],
            terminated=state["terminated"],
            best_steps=state["best_steps"],
        )
        return obs

    def obs2text(self, obs: MazeObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()
    
    def _capture_screen(self) -> Image.Image:
        """
        截取游戏画面（保留作为备用方法）
        
        注意：现在主要使用 create_maze_image() 方法直接从游戏状态生成图像，
        不依赖屏幕截图。此方法保留作为备用。
        """
        # 优先使用状态生成图像（推荐方式）
        return self.create_maze_image()

    def _render(self):
        """渲染游戏画面"""
        if not self.screen:
            return
        
        # 清空屏幕
        self.screen.fill(WHITE)
        
        state = self.game.get_state()
        maze = state["maze"]
        ball_pos = state["ball_pos"]
        target_pos = state["target_pos"]
        size = self.game.size
        
        # 计算每个格子的尺寸（无网格线，无缝连接）
        cell_width = DEFAULT_WIDTH // size
        cell_height = DEFAULT_HEIGHT // size
        
        # 绘制迷宫
        for row in range(size):
            for col in range(size):
                x = col * cell_width
                y = row * cell_height
                
                # 绘制色块（无网格线）
                if maze[row][col] == 0:
                    # 墙（黑色）
                    pygame.draw.rect(self.screen, BLACK, (x, y, cell_width, cell_height))
                else:
                    # 路径（白色）
                    pygame.draw.rect(self.screen, WHITE, (x, y, cell_width, cell_height))
        
        # 绘制目标（红旗）- 红色圆形标记
        target_x = target_pos[1] * cell_width + cell_width // 2
        target_y = target_pos[0] * cell_height + cell_height // 2
        pygame.draw.circle(self.screen, RED, (target_x, target_y), min(cell_width, cell_height) // 3)
        
        # 绘制小球 - 蓝色圆形
        ball_x = ball_pos[1] * cell_width + cell_width // 2
        ball_y = ball_pos[0] * cell_height + cell_height // 2
        pygame.draw.circle(self.screen, BLUE, (ball_x, ball_y), min(cell_width, cell_height) // 4)
        
        pygame.display.update()

    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.screen:
            return self.screen.get_size()
        return SIZE  # 默认大小 (500, 500)

    def parse_action(self, text: str) -> MazeAction:
        """
        解析 LLM 输出文本为动作
        
        Args:
            text: LLM 输出的文本
            
        Returns:
            MazeAction 对象
        """
        if self.action_mode == "gui":
            # GUI 模式: 解析 JSON 格式的 GUI_action
            try:
                # 尝试从文本中提取 JSON
                json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # 尝试直接查找 JSON 对象
                    json_match = re.search(r'\{[^{}]*"action_type"[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        json_str = text
                
                data = json.loads(json_str)
                gui_action = GUI_action.from_dict(data)
                
                # 坐标转换逻辑 (如果启用)
                if self.cfg.coor_trans:
                    width, height = self._get_window_size()
                    # 转换 X 坐标
                    if "x" in gui_action.parameters:
                        original_x = gui_action.parameters["x"]
                        new_x = transform_coordinate(original_x, width)
                        gui_action.parameters["x"] = new_x
                        logger.info(f"X coordinate transformed: {original_x} -> {new_x} (Window Width: {width})")
                    
                    # 转换 Y 坐标
                    if "y" in gui_action.parameters:
                        original_y = gui_action.parameters["y"]
                        new_y = transform_coordinate(original_y, height)
                        gui_action.parameters["y"] = new_y
                        logger.info(f"Y coordinate transformed: {original_y} -> {new_y} (Window Height: {height})")
                
                # 从 GUI 动作中提取语义动作（用于日志）
                semantic_action = None
                if gui_action.action_type == ActionType.PRESS:
                    key = gui_action.parameters.get("key", "").lower()
                    if key in ['up', 'down', 'left', 'right']:
                        semantic_action = key
                
                return MazeAction(
                    actions=[semantic_action] if semantic_action else [],
                    gui_action=gui_action,
                    mode="gui"
                )
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to parse GUI action from text: {e}")

        # Action 模式: 解析游戏语义动作 (up/down/left/right)
        elif self.action_mode == "semantic":
            matches = re.findall(r"\**([\w ]+)\**.?", text)
            actions = ["".join(match).lower().strip() for match in matches]
            # 过滤有效动作
            valid_actions = [a for a in actions if a in ['up', 'down', 'left', 'right']]
            
            return MazeAction(
                actions=valid_actions if valid_actions else [],
                gui_action=None,
                mode="semantic"
            )
        
        # 解析失败，默认返回空动作
        return MazeAction(actions=[], gui_action=None, mode=self.action_mode)

    def step(self, action: MazeAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        通过 GUIManager 或 pygame 事件系统发送键盘事件，执行动作.
        游戏状态由 MazeGame 类自动更新。
        """
        self.step_count += 1

        # 记录执行前的状态
        prev_state = self.game.get_state()
        prev_ball_pos = prev_state["ball_pos"]

        # 执行键盘操作
        self._execute_action(action)
        
        # 等待游戏响应
        max_wait_iterations = 10
        for i in range(max_wait_iterations):
            time.sleep(0.01)
            if self.screen:
                # 处理pygame事件
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pass
        
        # 获取游戏状态
        state = self.game.get_state()
        
        # 渲染游戏画面（用于显示，可选）
        if self.screen:
            self._render()
        
        # 从游戏状态生成图像（不依赖屏幕截图）
        image = self.create_maze_image()
        
        # 保存图像到 obs_images 子目录
        image_path = f"{self.log_path}/obs_images/step_{self.step_count:04d}.png"
        image.save(image_path)  
        
        obs = MazeObs(
            image=image,
            ball_pos=state["ball_pos"],
            target_pos=state["target_pos"],
            terminated=state["terminated"],
            best_steps=state["best_steps"],
        )
        
        # 计算奖励（如果到达目标则给予奖励）
        reward = 1.0 if state["won"] else 0.0
        
        return obs, reward, obs.terminated, False, None

    def _execute_action(self, action: MazeAction):
        """执行动作（直接调用游戏逻辑，不激活窗口）"""
        # 获取语义动作
        semantic_action = action.get_semantic_action()
        if not semantic_action:
            logger.warning(f"No valid action to execute: {action.actions}")
            return
        
        # 直接执行游戏逻辑（不通过GUI事件，因为这是内部游戏）
        # 直接调用游戏的move方法，不需要激活窗口
        success = self.game.move(semantic_action)
        if success:
            logger.info(f"Executed action: {semantic_action}, ball moved to {self.game.ball_pos}")
        else:
            logger.warning(f"Action {semantic_action} did not move the ball")
        
        # 注意：不再使用GUIManager激活窗口，因为我们直接调用游戏逻辑
        # 这样可以避免游戏窗口弹到前端

    def evaluate(self, obs: Obs):
        """
        评估当前状态
        
        评分规则：
        最终分数 = 距离score
        
        距离score：
        - 如果完成目标（到达终点）：距离score = 1.0
        - 如果未完成目标：距离score = 1 - (当前蓝球到红球的距离 / 初始蓝球到红球的距离)
          距离使用白色格子的最短路径步数（非欧氏距离）
           
        过程性评分的含义：
        - 如果蓝球位置没有改变或更远：距离score ≈ 0
        - 如果蓝球接近目标：距离score 接近 1.0
        - 如果到达目标：距离score = 1.0
        """
        done = obs.terminated
        state = self.game.get_state()
        
        # 首先检查是否到达终点（直接比较位置，最可靠）
        if state["ball_pos"] == state["target_pos"]:
            # 到达终点，距离score = 1.0
            distance_score = 1.0
            # 游戏结束时输出详细信息
            logger.info(f"Game finished - Distance score: {distance_score:.4f}, Final score: {distance_score:.4f}")
            return distance_score, True  # 到达终点，done 应该为 True
        
        # 如果 done=True 但位置不匹配（理论上不应该发生），也给予满分距离score
        if done:
            distance_score = 1.0
            # 游戏结束时输出详细信息
            logger.info(f"Game finished - Distance score: {distance_score:.4f}, Final score: {distance_score:.4f}")
            return distance_score, done
        
        # 计算当前蓝球到红球的距离（用于过程性评分）
        from game_servers.maze.game.maze_game import PathFinder
        path_finder = PathFinder(self.game.maze, self.game.size)
        current_distance = path_finder.find_best_steps(
            state["ball_pos"],
            state["target_pos"]
        )
        
        # 计算距离score
        if current_distance == 0:
            # 如果距离为0（到达终点），距离score = 1.0
            distance_score = 1.0
        elif current_distance < 0:
            # 如果无法计算距离（理论上不应该发生），距离score = 0
            distance_score = 0.0
        elif self.initial_distance <= 0:
            # 如果初始距离无效，距离score = 0
            distance_score = 0.0
        else:
            # 过程性评分：1 - (当前距离 / 初始距离)
            # 如果当前距离 >= 初始距离，距离score为0或接近0
            # 如果当前距离 < 初始距离，距离score > 0
            distance_score = max(0.0, 1.0 - (current_distance / self.initial_distance))
        
        # 最终分数 = 距离score（不再乘以效率）
        final_score = distance_score
        
        # 如果游戏结束（done=True），输出详细信息
        if done:
            logger.info(f"Game finished - Distance score: {distance_score:.4f}, Final score: {final_score:.4f}")
            
        return final_score, done

    def get_game_info(self) -> dict:
        """获取游戏信息"""
        state = self.game.get_state()
        return {
            "prev_state_str": None,
            "task_description": self.cfg.task,
            "best_steps": state["best_steps"],
            "current_steps": state["step_count"],
            "maze_size": self.cfg.size
        }
    
    def close(self):
        """关闭环境"""
        if hasattr(self, 'game') and self.game:
            pass  # 游戏状态可以保留
        if self.screen:
            pygame.quit()

