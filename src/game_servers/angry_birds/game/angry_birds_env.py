"""
Angry Birds 游戏环境

通过截图获取游戏状态，通过 GUI 鼠标操作模拟弹弓发射小鸟。
支持两种动作模式：
- semantic: LLM 输出 shoot(angle=X, power=Y)
- gui: LLM 直接输出 GUI 动作 (SHOOT action)
"""

import json
import re
import logging
import time
import os
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from PIL import Image

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.utils.coordinate import transform_coordinate

from .slingshot_detector import SlingshotDetector

logger = logging.getLogger(__name__)


@dataclass
class AngryBirdsObs(Obs):
    """
    Angry Birds 游戏观察类
    
    Attributes:
        image: 游戏截图 (传给 LLM 的唯一观察)
        info: 额外信息字典
    """
    image: Image.Image  # 主要观察：游戏截图
    info: Dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        """生成日志文本(仅用于记录)"""
        return ""


@dataclass
class AngryBirdsAction(Action):
    """
    Angry Birds 游戏动作类
    
    支持两种模式:
    1. Semantic Mode: shoot(angle=X, power=Y), wait()
    2. GUI Mode: JSON 格式的 GUI 动作列表
    """
    # Semantic 模式参数
    angle: float = 45.0
    power: float = 0.8
    
    # 动作类型: "shoot", "wait", "gui"
    action_type: str = "shoot"
    
    # GUI 模式: 动作列表
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    # 原始文本
    raw_text: str = ""
    
    # 输入模式: "semantic" 或 "gui"
    mode: str = "semantic"

    def __iter__(self) -> Iterator[GUI_action]:
        """iterate GUI actions"""
        if self.mode == "gui" and self.gui_actions:
            return iter(self.gui_actions)
        return iter([])

    def to_json(self) -> str:
        return json.dumps({
            "action_type": self.action_type,
            "angle": self.angle,
            "power": self.power
        })
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """返回动作参数（用于日志记录）"""
        return {
            "angle": self.angle,
            "power": self.power,
            "mode": self.mode
        }
    
    def get_gui_action(self) -> Optional[GUI_action]:
        """获取 GUI 动作"""
        if self.gui_action:
            return self.gui_action
        return None


