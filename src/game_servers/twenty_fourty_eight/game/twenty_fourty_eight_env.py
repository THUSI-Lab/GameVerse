import json
import re
import logging
import pygame
from pygame.locals import *
import time
import os

from PIL import Image
import numpy as np

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional
from game_servers.twenty_fourty_eight.game.game import Game2048

from rich import print

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs

logger = logging.getLogger(__name__)

THEME = "light"

DEFAULT_WIDTH = 500
DEFAULT_HEIGHT = 500
SIZE = (DEFAULT_WIDTH, DEFAULT_HEIGHT)

@dataclass
class TwentyFourtyEightObs(Obs):
    """
    2048 游戏观察类
    
    Attributes:
        image: 游戏截图 (传给 LLM 的主要观察)
        log_obs: 棋盘状态 (仅用于日志记录，不传给 LLM)
        terminated: 游戏是否结束
        score: 当前得分
    """
    image: Image.Image  # 主要观察：游戏截图
    log_obs: list = field(default_factory=list)  # 仅用于日志
    terminated: bool = False
    score: int = 0

    def to_text(self) -> str:
        """生成日志文本（仅用于记录，不传给 LLM）"""
        if self.log_obs:
            obs_text = f"Board of 2048 Games: \n {self.log_obs[0]} \n {self.log_obs[1]} \n {self.log_obs[2]} \n {self.log_obs[3]} \n Score: {self.score}"
        else:
            obs_text = f"Score: {self.score}"
        logger.info(f"{obs_text}")
        return obs_text


@dataclass
class TwentyFourtyEightAction(Action):
    """
    2048 游戏动作类
    
    支持语义动作模式: LLM 输出语义动作 ["up", "down", "left", "right"]
    """
    # 语义动作
    actions: List[str] = field(default_factory=list)
    
    # 输入模式
    mode: str = "semantic"

    def __iter__(self) -> Iterator[str]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> str:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)

    def to_json(self) -> str:
        return json.dumps(self.actions)
    
    def get_semantic_action(self) -> Optional[str]:
        """获取语义动作"""
        if self.actions:
            return self.actions[0].lower()
        return None


