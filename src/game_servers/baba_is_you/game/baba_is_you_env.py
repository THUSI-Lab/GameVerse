import json
import logging
import time
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.utils.coordinate import transform_coordinate

logger = logging.getLogger(__name__)


@dataclass
class BabaIsYouObs(Obs):
    """
    Baba Is You 游戏观察类

    Args:
        image: 游戏截图 (传给 LLM 的主要观察)
        level_name: 当前关卡名称
        turn_count: 当前回合数
    """
    image: Image.Image  # 主要观察：游戏截图
    level_name: str = ""
    turn_count: int = 0

    def to_text(self) -> str:
        """生成日志文本（仅用于记录，不传给 LLM）"""
        obs_text = f"Baba Is You - Level: {self.level_name}, Turn: {self.turn_count}"
        logger.info(obs_text)
        return obs_text


@dataclass
class BabaIsYouAction(Action):
    """
    Baba Is You 游戏动作类

    - semantic 模式: 解析得到的多个动作 eg: [up,up,up,down,down]
    - gui 模式: LLM 直接输出 GUI_action (键盘按键操作)
    """

    semantic_actions: List[str] = field(default_factory=list)  # 语义动作列表
    # GUI 动作 (最终执行的动作)
    gui_actions: List[Optional[GUI_action]] = field(default_factory=list)

    def __iter__(self) -> Iterator[str]:
        return iter(self.semantic_actions)

    def __getitem__(self, index: int) -> str:
        return self.semantic_actions[index]

    def __len__(self) -> int:
        return len(self.semantic_actions)

    def to_json(self) -> str:
        if self.gui_actions:
            # 将 GUI 动作列表转换为 JSON
            return json.dumps([action.to_dict() for action in self.gui_actions])
        return json.dumps(self.semantic_actions)
    

    def get_gui_actions(self) -> List[GUI_action]:
        """获取 GUI 动作列表（如果是语义动作模式，会自动转换）"""
        if self.gui_actions:
            return self.gui_actions
        elif self.semantic_actions:
            gui_actions = []
            for sem_action in self.semantic_actions:
                key = sem_action.lower()
                if key in ['up', 'down', 'left', 'right']:
                    gui_actions.append(
                        GUI_action(
                            action_type=ActionType.PRESS,
                            parameters={"key": key, "duration": 0.05}  # 增加按键持续时间
                        )
                    )
                elif key == 'idle':
                    # idle 动作不需要实际按键
                    pass
            return gui_actions
        return []
    
    def get_semantic_action(self) -> Optional[str]:
        """获取语义动作的字符串表示（用于日志）"""
        if self.semantic_actions:
            return ' -> '.join(self.semantic_actions)
        return None


