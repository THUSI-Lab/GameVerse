
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
class GenshinObs(BaseObs):
    """Observation for Genshin Impact"""
    pass # 无需添加新内容


@dataclass
class GenshinAction(BaseAction):
    """Action for Genshin Impact"""
    pass # 无需添加新内容

class GenshinEnv(BaseGUIEnv[GenshinObs, GenshinAction]):
    """Genshin Impact Game Environment"""
    
    @dataclass
    class Config:
        """Configuration for Genshin Impact Environment"""
        log_path: str
        task: str = "Advance the game's storyline."
        action_mode: str = "gui"
        window_title: str = "Genshin Impact"
        screenshot_delay: float = 0.1  # Delay after taking screenshot
        action_delay: float = 0.3  # Delay between actions
        coor_trans: bool = False  # 手控flag：是否启用坐标转换 (1000x1000 -> 实际分辨率)
    
    cfg: Config
    
    def initial_obs(self) -> GenshinObs:
        """Get initial observation"""
        self.step_count = 0
        logger.info("Getting initial observation")
        # 等待游戏窗口稳定
        time.sleep(1.0)
        screenshot = self._capture_screen()
        
        obs = GenshinObs(
            image=screenshot,
            step_count=self.step_count
        )
        self._save_obs_image(screenshot, "initial")
        return obs
      
    def parse_action(self, text: str) -> GenshinAction:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
            raise ValueError("Semantic action mode is not supported in Metro environment")
        elif self.action_mode == "gui":
            return self._parse_gui_action(text, GenshinAction)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")

    def step(self, action: GenshinAction) -> tuple:
        """
        Execute one step in the environment
        
        Returns:
            tuple: (obs, reward, terminated, truncated, info)
        """
        self.step_count += 1
        
        # Execute action
        self._execute_action(action)
        
        # Capture new observation
        time.sleep(self.cfg.action_delay)  # Wait for game to update
        screenshot = self._capture_screen()
        
        obs = GenshinObs(
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
    
    def get_game_info(self) -> Dict[str, Any]:
        """Get game information"""
        info = super().get_game_info()
        info["game_name"] = "RedDeadRedemption2"
        return info