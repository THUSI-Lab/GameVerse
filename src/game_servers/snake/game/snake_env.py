"""
Snake Game Environment
"""

import json
import time
import logging
import pygame
import threading
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from PIL import Image
import re
import os

from game_servers.base_gui_env import BaseGUIEnv
from game_servers.utils.types.gui_io import BaseAction, BaseObs
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType

from game_servers.snake.game.game import SnakeGame

logger = logging.getLogger(__name__)

@dataclass
class SnakeObs(BaseObs):
    """Observation for Snake Game"""
    score: int = 0
    snake_length: int = 1
    
    def to_text(self) -> str:
        """Convert observation to text description"""
        return f"Step: {self.step_count}\n."


@dataclass
class SnakeAction(BaseAction):
    """Action for Snake Game"""
    """semantic 模式通过映射使用GUI_action执行"""
    pass

class SnakeEnv(BaseGUIEnv[SnakeObs, SnakeAction]):
    """Snake Game Environment"""
    
    @dataclass
    class Config:
        """Configuration for Snake Game Environment"""
        log_path: str
        task: str = "Control the snake to eat food and avoid obstacles"
        action_mode: str = "gui"
        window_title: str = "Snake Game"
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
        move_interval: float = 0.0 # 已废弃的变量,保留以兼容之前的实验config格式合并
        
        game_mode: str = "discrete"  # or "realtime"
        board_size: Optional[int] = 10  # If None, read from constants.json
        num_obstacles: Optional[int] = 0
        max_steps: Optional[int] = 100
        action_timeout: Optional[float] = None  # Timeout for LLM action in realtime mode (seconds)
        max_duration: Optional[float] = None  # Max game duration in realtime mode (seconds)
        milestone_model: str = "gemini-2.0-flash-exp"

        screenshot_delay: float = 0.5  # Delay after taking screenshot
        action_delay: float = 0.0  # Delay between actions
    
    cfg: Config

    def configure(self) -> None:
        """Configure the environment"""
        
        self.game = SnakeGame(
            board_size=self.cfg.board_size,
            mode=self.cfg.game_mode,
            seed=42,
            num_obstacles=self.cfg.num_obstacles,
            max_duration=self.cfg.max_duration
        )
        
        # Set action_timeout if provided (for realtime mode)
        if self.cfg.action_timeout is not None:
            self.game.action_timeout = self.cfg.action_timeout
        
        self._game_loop_started = False

        # 启动 UI 线程
        self.ui_running = True
        self.ui_ready_event = threading.Event()
        self.ui_thread = threading.Thread(target=self._ui_loop, daemon=True)
        self.ui_thread.start()
        
        # 等待窗口创建
        self.ui_ready_event.wait()
        time.sleep(0.5)

        # 初始化 GUIManager
        super().configure()

    def _ui_loop(self):
        """Pygame UI loop running in a separate thread"""
        # 启动游戏主循环 (Pygame init & set_mode)
        self.game.start(window_title=self.cfg.window_title)
        self.ui_ready_event.set()
        
        while self.ui_running:
            try:
                # 检查 Pygame 是否已初始化
                if not pygame.get_init():
                    break

                # process_events 处理事件并刷新屏幕
                if not self.game.process_events():
                    break
                
                # 限制刷新率
                pygame.time.Clock().tick(30)
            except Exception as e:
                # 忽略关闭时的错误
                if "video system not initialized" not in str(e):
                    logger.warning(f"UI Loop error: {e}")
                break

    def close(self) -> None:
        """Close the environment"""
        self.ui_running = False
        if hasattr(self, 'ui_thread') and self.ui_thread.is_alive():
            self.ui_thread.join()
            
        # 停止游戏
        self.game.stop()
        super().close()
    
    def initial_obs(self) -> SnakeObs:
        """Get initial observation"""
        self.step_count = 0
        logger.info("Getting initial observation")
    
        screenshot = self._capture_screen()
        
        obs = SnakeObs(
            image=screenshot,
            step_count=self.step_count
        )
        self._save_obs_image(screenshot, "initial")
        return obs
    
    def parse_action(self, text: str) -> SnakeAction:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
           return self._parse_semantic_action(text, SnakeAction)
        elif self.action_mode == "gui":
            return self._parse_gui_action(text, SnakeAction)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")
    
    def _parse_semantic_action(self, text, action_class):
        
        """Parse semantic action from text"""
        action_map = {
            "L": GUI_action(ActionType.PRESS, {"key": "left"}),
            "R": GUI_action(ActionType.PRESS, {"key": "right"}),
            "U": GUI_action(ActionType.PRESS, {"key": "up"}),
            "D": GUI_action(ActionType.PRESS, {"key": "down"}),
            "Wait": GUI_action(ActionType.WAIT, {})
        }
        actions = []
        for line in text.strip().splitlines():
            line = line.strip().upper()
            if line in action_map:
                actions.append(action_map[line])
            else:
                logger.warning(f"Unknown semantic action: {line}")
        
        return action_class(gui_actions=actions)
    
    def _execute_action(self, action: SnakeAction):
        """
        关键修改：使用 Pygame 事件注入
        注意：在实时模式下，只处理第一个动作
        """
        if not pygame.get_init():
            return
        
        # 键位映射
        key_map = {
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "up": pygame.K_UP,
            "down": pygame.K_DOWN,
            "space": pygame.K_SPACE # Wait
        }
        
        # 在实时模式下只处理第一个动作
        actions_to_process = action.gui_actions[:1] if self.cfg.game_mode == "realtime" else action.gui_actions
        
        for gui_action in actions_to_process:
            if gui_action.action_type == ActionType.PRESS:
                key_name = gui_action.parameters.get("key", "").lower()
                if key_name in key_map:
                    # 构造一个真实的 Pygame 键盘事件
                    event = pygame.event.Event(pygame.KEYDOWN, key=key_map[key_name])
                    # 发送给游戏的消息队列
                    pygame.event.post(event)
                    logger.debug(f"Simulated KeyPress: {key_name}")
    
    def step(self, action: SnakeAction) -> tuple:
        """
        Execute one step in the environment.
        
        Returns:
            tuple: (obs, reward, terminated, truncated, info)
        """
        # Lazy start for realtime mode
        if self.cfg.game_mode == "realtime" and not self._game_loop_started:
            self.game.start_game_loop()
            self._game_loop_started = True

        self.step_count += 1
        
        # 执行动作
        self._execute_action(action)
        
        # 等待游戏处理事件
        time.sleep(self.cfg.screenshot_delay)
        
        # 捕获新的观察
        screenshot = self._capture_screen()

        # 获取最新游戏状态 (线程安全)
        state = self.game.get_state()
    
        score = state['reward']
        snake_length = len(state['snake'])
        obs = SnakeObs(
            image=screenshot,
            step_count=self.step_count,
            score=score,
            snake_length=snake_length
        )
        
        # 计算奖励
        reward = score
        terminated = False
        truncated = state['terminal']
        
        # 保存观察截图
        self._save_obs_image(screenshot, f"step_{self.step_count}")

        info = {
            "step_count": self.step_count,
            "action_count": len(action.gui_actions),
            "game_turn": state.get("game_turn", 0)
        }
        
        return obs, reward, terminated, truncated, info
    
    def evaluate(self, obs):
        if not hasattr(self, 'game'):
            return {"score": 0, "success": False}
    
        state = self.game.get_state()
        
        score = state["reward"]         # 累积奖励
        terminal = state["terminal"]    # 是否结束

        return score, terminal

    def get_game_info(self) -> dict:
        """Get game information"""
        info = super().get_game_info()
        info["game_name"] = "Snake"
        if hasattr(self, 'game'):
            info["board_size"] = self.game.B
            info["game_mode"] = self.game.mode
            info["num_obstacles"] = self.game.num_obstacle
    
        return info
