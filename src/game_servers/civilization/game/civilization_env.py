import json
import logging
import time
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional, Dict
from PIL import Image

from game_servers.base_gui_env import BaseGUIEnv
from game_servers.utils.types.gui_io import BaseAction, BaseObs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.GUI.GUI_manager import GUIManager

logger = logging.getLogger(__name__)


@dataclass
class CivilizationObs(BaseObs):
    """
    Civilization 游戏观察类
    """
    pass


@dataclass
class CivilizationAction(BaseAction):
    """
    Civilization 游戏动作类
    """
    pass
    

class CivilizationEnv(BaseGUIEnv):
    """
    Civilization 游戏环境
    纯图像观察模式，通过 GUIManager 发送鼠标和键盘事件来控制游戏。

    两种输入模式:
    - gui: LLM 直接输出 JSON 格式的鼠标和键盘动作
    """

    @dataclass
    class Config:
        log_path: str  # 日志保存路径
        task: str  # 文明名称或游戏任务描述
        action_mode: str = "gui"  # "gui"
        window_title: str = "Civilization"  # 游戏窗口标题
        screenshot_delay: float = 0.3
        action_delay: float = 0.3
        coor_trans: bool = True  # 手控flag：是否启用坐标转换 (1000x1000 -> 实际分辨率)
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型

    cfg: Config

    def configure(self):
        self.observations = []
        self.previous_actions = []
        self.action_mode = self.cfg.action_mode
        self.step_count = 1
        self.log_path = self.cfg.log_path

        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)

        # 初始化 GUI 管理器（用于发送键鼠事件和截图）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()

        logger.info(f"Civilization environment configured")

    def _init_gui_manager(self):
        """初始化 GUI 管理器"""
        self.gui_manager = GUIManager()

        # 查找游戏窗口（不需要转义，GUIManager 内部会处理）
        self.game_window = self.gui_manager.find_window(self.cfg.window_title)

        if self.game_window is None:
            logger.error(f"Cannot find game window: {self.cfg.window_title}")
            raise RuntimeError(f"Game window '{self.cfg.window_title}' not found. Please ensure the game is running.")
        else:
            # 激活游戏窗口
            self.gui_manager.activate(self.game_window)
            logger.info(f"Found and activated game window: {self.game_window.title}")

    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (1920, 1080)  # 默认大小
    
    def initial_obs(self) -> CivilizationObs:
        """获取初始观察（截图）"""
        logger.info("Getting initial observation")

        # 等待游戏窗口稳定
        time.sleep(1.0)

        # 截图
        image = self._capture_screen()

        obs = CivilizationObs(
            image=image,
            #civilization_name=self.cfg.task,
            step_count=1
        )

        # 保存初始观察截图
        self._save_obs_image(image, "initial")

        logger.info(f"Initial observation captured for civilization: {self.cfg.task}")
        return obs

    def parse_action(self, text: str) -> CivilizationAction:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
            raise ValueError("Semantic action mode is not supported in Civilization environment")
        elif self.action_mode == "gui":
            # 坐标转换逻辑现在由 BaseGUIEnv._parse_gui_action 统一处理
            return self._parse_gui_action(text, CivilizationAction)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")

    def step(self, action: CivilizationAction) -> tuple[CivilizationObs, float, bool, bool, dict[str, Any]]:
        """
        执行一步游戏
        注意当前的reward和terminated均为占位符，后续可根据实际游戏状态进行修改
        目前仅保持接口统一
        """
        self.step_count += 1

        logger.info(f"Step {self.step_count}: Executing action")

        # 执行动作
        self._execute_action(action)

        # 获取新的观察
        image = self._capture_screen()

        # 仅保持step接口统一
        reward = 0.0
        terminated = False

        # 创建新观察
        obs = CivilizationObs(
            image=image,
            #civilization_name=self.cfg.task,
            step_count=self.step_count
        )

        # 保存观察截图
        self._save_obs_image(image, f"step_{self.step_count}")

        # 构造返回信息
        info = {
            "step_count": self.step_count,
            "actions": [action.to_dict() for action in action.get_gui_actions()] if action.get_gui_actions() else None,
            "civilization_name": self.cfg.task
        }

        logger.info(f"Step {self.step_count} completed, terminated: {terminated}, reward: {reward}")

        return obs, reward, terminated, False, info

    def get_game_info(self) -> Dict[str, Any]:
        """Get game information"""
        info = super().get_game_info()
        info["game_name"] = "Civilization"
        return info