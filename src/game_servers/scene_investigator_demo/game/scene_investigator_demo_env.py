import os
import re
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs

# GUI Manager for screenshot and GUI action execution
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.utils.coordinate import transform_coordinate

logger = logging.getLogger(__name__)


@dataclass
class SceneInvestigatorDemoObs(Obs):
    """
    Scene Investigator Demo 游戏观察类
    
    Attributes:
        image: 游戏截图 (传给 LLM 的主要观察)
        terminated: 游戏是否结束
    """
    image: Image.Image  # 主要观察：游戏截图
    terminated: bool = False

    def to_text(self) -> str:
        """生成文本描述（用于日志记录）"""
        return f"Game state: terminated={self.terminated}"


@dataclass
class SceneInvestigatorDemoAction(Action):
    """
    Scene Investigator Demo 游戏动作类
    
    支持 GUI 模式，使用 GUI_action 列表模拟鼠标/键盘操作（支持多个连续动作）
    """
    # GUI 模式使用（模拟鼠标/键盘，支持多个连续动作）
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    # 动作模式
    mode: str = "gui"

    def __iter__(self) -> Iterator[GUI_action]:
        return iter(self.gui_actions)

    def __getitem__(self, index: int) -> GUI_action:
        return self.gui_actions[index]

    def __len__(self) -> int:
        return len(self.gui_actions)
    
    def to_json(self) -> str:
        if self.gui_actions:
            return json.dumps([a.to_dict() for a in self.gui_actions])
        return json.dumps([])