class BabaIsYouEnv(BaseEnv):
    """
    Baba Is You 游戏环境
    纯图像观察模式，通过 GUIManager 发送键盘事件来控制游戏。

    两种输入模式:
    - semantic: LLM 输出 "up 3 right 2 down"，env 转换为按键
    - gui: LLM 直接输出 JSON 格式的按键动作
    """

    @dataclass
    class Config:
        log_path: str
        task: str  # 关卡名称，如 "where do i go?"
        action_mode: str = "semantic"  # "semantic" or "gui"
        window_title: str = "Baba Is You"  # 游戏窗口标题
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
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

        # 初始化 GUI 管理器（用于发送键盘事件和截图）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()

        logger.info(f"Baba Is You environment configured for level: {self.cfg.task}")

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
    
    def initial_obs(self) -> BabaIsYouObs:
        """获取初始观察（截图）"""
        logger.info("Getting initial observation")

        # 等待游戏窗口稳定
        time.sleep(1.0)

        # 截图
        image = self._capture_screen()

        obs = BabaIsYouObs(
            image=image,
            level_name=self.cfg.task,
            turn_count=0
        )

        # 保存初始观察截图
        self._save_obs_image(image, "initial")

        logger.info(f"Initial observation captured for level: {self.cfg.task}")
        return obs

    def obs2text(self, obs: BabaIsYouObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()

    def parse_action(self, text: str) -> BabaIsYouAction:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
            return self._parse_semantic_action(text)
        elif self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")

    def _parse_semantic_action(self, text: str) -> BabaIsYouAction:
        """
        解析语义动作文本
        LLM: "up 3, right 2, down 1"
        支持格式:
        - "up 3, right 2, down 1"
        - "up, up, up, right, right"
        - "up"
        """
        # 清理文本
        text = text.lower().strip()
        actions = []
        
        # 使用正则表达式解析动作和次数
        # 匹配模式: "direction" 或 "direction count"
        pattern = r'(up|down|left|right|idle)\s*(\d+)?'
        matches = re.findall(pattern, text)
        
        for direction, count_str in matches:
            count = int(count_str) if count_str else 1
            # 将动作重复 count 次
            actions.extend([direction] * count)
        
        # 如果没有解析到任何动作，返回 idle
        if not actions:
            logger.warning(f"Could not parse any valid actions from '{text}', defaulting to idle")
            actions = ['idle']
        
        logger.debug(f"Parsed semantic actions: {actions}")
        return BabaIsYouAction(semantic_actions=actions)

    def _parse_gui_action(self, text: str) -> BabaIsYouAction:
        """解析 GUI 动作 JSON（支持单个动作或动作列表）"""
        try:
            # 清理 markdown 代码块标记
            text = text.strip()
            # 移除 ```json 或 ``` 开头和结尾
            if text.startswith('```'):
                # 找到第一个换行符后的内容
                lines = text.split('\n')
                # 移除第一行（```json 或 ```）
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                # 移除最后一行如果是 ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                text = '\n'.join(lines).strip()
            
            action_data = json.loads(text)
            gui_actions = []
            
            # 支持两种格式：单个动作对象 或 动作对象列表
            if isinstance(action_data, list):
                # 动作列表
                for action_dict in action_data:
                    gui_action = GUI_action.from_dict(action_dict)
                    # 如果没有指定 duration，添加默认值
                    if 'duration' not in gui_action.parameters:
                        gui_action.parameters['duration'] = 0.05
                    gui_actions.append(gui_action)
                    
            elif isinstance(action_data, dict):
                # 单个动作
                gui_action = GUI_action.from_dict(action_data)
                # 如果没有指定 duration，添加默认值
                if 'duration' not in gui_action.parameters:
                    gui_action.parameters['duration'] = 0.05
                gui_actions.append(gui_action)
            else:
                raise ValueError(f"Invalid action format: {type(action_data)}")
            
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
            
            logger.debug(f"Parsed {len(gui_actions)} GUI action(s)")
            return BabaIsYouAction(gui_actions=gui_actions)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"Failed to parse GUI action '{text}': {e}")
            # 降级为 idle 动作
            return BabaIsYouAction(semantic_actions=['idle'])

    def _capture_screen(self) -> Image.Image:
        """截取游戏窗口截图"""
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

    def _execute_action(self, action: BabaIsYouAction):
        """执行游戏动作，统一通过 GUIManager 发送键盘事件"""
        gui_actions = action.get_gui_actions()

        if not gui_actions:
            logger.debug("No actions to execute (idle or empty)")
            time.sleep(0.5)  # 短暂等待
            return

        self.game_window = self.gui_manager.refresh_window(self.game_window)
        # 确保窗口处于激活状态
        if self.game_window:
            self.gui_manager.activate(self.game_window)
            time.sleep(0.1)

        # 执行所有按键动作
        logger.info(f"Executing {len(gui_actions)} actions: {action.get_semantic_action() or 'GUI actions'}")
        
        for i, gui_action in enumerate(gui_actions):
            logger.debug(f"  Action {i+1}/{len(gui_actions)}: {gui_action.parameters.get('key', 'unknown')}")
            self.gui_manager.execute(self.game_window, gui_action)
            # 每个动作之间短暂延迟，让游戏有时间响应
            time.sleep(0.3)

        # 等待最后一个动作完成
        time.sleep(0.5)

    def step(self, action: BabaIsYouAction) -> tuple[BabaIsYouObs, float, bool, bool, dict[str, Any]]:
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
        obs = BabaIsYouObs(
            image=image,
            level_name=self.cfg.task,
            turn_count=self.step_count
        )

        # 保存观察截图
        self._save_obs_image(image, f"step_{self.step_count}")

        # 构造返回信息
        info = {
            "step_count": self.step_count,
            "action": action.get_semantic_action() or "gui_action",
            "level_name": self.cfg.task
        }

        logger.info(f"Step {self.step_count} completed, terminated: {terminated}, reward: {reward}")

        return obs, reward, terminated, False, info

    def evaluate(self, obs: BabaIsYouObs) -> tuple[float, bool]:
        """评估当前观察，当前暂不支持 mod 评估"""
        # 简单的超时检查：如果超过 100 步就判定为失败
        is_timeout = obs.turn_count > 100
        score = 0.0  # 暂无评分逻辑
        return score, is_timeout

    def get_game_info(self) -> dict:
        """获取游戏信息"""
        window_width, window_height = self._get_window_size()
        return {
            "game_name": "Baba Is You",
            "level_name": self.cfg.task,
            "action_mode": self.action_mode,
            "window_width": window_width,
            "window_height": window_height,
            "step_count": self.step_count
        }