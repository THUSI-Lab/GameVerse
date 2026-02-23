import json
import time
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Generic, TypeVar
from PIL import Image
import re
import os

from game_servers.base_env import BaseEnv
from game_servers.utils.types.gui_io import BaseAction, BaseObs
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.utils.coordinate import transform_coordinate

logger = logging.getLogger(__name__)

# Type variables for generic GUI environment
ObsT = TypeVar('ObsT', bound=BaseObs)
ActionT = TypeVar('ActionT', bound=BaseAction)


class BaseGUIEnv(BaseEnv, Generic[ObsT, ActionT]):
    """Base GUI Game Environment
    
    This class provides common functionalities for GUI-based game environments.
    It uses Generic types to allow subclasses to define their own observation
    and action types while inheriting all common GUI functionality.
    
    Type Parameters:
        ObsT: Observation type, must inherit from BaseGUIObs
        ActionT: Action type, must inherit from BaseGUIAction
    
    Subclasses should:
        1. Define their own Obs class inheriting from BaseGUIObs
        2. Define their own Action class inheriting from BaseGUIAction
        3. Implement abstract methods: initial_obs(), parse_action(), step()
        4. Optionally override get_game_info() to provide game-specific info
    """
    
    @dataclass
    class Config:
        """Configuration for GUI Game Environment"""
        log_path: str
        task: str 
        window_title: str 
        action_mode: str = "gui"
        screenshot_delay: float = 0.3  # Delay after taking screenshot
        action_delay: float = 0.3  # Delay between actions
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
    
    cfg: Config

    def configure(self):
        """Initialize the environment"""
        self.step_count = 0
        self.action_mode = self.cfg.action_mode
        self.log_path = self.cfg.log_path  

        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)

        # 初始化 GUI 管理器（用于发送键盘事件和截图）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
    
    def _init_gui_manager(self):
        """Initialize GUI manager for window control"""
        self.gui_manager = GUIManager()
        window_pattern = re.escape(self.cfg.window_title)
        self.game_window = self.gui_manager.find_window(window_pattern)
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

    def _capture_screen(self) -> Image.Image:
        """Capture screenshot of the game window"""
        if self.game_window is None:
            raise RuntimeError("Game window not initialized")

        image = self.gui_manager.capture(self.game_window)
        return image
    
    def _save_obs_image(self, image: Image.Image, prefix: str = "obs"):
        """保存观察截图"""
        filename = f"{prefix}.png"
        filepath = os.path.join(self.log_path, "obs_images", filename)
        image.save(filepath)
        logger.debug(f"Saved observation image: {filepath}")

    @abstractmethod
    def initial_obs(self) -> ObsT:
        """Get initial observation
        
        Subclasses must implement this method to return their specific
        observation type.
        
        Typical implementation:
            self.step_count = 0
            logger.info("Getting initial observation")
            time.sleep(1.0)
            screenshot = self._capture_screen()
            obs = YourObsClass(image=screenshot, step_count=self.step_count)
            self._save_obs_image(screenshot, "initial")
            return obs
        """
        pass
    
    def obs2text(self, obs: ObsT) -> str:
        """Convert observation to text
        
        Default implementation calls obs.to_text().
        Override if custom behavior is needed.
        """
        return obs.to_text()
    
    @abstractmethod
    def parse_action(self, text: str) -> ActionT:
        """Parse action from text
        
        Subclasses must implement this method to parse LLM output
        and return their specific action type.
        
        Typical implementation delegates to _parse_gui_action():
            if self.action_mode == "gui":
                return self._parse_gui_action(text, YourActionClass)
            else:
                raise ValueError(f"Unsupported action mode: {self.action_mode}")
        """
        pass

    def _parse_gui_action(self, text: str, action_class: type[ActionT]) -> ActionT:
        """Parse LLM output text to GUI action
        
        This is a helper method that extracts JSON from markdown code blocks
        and creates GUI actions. Subclasses should call this method from
        their parse_action() implementation.
        
        Args:
            text: Raw text output from LLM
            action_class: The action class to instantiate (e.g., ForzaHorizon5Action)
            
        Returns:
            An instance of action_class with parsed GUI actions
        """
        try:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 尝试直接查找 JSON 数组或对象
                # 先尝试匹配数组
                array_match = re.search(r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]', text, re.DOTALL)
                if array_match:
                    json_str = array_match.group(0)
                else:
                    # 尝试匹配单个对象
                    obj_match = re.search(r'\{[^{}]*"action_type"[^{}]*\}', text, re.DOTALL)
                    if obj_match:
                        json_str = obj_match.group(0)
                    else:
                        json_str = text
            
            parsed_data = json.loads(json_str)
            
            # 支持数组或单个对象
            if isinstance(parsed_data, list):
                gui_actions = [GUI_action.from_dict(item) for item in parsed_data]
            else:
                gui_actions = [GUI_action.from_dict(parsed_data)]

            # 坐标转换逻辑 (如果启用)
            if self.cfg.coor_trans:
                width, height = self._get_window_size()
                if gui_actions:
                    for i, gui_act in enumerate(gui_actions):
                        # 转换 X 坐标
                        if "x" in gui_act.parameters:
                            original_x = gui_act.parameters["x"]
                            new_x = transform_coordinate(original_x, width)
                            gui_act.parameters["x"] = new_x
                            logger.info(f"Action {i} X coordinate transformed: {original_x} -> {new_x} (Window Width: {width})")
                        
                        # 转换 Y 坐标
                        if "y" in gui_act.parameters:
                            original_y = gui_act.parameters["y"]
                            new_y = transform_coordinate(original_y, height)
                            gui_act.parameters["y"] = new_y
                            logger.info(f"Action {i} Y coordinate transformed: {original_y} -> {new_y} (Window Height: {height})")

            logger.info(f"Parsed {len(gui_actions)} GUI action(s)")
            return action_class(gui_actions=gui_actions)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"Failed to parse GUI action '{text}': {e}")
            # 降级为空动作列表
            return action_class(gui_actions=[])
    
    def _execute_action(self, action: ActionT):
        """Execute the parsed action
        
        This method handles the actual execution of GUI actions through
        the GUIManager. It refreshes the window, ensures it's active,
        and executes each action sequentially with delays.
        """
        gui_actions = action.get_gui_actions()

        if not gui_actions:
            logger.debug("No actions to execute (empty list)")
            time.sleep(0.5)  # 
            return
    
        self.game_window = self.gui_manager.refresh_window(self.game_window)
        # 确保窗口处于激活状态
        if self.game_window:
            self.gui_manager.activate(self.game_window)
        
        # 依次执行所有动作
        for i, gui_action in enumerate(gui_actions):
            logger.info(f"Executing action {i+1}/{len(gui_actions)}: {gui_action.to_dict()}")
            try:
                self.gui_manager.execute(self.game_window, gui_action)
                # 等待动作完成
                if self.cfg.action_delay > 0.0:
                    time.sleep(self.cfg.action_delay)
            except Exception as e:
                logger.warning(f"Failed to execute action {i+1}: {e}")
    
    @abstractmethod
    def step(self, action: ActionT) -> tuple[ObsT, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment
        
        Subclasses must implement this method to perform game-specific
        step logic.
        
        Typical implementation:
            self.step_count += 1
            self._execute_action(action)
            time.sleep(0.2)  # Wait for game to update
            screenshot = self._capture_screen()
            obs = YourObsClass(image=screenshot, step_count=self.step_count)
            self._save_obs_image(screenshot, f"step_{self.step_count}")
            info = {"step_count": self.step_count, "action_count": len(action.gui_actions)}
            return obs, 0.0, False, False, info
        
        Args:
            action: Action to execute
            
        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """
        pass
    
    def evaluate(self, obs: ObsT) -> tuple:
        """Evaluate current observation
        
        Default implementation returns no reward and not done.
        Override if game-specific evaluation logic is needed.
        
        Returns:
            tuple: (score, done)
        """
        return 0.0, False
    
    def get_game_info(self) -> Dict[str, Any]:
        """Get game information
        
        Returns basic game information including window size and configuration.
        Subclasses should override this to add game-specific information,
        especially the game_name field.
        
        Returns:
            dict: Game information dictionary
        """
        window_width, window_height = self._get_window_size()
        return {
            "game_name": "BaseGUIGame",  # Subclasses should override this
            "window_title": self.cfg.window_title,
            "action_mode": self.cfg.action_mode,
            "window_width": window_width,
            "window_height": window_height,
            "step_count": self.step_count,
            "task": self.cfg.task
        }
