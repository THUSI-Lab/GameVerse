"""
Forza Horizon 5 Game Environment
A racing game environment for LLM agent interaction
"""

import json
import time
import logging
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

logger = logging.getLogger(__name__)

@dataclass
class ForzaHorizon5Obs(BaseObs):
    """Observation for Forza Horizon 5"""
    def to_text(self) -> str:
        """Convert observation to text description"""
        return f"Step: {self.step_count}\n."


@dataclass
class ForzaHorizon5Action(BaseAction):
    """Action for Forza Horizon 5"""
    pass # 无需添加新内容

class ForzaHorizon5Env(BaseGUIEnv[ForzaHorizon5Obs, ForzaHorizon5Action]):
    """Forza Horizon 5 Game Environment"""
    
    @dataclass
    class Config:
        """Configuration for Forza Horizon 5 Environment"""
        log_path: str
        task: str = "Complete the stadium circuit race"
        action_mode: str = "gui"
        window_title: str = "Forza Horizon 5"
        screenshot_delay: float = 0.1  # Delay after taking screenshot
        action_delay: float = 0.0  # Delay between actions
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 非click操作游戏禁用
    
    cfg: Config
  
    def initial_obs(self) -> ForzaHorizon5Obs:
        """Get initial observation"""
        self.step_count = 0
        logger.info("Getting initial observation")
        # 等待游戏窗口稳定
        time.sleep(1.0)
        screenshot = self._capture_screen()
        
        obs = ForzaHorizon5Obs(
            image=screenshot,
            step_count=self.step_count
        )
        self._save_obs_image(screenshot, "initial")
        return obs
    
    def parse_action(self, text: str) -> ForzaHorizon5Action:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
            raise ValueError("Semantic action mode is not supported in Metro environment")
        elif self.action_mode == "gui":
            return self._parse_gui_action(text, ForzaHorizon5Action)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")

    def step(self, action: ForzaHorizon5Action) -> tuple:
        """
        Execute one step in the environment
        
        Returns:
            tuple: (obs, reward, terminated, truncated, info)
        """
        self.step_count += 1
        
        # Execute action
        self._execute_action(action)
        
        # Capture new observation
        screenshot = self._capture_screen()
        
        obs = ForzaHorizon5Obs(
            image=screenshot,
            step_count=self.step_count
        )
        
        # No automatic termination or reward calculation
        reward = 0.0
        terminated = False
        truncated = False
        # 保存观察截图
        self._save_obs_image(screenshot, f"step_{self.step_count}")

        info = {
            "step_count": self.step_count,
            "action_count": len(action.gui_actions)
        }
        
        return obs, reward, terminated, truncated, info
    
    def get_game_info(self) -> dict:
        """Get game information"""
        info = super().get_game_info()
        info["game_name"] = "ForzaHorizon5"
        return info