class AngryBirdsEnv(BaseEnv):
    """
    Angry Birds 游戏环境
    
    通过 GUIManager 截图获取游戏状态，
    通过鼠标拖拽操作模拟弹弓发射。
    
    两种输入模式:
    - semantic: LLM 输出 "shoot(angle=X, power=Y)"
    - gui: LLM 直接输出 JSON 格式的射击动作
    """
    
    @dataclass
    class Config:
        log_path: str
        task: str
        window_title: str = "Angry Birds"  # 游戏窗口标题(支持正则表达式)
        action_mode: str = "semantic"  # "semantic" or "gui"
        
        # 弹弓位置 (相对窗口坐标) - 仅作为备用,优先使用自动检测
        slingshot_pos_x: float = 0.15
        slingshot_pos_y: float = 0.65
        
        # 射击配置
        slingshot_pull_ratio: float = 1.8  # 拉弓距离系数: 最大拉弓长度 = 弹弓高度 × ratio
        max_pull_distance: float = 0.15  # 最大拉弓距离(仅在未检测到弹弓高度时使用)
        wait_after_shot: float = 5.0     # 射击后等待时间
        wait_for_ui: float = 1.0         # UI 操作等待时间
        
        # 关卡配置
        scene: int = 1
        level: int = 1
        
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
        
    cfg: Config

    def configure(self):
        self.observations = []
        self.previous_actions = []
        self.action_mode = self.cfg.action_mode
        self.step_count = 0
        self.shot_count = 0
        self.log_path = self.cfg.log_path
        
        # 弹弓位置(默认值,如果检测失败则使用)
        self.slingshot_pos = {
            "x": self.cfg.slingshot_pos_x,
            "y": self.cfg.slingshot_pos_y
        }
        self.slingshot_height = 0  # 弹弓高度(像素),用于计算最大拉弓距离
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # 加载关卡配置
        self._load_level_config()
        
        # 初始化 GUI 管理器
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
        
        # 初始化弹弓检测器
        try:
            self.slingshot_detector = SlingshotDetector()
            logger.info("Slingshot detector initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize slingshot detector: {e}")
            self.slingshot_detector = None
        
        logger.info(f"AngryBirds Env initialized: Scene {self.cfg.scene}, Level {self.cfg.level}")
    
    def _load_level_config(self):
        """初始化关卡相关变量"""
        # 不再使用外部配置文件，所有配置在 config.yaml 中
        # 小鸟数量不再重要，因为不判断游戏结束
        self.bird_number = 10  # 设置一个足够大的数，不影响游戏
        self.current_bird_index = 0
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器"""
        self.gui_manager = GUIManager()
        
        # 查找游戏窗口
        window_pattern = self.cfg.window_title
        self.game_window = self.gui_manager.find_window(window_pattern)
        
        if self.game_window is None:
            logger.warning(f"Cannot find game window: {self.cfg.window_title}")
            logger.warning("Please make sure Angry Birds game is running")
        else:
            # 激活游戏窗口
            self.gui_manager.activate(self.game_window)
            logger.info(f"Found game window: {self.game_window.title}")

    def initial_obs(self) -> AngryBirdsObs:
        """获取初始观察（截图）"""
        # 等待游戏初始化
        time.sleep(self.cfg.wait_for_ui)
        
        # 在定位弹弓之前，先向后滚动滚轮将视野放到最大（向下滚动）
        if self.gui_manager and self.game_window:
            try:
                # 激活窗口确保滚轮操作生效
                self.gui_manager.activate(self.game_window)
                time.sleep(0.3)  # 增加等待时间确保窗口完全激活
                
                # 获取窗口尺寸
                window_rect = self.gui_manager.get_window_rect(self.game_window)
                win_left, win_top, win_width, win_height = window_rect
              
                # 移动鼠标到窗口中心，确保滚轮操作在窗口内生效
                center_x = win_left + win_width // 2
                center_y = win_top + win_height // 2
                
                # 直接使用pyautogui移动鼠标和滚动，更可靠
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.moveTo(center_x, center_y, duration=0.2)
                time.sleep(0.2)
                
                # 执行多次向下滚动以确保视野放到最大
                # 使用pyautogui.scroll直接滚动，正数向下滚动（放大视野）
                for i in range(30):  # 增加滚动次数，确保放到最大
                    pyautogui.scroll(3)  # 每次滚动3个单位
                    time.sleep(0.03)  # 每次滚动后短暂等待
                
                time.sleep(0.5)  # 等待所有滚动完成和画面更新
                
                logger.info("Zoomed out to maximum view by scrolling down")
            except Exception as e:
                logger.warning(f"Failed to scroll for zoom out: {e}")
        
        # 截图（在放大后）
        image = self._capture_screen()
        
        # 自动检测弹弓位置（在放大后检测）
        self._detect_and_update_slingshot(image)
        
        obs = AngryBirdsObs(
            image=image,
            info={}
        )
        return obs
    
    def _detect_and_update_slingshot(self, image: Image.Image) -> bool:
        """
        自动检测并更新弹弓上小鸟的位置
        
        优先检测 bird_on_slingshot (精确的拉弓起点)，失败时回退到 slingshot。
        
        Args:
            image: 游戏截图
            
        Returns:
            是否检测成功
        """
        if self.slingshot_detector is None:
            logger.warning("Slingshot detector not available, using default position")
            return False
        
        try:
            # 检测弹弓上的小鸟位置
            result = self.slingshot_detector.detect(
                image, 
                threshold=0.6,  # 匹配阈值
                scale_range=(0.5, 1.5),  # 缩放范围
                scale_steps=20,  # 缩放步数
                prefer_bird=True  # 优先使用 bird_on_slingshot
            )
            
            if result is not None:
                # 解包结果
                rel_x, rel_y, slingshot_height, detection_type = result
                
                # 更新弹弓位置和高度
                old_pos = self.slingshot_pos.copy()
                old_height = self.slingshot_height
                self.slingshot_pos["x"] = rel_x
                self.slingshot_pos["y"] = rel_y
                self.slingshot_height = slingshot_height
                
                logger.info(f"Slingshot position updated (using {detection_type}):")
                logger.info(f"  Old: ({old_pos['x']:.3f}, {old_pos['y']:.3f}), height={old_height}px")
                logger.info(f"  New: ({rel_x:.3f}, {rel_y:.3f}), height={slingshot_height}px")
                
                # 保存可视化结果(用于调试)
                vis_path = os.path.join(self.log_path, "slingshot_detection.png")
                self.slingshot_detector.detect_with_visualization(
                    image, 
                    output_path=vis_path,
                    threshold=0.6,
                    prefer_bird=True
                )
                
                return True
            else:
                logger.warning("Failed to detect slingshot/bird, using default position")
                return False
                
        except Exception as e:
            logger.error(f"Error in slingshot detection: {e}")
            return False

    def obs2text(self, obs: AngryBirdsObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()
    
    def _capture_screen(self) -> Image.Image:
        """截取游戏画面"""
        if self.gui_manager and self.game_window:
            try:
                self.game_window = self.gui_manager.refresh_window(self.game_window)
                return self.gui_manager.capture(self.game_window)
            except Exception as e:
                logger.warning(f"GUIManager capture failed: {e}")
        
        # 返回空白图像作为fallback
        return Image.new('RGB', (800, 600), color='white')
    
    def _get_current_bird(self) -> str:
        """获取当前弹弓上的小鸟类型(固定为红色)"""
        if self.current_bird_index < self.bird_number:
            return "red"
        return "none"
    
    def _get_remaining_birds(self) -> int:
        """获取剩余小鸟数量"""
        remaining = self.bird_number - self.current_bird_index - 1
        return max(0, remaining)

    def parse_action(self, text: str) -> AngryBirdsAction:
        """
        解析 LLM 输出文本为动作
        
        Args:
            text: LLM 输出的文本
            
        Returns:
            AngryBirdsAction 对象
        """
        if self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            return self._parse_semantic_action(text)
    
    def _parse_gui_action(self, text: str) -> AngryBirdsAction:
        """
        解析 GUI 模式的动作
        
        期望格式: {"action_type": "MOUSE_DOWN", "parameters": {"x": 0.15, "y": 0.65}}
        或者动作列表: [{"action_type": "MOUSE_DOWN", ...}, ...]
        """
        try:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接查找 JSON 对象或数组
                json_match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = text.strip()
            
            data = json.loads(json_str)
            
            # 处理单个动作或动作列表
            if isinstance(data, list):
                gui_actions = [GUI_action.from_dict(d) for d in data]
            else:
                gui_actions = [GUI_action.from_dict(data)]
            
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
            
            return AngryBirdsAction(
                action_type="gui",
                gui_actions=gui_actions,
                raw_text=text,
                mode="gui"
            )
            
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse GUI action: {e}")
            return AngryBirdsAction(action_type="wait", raw_text=text, mode="gui")
    
    def _parse_semantic_action(self, text: str) -> AngryBirdsAction:
        """
        解析语义动作模式的动作
        
        支持的格式：
        - shoot(angle=45, power=0.8)
        - wait()
        """
        # 检查是否是 wait 动作
        if "wait()" in text.lower():
            return AngryBirdsAction(
                action_type="wait",
                raw_text=text,
                mode="semantic"
            )
        
        # 解析 shoot 动作
        shoot_match = re.search(
            r"shoot\s*\(\s*angle\s*=\s*(-?\d+\.?\d*)\s*,\s*power\s*=\s*(\d+\.?\d*)\s*\)", 
            text, 
            re.IGNORECASE
        )
        
        if shoot_match:
            angle = float(shoot_match.group(1))
            power = float(shoot_match.group(2))
            
            # 限制参数范围
            angle = max(0, min(90, angle))
            power = max(0.0, min(1.0, power))
            
            return AngryBirdsAction(
                action_type="shoot",
                angle=angle,
                power=power,
                raw_text=text,
                mode="semantic"
            )
        
        # 解析失败，返回默认动作
        logger.warning(f"Failed to parse semantic action from: {text[:100]}...")
        return AngryBirdsAction(
            action_type="shoot",
            angle=45,
            power=0.5,
            mode=self.action_mode
        )

    def step(self, action: AngryBirdsAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        支持两种模式:
        - Semantic: shoot(angle, power) -> 自动转换为 GUI 操作
        - GUI: 直接执行 LLM 输出的 GUI 动作序列
        """
        self.step_count += 1
        
        # GUI 模式: 直接执行 GUI 动作列表
        if action.mode == "gui":
            # 如果检测到MOUSE_DOWN动作，修正坐标到初始检测到的弹弓位置
            for gui_action in action.gui_actions:
                if gui_action.action_type == ActionType.MOUSE_DOWN and 'x' in gui_action.parameters and 'y' in gui_action.parameters:
                    # 将坐标修正为初始检测到的弹弓位置（仅在游戏开始时定位一次）
                    if self.game_window:
                        window_rect = self.gui_manager.get_window_rect(self.game_window)
                        win_left, win_top, win_width, win_height = window_rect
                        # 使用初始检测到的相对坐标转换为绝对坐标
                        corrected_x = int(win_left + win_width * self.slingshot_pos["x"])
                        corrected_y = int(win_top + win_height * self.slingshot_pos["y"])
                        gui_action.parameters['x'] = corrected_x
                        gui_action.parameters['y'] = corrected_y
                        logger.info(f"Corrected MOUSE_DOWN coordinates to initial slingshot position: ({corrected_x}, {corrected_y})")
            
            logger.info(f"Executing GUI mode actions: {len(action.gui_actions)} actions")
            for gui_action in action.gui_actions:
                if self.gui_manager and self.game_window:
                    self.gui_manager.execute(self.game_window, gui_action)
                    time.sleep(0.1)  # 动作间短暂延迟
            
            # GUI 模式下,假设动作包含射击,更新计数
            if any(a.action_type == ActionType.MOUSE_DOWN for a in action.gui_actions):
                self.shot_count += 1
                self.current_bird_index += 1
                time.sleep(1.0)
        
        # Semantic 模式: 处理语义动作
        elif action.action_type == "wait":
            logger.info("Executing WAIT action - observing without shooting")
            time.sleep(self.cfg.wait_after_shot)
            
        elif action.action_type == "shoot":
            # 执行射击操作
            self._execute_shoot(action)
            
            # 处理小鸟特殊技能(红鸟无特殊技能,这里是空实现)
            self._handle_bird_ability()
            
            # 更新小鸟索引
            self.shot_count += 1
            self.current_bird_index += 1
            
            # 射击后短暂等待
            logger.info(f"Bird #{self.shot_count} launched, brief wait before next observation")
            time.sleep(1.0)
        
        # 截图
        image = self._capture_screen()
        
        # 弹弓位置仅在游戏开始时定位一次，不再在每次step后重新检测
        
        # 保存截图
        image_path = f"{self.log_path}/obs_images/step_{self.step_count:04d}.png"
        image.save(image_path)
        
        obs = AngryBirdsObs(
            image=image,
            info={}
        )
        
        return obs, 0, False, False, None

    def _execute_shoot(self, action: AngryBirdsAction):
        """执行弹弓射击操作"""
        if self.gui_manager is None or self.game_window is None:
            logger.warning("GUI manager not available, cannot execute shoot")
            return
        
        try:
            # 刷新窗口信息
            self.game_window = self.gui_manager.refresh_window(self.game_window)
        except:
            pass
        
        # 激活窗口
        self.gui_manager.activate(self.game_window)
        time.sleep(0.1)
        
        # 获取窗口尺寸
        window_rect = self.gui_manager.get_window_rect(self.game_window)
        win_left, win_top, win_width, win_height = window_rect
        
        # 计算弹弓起点的绝对坐标
        start_x = int(win_left + win_width * self.slingshot_pos["x"])
        start_y = int(win_top + win_height * self.slingshot_pos["y"])
        
        # 计算拉弓终点
        # 拉弓方向是发射方向的反方向
        angle_rad = math.radians(action.angle)
        # 最大拉弓长度 = 弹弓高度 * slingshot_pull_ratio
        # 实际拉弓长度 = 最大拉弓长度 * power
        if self.slingshot_height > 0:
            max_pull_distance = self.slingshot_height * self.cfg.slingshot_pull_ratio
            pull_distance = max_pull_distance * action.power
            logger.info(f"Slingshot height: {self.slingshot_height}px, ratio: {self.cfg.slingshot_pull_ratio}, max_pull: {max_pull_distance:.1f}px")
        else:
            # 回退到基于窗口宽度的默认值
            pull_distance = self.cfg.max_pull_distance * action.power * win_width
            logger.warning(f"Using default pull distance (slingshot height not detected)")
        
        # 拉弓向左下方 (发射向右上方)
        delta_x = -pull_distance * math.cos(angle_rad)
        delta_y = pull_distance * math.sin(angle_rad)  # 屏幕坐标 Y 向下为正
        
        end_x = int(start_x + delta_x)
        end_y = int(start_y + delta_y)
        
        # 确保坐标在窗口范围内
        end_x = max(win_left, min(end_x, win_left + win_width - 1))
        end_y = max(win_top, min(end_y, win_top + win_height - 1))
        
        logger.info(f"Executing shoot: angle={action.angle}, power={action.power}")
        logger.info(f"  Start: ({start_x}, {start_y}), End: ({end_x}, {end_y})")
        
        # 执行拖拽动作 (模拟弹弓拉放)
        # 1. 移动到弹弓位置
        move_action = GUI_action(
            action_type=ActionType.MOVE_TO,
            parameters={"x": start_x - win_left, "y": start_y - win_top}
        )
        self.gui_manager.execute(self.game_window, move_action)
        time.sleep(0.1)
        
        # 2. 按下鼠标
        mouse_down = GUI_action(
            action_type=ActionType.MOUSE_DOWN,
            parameters={"button": "left"}
        )
        self.gui_manager.execute(self.game_window, mouse_down)
        time.sleep(0.1)
        
        # 3. 拖拽到拉弓位置
        drag_action = GUI_action(
            action_type=ActionType.DRAG_TO,
            parameters={"x": end_x - win_left, "y": end_y - win_top}
        )
        self.gui_manager.execute(self.game_window, drag_action)
        time.sleep(0.5)
        
        # 4. 释放鼠标
        mouse_up = GUI_action(
            action_type=ActionType.MOUSE_UP,
            parameters={"button": "left"}
        )
        self.gui_manager.execute(self.game_window, mouse_up)
        
        logger.info("Shoot action completed")
    
    def _handle_bird_ability(self):
        """处理小鸟特殊技能"""
        # 只使用红色小鸟,无特殊技能
        pass

    def evaluate(self, obs: AngryBirdsObs):
        """
        评估当前状态
        
        Returns:
            (score, done) 元组
        """
        # 不判定游戏结束，完全依赖 max_steps 限制
        return 0.0, False

    def get_game_info(self) -> dict:
        """获取游戏信息，用于 prompt 模板变量替换"""
        window_width, window_height = self._get_window_size()
        
        return {
            "prev_state_str": None,
            "task_description": self.cfg.task,
            "window_width": window_width,
            "window_height": window_height,
            # 用于 action 解析
            "action": None
        }
    
    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (1920, 1080)  # 默认大小
    
    def close(self):
        """关闭环境"""
        logger.info("AngryBirds environment closed")