class TwentyFourtyEightEnv(BaseEnv):
    """
    2048 游戏环境
    
    游戏状态完全由 Game2048 类管理
    env 通过 pygame 事件系统发送键盘事件来控制游戏，支持后台运行。
    
    输入模式:
    - semantic_action: LLM 输出 "up"/"down"/"left"/"right"，env 转换为按键
    """
    
    @dataclass
    class Config:
        log_path: str
        target_tile: int
        task: str
        action_mode: str = "semantic"  # "semantic" or "gui"
        window_title: str = "2048 Game"  # 游戏窗口标题
        show_graphic: bool = True  # 是否显示游戏界面（保留兼容性）
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率) - 保留兼容性，此游戏不使用GUI操作
        
    cfg: Config

    def configure(self):
        self.observations = []
        self.previous_actions = []
        self.target_tile = self.cfg.target_tile
        self.action_mode = self.cfg.action_mode
        self.step_count = 0 
        self.log_path = self.cfg.log_path
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # 创建游戏实例（在主线程中运行）
        self.game = Game2048(
            theme=THEME,
            target_tile=self.cfg.target_tile,
            size=SIZE,
            window_title=self.cfg.window_title
        )
        # 启动游戏
        self.game.start()
        logger.info(f"Game started with target tile: {self.target_tile}")
        logger.info("Using pygame event system and surface capture (supports background running)")

    def initial_obs(self) -> TwentyFourtyEightObs:
        """获取初始观察（截图）"""
        # 等待游戏初始化
        time.sleep(1.0)
        
        # 获取游戏状态
        state = self.game.get_state()
        
        # 截图
        image = self._capture_screen()
        
        obs = TwentyFourtyEightObs(
            image=image,
            log_obs=state["board"] if state["board"] else [],
            terminated=state["terminated"],
            score=state["score"],
        )
        return obs

    def obs2text(self, obs: TwentyFourtyEightObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()
    
    def _capture_screen(self) -> Image.Image:
        """
        直接从 pygame surface 截取游戏画面（支持后台运行）
        """
        try:
            surface = pygame.display.get_surface()
            if surface:
                # 使用 tostring 获取 RGB 数据
                data = pygame.image.tostring(surface, 'RGB')
                width, height = surface.get_size()
                return Image.frombytes('RGB', (width, height), data)
            else:
                # 如果 surface 不存在，创建一个空白图像
                logger.warning("Pygame surface not available, returning blank image")
                return Image.new('RGB', SIZE, color='white')
        except Exception as e:
            logger.warning(f"Pygame capture failed: {e}, returning blank image")
            return Image.new('RGB', SIZE, color='white')

    def parse_action(self, text: str) -> TwentyFourtyEightAction:
        """
        解析 LLM 输出文本为动作
        
        Args:
            text: LLM 输出的文本
            
        Returns:
            TwentyFourtyEightAction 对象
        """
        # 解析游戏语义动作 (up/down/left/right)
        matches = re.findall(r"\**([\w ]+)\**.?", text)
        actions = ["".join(match).lower().strip() for match in matches]
        # 过滤有效动作
        valid_actions = [a for a in actions if a in ['up', 'down', 'left', 'right']]
        
        return TwentyFourtyEightAction(
            actions=valid_actions if valid_actions else [],
            mode="semantic"
        )

    def step(self, action: TwentyFourtyEightAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        通过 pygame 事件系统发送键盘事件，执行动作（支持后台运行）。
        游戏状态由 Game2048 类自动更新。
        """
        self.step_count += 1

        # 记录执行前的状态（用于验证动作是否生效）
        prev_state = self.game.get_state()
        prev_step_count = prev_state.get("step_count", 0)

        # 执行键盘操作
        self._execute_action(action)
        
        # 等待游戏响应，多次尝试更新事件
        # 如果使用 pygame 事件系统，需要更长的等待时间确保事件被处理
        max_wait_iterations = 50  # 增加到 500ms
        for i in range(max_wait_iterations):
            time.sleep(0.01)
            self.game.process_events()
            
            # 检查状态是否已更新（如果 step_count 增加了，说明动作已执行）
            current_state = self.game.get_state()
            current_step_count = current_state.get("step_count", 0)
            if current_step_count > prev_step_count:
                # 动作已执行，可以提前退出等待
                break
        
        # 获取游戏状态
        state = self.game.get_state()
        
        # 截图
        image = self._capture_screen()
        
        # 保存截图到 obs_images 子目录
        image_path = f"{self.log_path}/obs_images/step_{self.step_count:04d}.png"
        image.save(image_path)  
        
        obs = TwentyFourtyEightObs(
            image=image,
            log_obs=state["board"] if state["board"] else [],
            terminated=state["terminated"],
            score=state["score"],
        )
        
        return obs, 0, obs.terminated, False, None

    def _execute_action(self, action: TwentyFourtyEightAction):
        """执行键盘动作（直接使用 pygame 事件系统，支持后台运行）"""
        # 获取语义动作
        semantic_action = action.get_semantic_action()
        if not semantic_action:
            logger.warning(f"No valid action to execute: {action.actions}")
            return
        
        # 按键映射：语义动作 -> pygame 按键常量
        key_mapping = {
            "up": pygame.K_UP,
            "down": pygame.K_DOWN,
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT
        }
        
        pygame_key = key_mapping.get(semantic_action.lower())
        if pygame_key is None:
            logger.warning(f"Unknown action: {semantic_action}")
            return
        
        # 直接使用 pygame 事件系统（不需要窗口在前台）
        # 创建并发送键盘按下事件
        keydown_event = pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame_key,
            unicode=""
        )
        pygame.event.post(keydown_event)
        
        # 短暂延迟后发送键盘释放事件
        time.sleep(0.01)
        keyup_event = pygame.event.Event(
            pygame.KEYUP,
            key=pygame_key
        )
        pygame.event.post(keyup_event)
        
        logger.debug(f"Executed action via pygame events: {semantic_action}")

    def evaluate(self, obs: Obs):
        """评估当前状态"""
        done = obs.terminated
        return obs.score, done

    def get_game_info(self) -> dict:
        """获取游戏信息"""
        return {
            "prev_state_str": None,
            "task_description": "Merge tiles to make a tile with the value of 2048"
        }
    
    def close(self):
        """关闭环境"""
        if hasattr(self, 'game') and self.game:
            self.game.stop()
