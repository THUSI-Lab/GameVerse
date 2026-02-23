import json
import logging
import time
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image
import cv2

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.utils.coordinate import transform_coordinate

from game_servers.metro.game.metro_utils import find_ui_template, find_stations

logger = logging.getLogger(__name__)


@dataclass
class MetroObs(Obs):
    """
    Metro 游戏观察类

    Args:
        image: 游戏截图 (传给 LLM 的主要观察)
        level_name: 当前关卡名称
        turn_count: 当前回合数
    """
    image: Image.Image  # 主要观察：游戏截图
    stations: List[dict] = field(default_factory=list)  # 站点列表
    UI_icons: dict = field(default_factory=dict)  # UI 图标位置字典
    step_count: int = 0

    def to_text(self) -> str:
        """生成包含站点和UI图标位置信息的文本描述"""
        lines = []
        # 格式化站点信息
        if self.stations:
            lines.append(f"stations' positions you can refer to:")
            for i, station in enumerate(self.stations, 1):
                cx, cy = station.get('cx', 0), station.get('cy', 0)
                # bbox = station.get('bbox', (0, 0, 0, 0))
                # x, y, w, h = bbox
                lines.append(f"  Station {i}: Center coordinates ({cx}, {cy})")
        else:
            lines.append("\nDetected stations: None")
        
        # Format UI icon information
        if self.UI_icons:
            lines.append(f"\nUI icon positions:")
            for icon_name, pos in sorted(self.UI_icons.items()):
                if pos:
                    cx, cy = pos.get('cx', 0), pos.get('cy', 0)
                    lines.append(f"  {icon_name}: ({cx}, {cy})")
        else:
            lines.append("\nUI icon positions: None")
        
        obs_text = "\n".join(lines)
        logger.debug(f"Generated observation text with {len(self.stations)} stations and {len(self.UI_icons)} UI icons")
        return obs_text


@dataclass
class MetroAction(Action):
    """
    Metro 游戏动作类
    支持执行多个连续的 GUI 动作

    - semantic 模式: 游戏不使用语义动作，仅保留接口
    - gui 模式: LLM 输出 GUI_action 列表（支持多个连续动作）
    """

    semantic_actions: Optional[list] = None  # 语义动作（未使用）
    gui_actions: List[GUI_action] = field(default_factory=list)  # GUI 动作列表

    def to_json(self) -> str:
        if self.gui_actions:
            return json.dumps([a.to_dict() for a in self.gui_actions])
        return None   

    def get_gui_actions(self) -> List[GUI_action]:
        """获取 GUI 动作列表"""
        return self.gui_actions
    
    # def get_semantic_action(self) -> Optional[str]:
    #     """获取语义动作的字符串表示（用于日志）"""
    #     if self.semantic_action:
    #         return self.semantic_action
    #     return None