class SceneInvestigatorDemoEnv(BaseEnv):
    """
    Scene Investigator Demo 游戏环境
    
    使用 GUI 模式：LLM 输出 JSON 格式的鼠标/键盘动作，通过 GUIManager 执行
    
    动作空间包括：
    - W A S D 移动
    - Ctrl 蹲下/站起
    - F 打开/关闭手电筒
    - Q 返回
    - E 检查
    - R 阅读（某些场景）
    - ESC 取消
    - 鼠标左键交互（当人物距离可交互物品很近时）
    - 鼠标右键旋转
    - 移动鼠标（以像素为距离单位）转动人物视角
    """
    
    @dataclass
    class Config:
        task: str
        log_path: str
        action_mode: str = "gui"  # "gui" mode only
        window_title: str = "Scene Investigators (Demo)"
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
        
    cfg: Config

    def configure(self):
        self.action_mode = self.cfg.action_mode
        self.log_path = self.cfg.log_path
        self.step_count = 0
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # 初始化 GUI 管理器（用于截图和 GUI 动作执行）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器"""
        self.gui_manager = GUIManager()
        
        # 查找游戏窗口
        window_pattern = self.cfg.window_title
        self.game_window = self.gui_manager.find_window(window_pattern)

        if self.game_window is None:
            logger.warning(f"Cannot find game window: {self.cfg.window_title}")
        else:
            # 激活游戏窗口
            self.gui_manager.activate(self.game_window)
            logger.info(f"Found game window: {self.game_window.title}")
    
    def _capture_screen(self) -> Optional[Image.Image]:
        """使用 GUIManager 截取游戏画面"""
        if self.gui_manager and self.game_window:
            try:
                # 刷新窗口信息
                self.game_window = self.gui_manager.refresh_window(self.game_window)
                image = self.gui_manager.capture(self.game_window)
                
                # 保存截图到日志目录
                image_path = os.path.join(self.log_path, "obs_images", f"step_{self.step_count:04d}.png")
                image.save(image_path)
                
                return image
            except Exception as e:
                logger.warning(f"GUIManager capture failed: {e}")
                return None
        
        # 如果截图失败，返回空白图像
        logger.warning("GUI manager or game window not available, returning blank image")
        return Image.new('RGB', (1920, 1080), color='black')
    
    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (1920, 1080)  # 默认大小

    def initial_obs(self) -> SceneInvestigatorDemoObs:
        """
        获取初始观察
        
        等待游戏窗口初始化后返回截图
        """
        # 等待游戏初始化
        time.sleep(1.0)
        
        # 截图
        image = self._capture_screen()
        
        if image is None:
            logger.warning("Failed to capture initial screenshot, using blank image")
            image = Image.new('RGB', (1920, 1080), color='black')
        
        obs = SceneInvestigatorDemoObs(
            image=image,
            terminated=False,
        )
        return obs

    def obs2text(self, obs: SceneInvestigatorDemoObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()

    def parse_action(self, text: str) -> SceneInvestigatorDemoAction:
        """
        解析 LLM 输出文本为动作
        
        GUI 模式：解析 JSON 格式的 GUI_action（支持单个或多个动作）
        """
        return self._parse_gui_action(text)
    
    def _parse_gui_action(self, text: str) -> SceneInvestigatorDemoAction:
        """解析 GUI 模式的动作（JSON 格式，支持单个或多个动作）"""
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
            
            logger.info(f"Parsed {len(gui_actions)} GUI actions")
            return SceneInvestigatorDemoAction(gui_actions=gui_actions, mode="gui")
        except Exception as e:
            logger.warning(f"Failed to parse GUI action: {e}, text: {text}")
            # 返回一个空操作
            return SceneInvestigatorDemoAction(gui_actions=[], mode="gui")

    def get_game_info(self) -> dict:
        """获取游戏信息，用于填充 prompt"""
        task_description = self.cfg.task
        window_width, window_height = self._get_window_size()

        return {
            "task_description": task_description,
            "window_width": window_width,
            "window_height": window_height,
        }

    def step(
        self, action: SceneInvestigatorDemoAction
    ) -> tuple[SceneInvestigatorDemoObs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        GUI 模式下，依次执行多个 gui_actions，然后截图获取新状态
        """
        return self._step_gui(action)
    
    def _step_gui(self, action: SceneInvestigatorDemoAction) -> tuple[SceneInvestigatorDemoObs, float, bool, bool, dict[str, Any]]:
        """
        GUI 模式下执行动作
        
        依次执行多个 gui_actions，然后截图获取新状态
        """
        if action.gui_actions and self.gui_manager and self.game_window:
            for i, gui_action in enumerate(action.gui_actions):
                try:
                    logger.info(f"Executing GUI action {i+1}/{len(action.gui_actions)}: {gui_action}")
                    # 刷新窗口信息
                    self.game_window = self.gui_manager.refresh_window(self.game_window)
                    # 激活窗口
                    self.gui_manager.activate(self.game_window)
                    time.sleep(0.05)
                    # 执行动作
                    self.gui_manager.execute(self.game_window, gui_action)
                    # 等待动作执行完成
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Failed to execute GUI action {i+1}: {e}")
            # 所有动作执行完后等待游戏响应
            time.sleep(0.3)
        else:
            logger.warning("No valid GUI actions to execute or GUI manager not initialized")
            time.sleep(0.3)
        
        # 增加步数计数
        self.step_count += 1
        
        # 截图获取新状态
        image = self._capture_screen()
        
        if image is None:
            logger.warning("Failed to capture screenshot after action, using blank image")
            image = Image.new('RGB', (1920, 1080), color='black')
        
        # 判断游戏是否结束（需要根据实际游戏逻辑调整）
        terminated = False  # TODO: 根据游戏状态判断
        
        obs = SceneInvestigatorDemoObs(
            image=image,
            terminated=terminated,
        )
        
        reward = 0.0  # TODO: 根据游戏逻辑计算奖励
        
        return obs, reward, obs.terminated, False, {}

    def evaluate(self, obs: SceneInvestigatorDemoObs):
        """评估游戏状态"""
        done = obs.terminated
        score = 0.0  # TODO: 根据游戏逻辑计算分数
        return score, done