class MetroEnv(BaseEnv):
    """
    Metro 游戏环境
    纯图像观察模式，通过 GUIManager 发送键盘事件来控制游戏。
    目前假设游戏的分辨率是 1280 * 960 来编码暂停和开始按钮的位置。

    两种输入模式:
    - semantic: 不使用
    - gui: LLM 直接输出 JSON 格式的按键动作
    """

    @dataclass
    class Config:
        log_path: str
        task: str  = "design an efficient subway network to transport passengers " # 
        action_mode: str = "gui"  # "gui"
        window_title: str = "Mini Metro"  # 游戏窗口标题
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        assets_dir: str = "./src/game_servers/metro/assets/"  # 站点模板图片目录
        ui_icons_update_interval: int = 5  # UI图标位置更新间隔（步数）
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
        enable_contour_detection: bool = True  # 是否启用轮廓检测（站点检测）

    cfg: Config

    def configure(self):
        self.observations = []
        self.previous_actions = []
        self.action_mode = self.cfg.action_mode
        self.step_count = 0
        self.log_path = self.cfg.log_path
        self.assets_dir = self.cfg.assets_dir
        self.ui_icons_update_interval = self.cfg.ui_icons_update_interval
        self.last_ui_update_step = 0

        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)

        # 初始化 GUI 管理器（用于发送键盘事件和截图）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()

        # 预加载UI模板
        self.ui_templates = self._load_ui_templates()
        logger.info(f"Loaded {len(self.ui_templates)} UI templates")
        logger.info(f"Metro environment configured")

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

    def _load_ui_templates(self) -> dict:
        """预加载所有UI模板图片"""
        ui_templates = {}
        icons_dir = os.path.join(self.assets_dir, "icons")
        
        if not os.path.exists(icons_dir):
            logger.warning(f"Icons directory not found: {icons_dir}")
            return ui_templates
        
        # 加载所有图标模板
        icon_files = os.listdir(icons_dir)
        for icon_file in icon_files:
            icon_path = os.path.join(icons_dir, icon_file)
            if os.path.exists(icon_path):
                template_img = cv2.imread(icon_path)
                if template_img is not None:
                    icon_name = os.path.splitext(icon_file)[0]  # 去掉.png后缀
                    ui_templates[icon_name] = template_img
                    logger.debug(f"Loaded UI template: {icon_name}")
                else:
                    logger.warning(f"Failed to load icon template: {icon_path}")
            else:
                logger.warning(f"Icon template not found: {icon_path}")
        
        return ui_templates

    def _detect_ui_icons(self, screenshot: Image.Image) -> dict:
        """检测所有UI图标的位置"""
        ui_icons = {}
        window_size = self._get_window_size()
        
        for icon_name, template_img in self.ui_templates.items():
            target_pos = find_ui_template(screenshot, template_img, window_size)
            if target_pos:
                ui_icons[icon_name] = {
                    "cx": target_pos["cx"], 
                    "cy": target_pos["cy"],
                    "bbox": target_pos["bbox"]
                }
                logger.debug(f"Detected UI icon '{icon_name}' at ({target_pos['cx']}, {target_pos['cy']})")
            else:
                logger.debug(f"UI icon '{icon_name}' not detected")
        
        return ui_icons
    
    def initial_obs(self) -> MetroObs:
        """获取初始观察（截图）"""
        logger.info("Getting initial observation")

        # 等待游戏窗口稳定
        time.sleep(1.0)
        # self._pause_game()

        # 截图
        image = self._capture_screen()

        # 先检测UI图标位置
        ui_icons = self._detect_ui_icons(image)
        self.last_ui_update_step = 0
        logger.info(f"Detected {len(ui_icons)} UI icons in initial observation")

        # 提取UI区域的bbox列表用于mask
        ui_regions = [icon_data["bbox"] for icon_data in ui_icons.values() if "bbox" in icon_data]
        
        # 检测站点（如果启用轮廓检测），传入UI区域进行mask
        stations = []
        if self.cfg.enable_contour_detection:
            stations = find_stations(image, ui_regions=ui_regions)
            logger.info(f"Detected {len(stations)} stations in initial observation")
        else:
            logger.info("Contour detection disabled, skipping station detection")

        obs = MetroObs(
            image=image,
            step_count=0,
            stations=stations,
            UI_icons=ui_icons
        )

        # 保存初始观察截图
        self._save_obs_image(image, "initial")

        logger.info(f"Initial observation captured : {self.cfg.task}")
        return obs

    def obs2text(self, obs: MetroObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()

    def parse_action(self, text: str) -> MetroAction:
        """根据 action_mode 解析动作"""
        if self.action_mode == "semantic":
            raise ValueError("Semantic action mode is not supported in Metro environment")
        elif self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            raise ValueError(f"Unsupported action mode: {self.action_mode}")

    def _parse_gui_action(self, text: str) -> MetroAction:
        """解析 GUI 动作 JSON (支持单个动作对象或动作数组)"""
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
            return MetroAction(gui_actions=gui_actions)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"Failed to parse GUI action '{text}': {e}")
            # 降级为空动作列表
            return MetroAction(gui_actions=[])

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

    def _execute_action(self, action: MetroAction):
        """执行游戏动作，依次执行多个 GUI 动作"""
        gui_actions = action.get_gui_actions()

        if not gui_actions:
            logger.debug("No actions to execute (empty list)")
            time.sleep(0.5)  # 短暂等待
            return

        self.game_window = self.gui_manager.refresh_window(self.game_window)
        # 确保窗口处于激活状态
        if self.game_window:
            self.gui_manager.activate(self.game_window)
            time.sleep(0.2)

        # 依次执行所有动作
        for i, gui_action in enumerate(gui_actions):
            logger.info(f"Executing action {i+1}/{len(gui_actions)}: {gui_action.to_dict()}")
            try:
                self.gui_manager.execute(self.game_window, gui_action)
                # 等待动作完成
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Failed to execute action {i+1}: {e}")
        
        # 所有动作执行完后额外等待
        time.sleep(0.3)

    def click_ui_icons(self, ui_icons: dict, icon_name: str):
        """
        点击指定的UI图标
        可以用于暂停或继续游戏这样的系统操作
        """
        target_pos = None
        
        # 优先使用obs中保存的UI位置
        if ui_icons and icon_name in ui_icons:
            target_pos = ui_icons[icon_name]
            logger.debug(f"Using {icon_name} position from obs")

         # 其次尝试实时检测
        elif icon_name in self.ui_templates:
            detected_pos = find_ui_template(
                self._capture_screen(), 
                self.ui_templates[icon_name], 
                self._get_window_size()
            )
            if detected_pos:
                target_pos = detected_pos
                logger.debug(f"Using {icon_name} position from real-time detection")
        # 执行点击
        if target_pos:
            target_action = GUI_action(
                action_type=ActionType.CLICK,
                parameters={'x': target_pos['cx'], 'y': target_pos['cy'], 'duration': 0.1}
            )
            self.gui_manager.execute(self.game_window, target_action)
            time.sleep(0.5)
            logger.info(f"Game paused at ({target_pos['cx']}, {target_pos['cy']})")
        else:
            # 最后使用硬编码位置作为fallback
            if icon_name == "pause":
                target_action = GUI_action(
                    action_type=ActionType.CLICK,
                    parameters={'x': 1225, 'y': 100, 'duration': 0.1}
                )
            elif icon_name == "continue":
                target_action = GUI_action(
                    action_type=ActionType.CLICK,
                    parameters={'x': 1225, 'y': 100, 'duration': 0.1}
                )
            else:
                logger.warning(f"Unknown icon name for fallback click: {icon_name}")
                return
            
            self.gui_manager.execute(self.game_window, target_action)
            time.sleep(0.5)
            logger.warning("Game paused using fallback hardcoded position (1225, 100)")

    def step(self, action: MetroAction) -> tuple[MetroObs, float, bool, bool, dict[str, Any]]:
        """
        执行一步游戏
        注意当前的reward和terminated均为占位符，后续可根据实际游戏状态进行修改
        目前仅保持接口统一
        """
        self.step_count += 1

        logger.info(f"Step {self.step_count}: Executing action")

        # 执行动作
        self._execute_action(action)

        # 如果需要使用pause/continue，可以取消注释以下代码
        # ui_icons = self.observations[-1].UI_icons if self.observations else {}
        # self.click_ui_icons(ui_icons, "pause")
        # time.sleep(20.0)  # 等待游戏暂停
        # self.click_ui_icons(ui_icons, "continue")

        # 获取新的观察
        image = self._capture_screen()

        # 检查是否需要更新UI图标位置
        ui_icons = {}
        if self.step_count - self.last_ui_update_step >= self.ui_icons_update_interval:
            ui_icons = self._detect_ui_icons(image)
            self.last_ui_update_step = self.step_count
            logger.info(f"Updated UI icons at step {self.step_count}: detected {len(ui_icons)} icons")
        else:
            # 使用上一次的UI图标位置
            if self.observations:
                ui_icons = self.observations[-1].UI_icons
                logger.debug(f"Reusing UI icons from previous observation")

        # 提取UI区域的bbox列表用于mask
        ui_regions = [icon_data["bbox"] for icon_data in ui_icons.values() if "bbox" in icon_data]
        
        # 每次step都检测站点位置（如果启用轮廓检测），传入UI区域进行mask
        stations = []
        if self.cfg.enable_contour_detection:
            stations = find_stations(image, ui_regions=ui_regions)
            logger.debug(f"Detected {len(stations)} stations at step {self.step_count}")
        else:
            logger.debug("Contour detection disabled, skipping station detection")

        # 仅保持step接口统一
        reward = 0.0
        terminated = False

        # 创建新观察
        obs = MetroObs(
            image=image,
            step_count=self.step_count,
            stations=stations,
            UI_icons=ui_icons
        )

        # 保存观察截图
        self._save_obs_image(image, f"step_{self.step_count}")

        # 构造返回信息
        info = {
            "step_count": self.step_count,
            "actions": [a.to_dict() for a in action.get_gui_actions()] if action.get_gui_actions() else [],
            "num_stations": len(stations)
        }

        logger.info(f"Step {self.step_count} completed, terminated: {terminated}, reward: {reward}")

        return obs, reward, terminated, False, info

    def evaluate(self, obs: MetroObs) -> tuple[float, bool]:
        """无Mod游戏信息评估逻辑"""
        is_timeout = False 
        score = 0.0  # 暂无评分逻辑
        return score, is_timeout

    def get_game_info(self) -> dict:
        """获取游戏信息"""
        window_width, window_height = self._get_window_size()
        return {
            "game_name": "Maze: Path of Light",
            "task_description": self.cfg.task,  # 添加 task_description 用于 prompt
            "action_mode": self.action_mode,
            "window_width": window_width,
            "window_height": window_height,
            "step_count": self.step_count
        }