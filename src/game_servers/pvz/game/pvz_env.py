"""
Plants vs. Zombies 游戏环境

仿照 2048 的实现方式：
- 通过游戏截图获取游戏信息
- 通过 GUIManager 发送鼠标/键盘事件与游戏交互

动作设计（3种语义动作）：
1. plant <slot> at (<row>, <col>) - 选择第slot个卡槽的植物，种植到(row,col)格子
2. collect - 收集阳光（使用YOLO检测阳光位置）
3. wait - 等待/观察
"""

import json
import re
import logging
import time
import os
import subprocess
import numpy as np
from PIL import Image
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.utils.coordinate import transform_coordinate
from game_servers.GUI.GUI_manager import GUIManager

from .constants import (
    GRID_ROWS, GRID_COLS,
    GRID_CELL_WIDTH, GRID_CELL_HEIGHT,
    GRID_OFFSET_X, GRID_OFFSET_Y,
    PLANT_SLOT_WIDTH,
    NUM_PLANT_SLOTS,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    BACK_TO_GAME_X, BACK_TO_GAME_Y,
    grid_to_screen,
    get_plant_slot_position,
    is_valid_grid_position, is_valid_slot_index
)

logger = logging.getLogger(__name__)


# ======================== 阳光检测器 ========================

class SunDetector:
    """
    检测游戏画面中的阳光位置
    
    阳光 vs 向日葵的区别（基于实际游戏截图分析）：
    - 阳光：圆度约 0.4-0.7，面积约 2000-4000，可以出现在任何位置
    - 向日葵：圆度约 0.25-0.35（因为有花瓣），通常在固定的列位置
    
    检测策略：
    1. 使用 HSV 颜色过滤亮黄色区域
    2. 使用圆度过滤（阳光更圆，圆度 > 0.38）
    3. 排除左上角阳光计数器区域
    """
    
    # 游戏区域边界（排除UI区域）
    GAME_AREA_TOP = 90       # 排除顶部植物卡槽
    GAME_AREA_BOTTOM = 580   # 底部边界
    
    # 左上角阳光计数器区域（需要排除）
    # 这个区域显示当前阳光数量，有一个阳光图标，不是可收集的阳光
    SUN_COUNTER_X_MAX = 75   # 阳光计数器的x范围
    SUN_COUNTER_Y_MAX = 95   # 阳光计数器的y范围
    
    # 阳光大小范围（像素面积）
    SUN_MIN_AREA = 1500      # 最小面积
    SUN_MAX_AREA = 4500      # 最大面积
    
    # 阳光圆度阈值（阳光比向日葵更圆）
    # 阳光圆度约 0.4-0.7，向日葵圆度约 0.25-0.35
    SUN_MIN_CIRCULARITY = 0.38
    
    def __init__(self, model_path: str = None):
        """
        初始化阳光检测器
        
        Args:
            model_path: YOLO模型路径（可选，目前使用颜色检测）
        """
        self.model = None
        self.model_path = model_path
        logger.info("SunDetector initialized with color-based detection")
    
    def detect(self, image: Image.Image) -> List[Tuple[int, int]]:
        """
        检测图像中的所有阳光位置
        
        Args:
            image: PIL Image 游戏截图
            
        Returns:
            阳光中心坐标列表 [(x1, y1), (x2, y2), ...]
        """
        return self._detect_with_color(image)
    
    def _is_sun_counter_area(self, cx: int, cy: int) -> bool:
        """
        判断位置是否在左上角阳光计数器区域
        
        这个区域的阳光图标只是显示用的，不是可收集的阳光
        """
        return cx < self.SUN_COUNTER_X_MAX and cy < self.SUN_COUNTER_Y_MAX
    
    def _detect_with_color(self, image: Image.Image) -> List[Tuple[int, int]]:
        """
        使用优化的颜色和形状检测阳光
        
        策略：
        1. HSV 颜色过滤亮黄色区域
        2. 面积过滤（1500-4500像素）
        3. 圆度过滤（> 0.38，阳光比向日葵更圆）
        4. 排除左上角阳光计数器区域
        5. 排除顶部植物卡槽区域
        """
        try:
            import cv2
            
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 处理 RGBA 图像（如果有透明通道）
            if img_array.shape[-1] == 4:
                img_array = img_array[:, :, :3]
            
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # 阳光的HSV颜色范围
            # H: 18-42 (黄色到橙色)
            # S: 80-255 (较高饱和度)  
            # V: 180-255 (非常亮)
            lower_sun = np.array([18, 80, 180])
            upper_sun = np.array([42, 255, 255])
            
            # 创建颜色掩码
            mask = cv2.inRange(hsv, lower_sun, upper_sun)
            
            # 形态学操作
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            # 找到所有轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            sun_positions = []
            
            for contour in contours:
                # 计算面积
                area = cv2.contourArea(contour)
                
                # 面积过滤
                if area < self.SUN_MIN_AREA or area > self.SUN_MAX_AREA:
                    continue
                
                # 计算圆度
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                # 圆度过滤（阳光比向日葵更圆）
                if circularity < self.SUN_MIN_CIRCULARITY:
                    continue
                
                # 计算中心位置
                M = cv2.moments(contour)
                if M["m00"] == 0:
                    continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # 排除左上角阳光计数器区域
                if self._is_sun_counter_area(cx, cy):
                    logger.debug(f"Filtered out sun counter icon at ({cx}, {cy})")
                    continue
                
                # 排除顶部植物卡槽区域
                if cy < self.GAME_AREA_TOP:
                    continue
                
                # 通过所有过滤条件，认为是阳光
                sun_positions.append((cx, cy))
                logger.debug(f"Detected sun at ({cx}, {cy}), area={area:.0f}, circularity={circularity:.2f}")
            
            if sun_positions:
                logger.info(f"Detected {len(sun_positions)} sun(s) at: {sun_positions}")
            
            return sun_positions
            
        except ImportError:
            logger.warning("cv2 not installed, cannot detect sun")
            return []
        except Exception as e:
            logger.warning(f"Sun detection failed: {e}")
            return []
    
    def visualize_detection(self, image: Image.Image, save_path: str = None) -> Image.Image:
        """
        可视化阳光检测结果（用于调试）
        """
        try:
            import cv2
            
            img_array = np.array(image)
            if img_array.shape[-1] == 4:
                img_array = img_array[:, :, :3]
            
            result = img_array.copy()
            
            # 检测阳光
            sun_positions = self.detect(image)
            
            # 绘制检测结果
            for x, y in sun_positions:
                cv2.circle(result, (x, y), 25, (255, 0, 0), 2)
                cv2.circle(result, (x, y), 3, (255, 0, 0), -1)
                cv2.putText(result, "SUN", (x - 15, y - 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            result_image = Image.fromarray(result)
            
            if save_path:
                result_image.save(save_path)
                logger.info(f"Detection visualization saved to {save_path}")
            
            return result_image
            
        except Exception as e:
            logger.warning(f"Visualization failed: {e}")
            return image


# ======================== 观察类定义 ========================

@dataclass
class PvZObs(Obs):
    """
    植物大战僵尸游戏观察类
    
    Attributes:
        image: 游戏截图 (传给 LLM 的唯一观察)
        log_obs: 日志信息 (仅用于记录)
        game_state: 游戏状态
        terminated: 游戏是否结束
        info: 额外信息字典
    """
    image: Image.Image  # 主要观察：游戏截图
    log_obs: str = ""   # 仅用于日志
    game_state: str = "playing"
    terminated: bool = False
    info: Dict[str, Any] = field(default_factory=dict)
    
    def to_text(self) -> str:
        """生成日志文本（仅用于记录）"""
        obs_text = f"Game State: {self.game_state}, Terminated: {self.terminated}, {self.log_obs}"
        logger.info(obs_text)
        return obs_text


# ======================== 动作类定义 ========================

@dataclass
class PvZAction(Action):
    """
    植物大战僵尸游戏动作类
    
    简化的动作设计（3种语义动作）：
    
    1. plant <slot> at (<row>, <col>)
       - 选择卡槽中第slot个植物（1-indexed: slot 1-8）
       - 种植到草坪的(row, col)格子（1-indexed: row 1-5, col 1-9）
       - 转换为: 点击卡槽 → 移动到格子 → 点击格子
    
    2. collect
       - 收集屏幕上的阳光
       - 使用YOLO检测阳光位置后依次点击
    
    3. wait
       - 什么都不做，等待/观察
    
    注意：内部使用 0-based 索引，但 LLM 输入是 1-based
    """
    # 语义动作类型: "plant", "collect", "wait"
    action_type: str = ""
    
    # 动作参数
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 原始LLM输出文本
    raw_text: str = ""
    
    # 转换后的 GUI 动作序列
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    # 输入模式
    mode: str = "semantic"
    
    def __iter__(self) -> Iterator[GUI_action]:
        return iter(self.gui_actions)
    
    def __len__(self) -> int:
        return len(self.gui_actions)
    
    def to_json(self) -> str:
        if self.gui_actions:
            return json.dumps([a.to_dict() for a in self.gui_actions])
        return json.dumps({
            "action_type": self.action_type,
            "parameters": self.parameters
        })
    
    def get_semantic_description(self) -> str:
        """获取语义动作的描述（使用 1-based 索引显示）"""
        if self.action_type == "plant":
            slot = self.parameters.get("slot", 0)
            row = self.parameters.get("row", 0)
            col = self.parameters.get("col", 0)
            # 内部是 0-based，显示时转为 1-based
            return f"Plant slot {slot+1} at ({row+1}, {col+1})"
        elif self.action_type == "collect":
            count = len(self.parameters.get("sun_positions", []))
            return f"Collect {count} sun(s)"
        elif self.action_type == "wait":
            return "Wait"
        elif self.action_type == "multi_step":
            steps = self.parameters.get("steps", [])
            return f"Multi-step: {' → '.join(steps)}"
        return self.raw_text


# ======================== 环境类定义 ========================

class PvzEnv(BaseEnv):
    """
    植物大战僵尸游戏环境
    
    通过 GUIManager 与已运行的游戏窗口交互：
    - 截图获取游戏画面
    - 发送鼠标点击事件执行动作
    
    动作模式:
    - semantic: LLM 输出语义化动作，env 转换为鼠标操作
    - gui: LLM 直接输出 JSON 动作
    """
    
    @dataclass
    class Config:
        log_path: str
        task: str
        window_title: str = "Plants vs. Zombies"
        game_path: str = ""  # 游戏可执行文件路径
        action_mode: str = "semantic"  # "semantic" or "gui"
        timeout: int = 600
        screenshot_interval: float = 0.5
        
        # YOLO模型路径（用于阳光检测）
        sun_detector_model: str = ""
        
        # 网格配置（从 constants.py 导入，通过 pvz_calibrate.py 校准得到）
        grid_rows: int = GRID_ROWS
        grid_cols: int = GRID_COLS
        grid_cell_width: int = GRID_CELL_WIDTH
        grid_cell_height: int = GRID_CELL_HEIGHT
        grid_offset_x: int = GRID_OFFSET_X
        grid_offset_y: int = GRID_OFFSET_Y
        
        # 植物卡槽栏配置（实际使用 get_plant_slot_position() 函数）
        plant_slot_width: int = PLANT_SLOT_WIDTH
        
        # 卡槽数量
        num_plant_slots: int = NUM_PLANT_SLOTS
        
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)
    
    cfg: Config
    
    def configure(self):
        """配置环境"""
        self.observations = []
        self.previous_actions = []
        self.action_mode = self.cfg.action_mode
        self.step_count = 0
        self.log_path = self.cfg.log_path
        self.start_time = time.time()
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_image"), exist_ok=True)
        
        # 游戏进程（如果需要启动游戏）
        self.game_process: Optional[subprocess.Popen] = None
        
        # 初始化 GUI 管理器
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
        
        # 初始化阳光检测器
        self.sun_detector = SunDetector(self.cfg.sun_detector_model)
        
        # 缓存最近一次检测到的阳光位置
        self._last_sun_positions: List[Tuple[int, int]] = []
        
        logger.info(f"PvZ Environment configured with action_mode: {self.action_mode}")
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器并查找游戏窗口
        
        Raises:
            RuntimeError: 如果找不到游戏窗口且无法启动游戏
        """
        self.gui_manager = GUIManager()
        
        # 查找游戏窗口（不需要转义，GUIManager 内部会处理）
        self.game_window = self.gui_manager.find_window(self.cfg.window_title)
        
        if self.game_window is None:
            logger.warning(f"Cannot find game window: {self.cfg.window_title}")
            logger.warning("Please make sure the game is running.")
            
            # 尝试启动游戏
            if self.cfg.game_path and os.path.exists(self.cfg.game_path):
                logger.info(f"Attempting to start game: {self.cfg.game_path}")
                try:
                    self.game_process = subprocess.Popen(self.cfg.game_path)
                    time.sleep(5)  # 等待游戏启动
                    self.game_window = self.gui_manager.find_window(self.cfg.window_title)
                except Exception as e:
                    logger.error(f"Failed to start game: {e}")
        
        # 最终检查：如果仍然找不到游戏窗口，抛出异常
        if self.game_window is None:
            error_msg = (
                f"\n{'='*60}\n"
                f"ERROR: 无法找到游戏窗口！\n"
                f"{'='*60}\n"
                f"请确保以下条件已满足：\n"
                f"  1. 植物大战僵尸游戏已启动\n"
                f"  2. 游戏窗口标题包含: '{self.cfg.window_title}'\n"
                f"  3. 游戏窗口未被最小化\n\n"
                f"当前搜索的窗口标题: {self.cfg.window_title}\n"
                f"{'='*60}"
            )
            logger.error(error_msg)
            raise RuntimeError(f"Game window not found: '{self.cfg.window_title}'. Please start the game first!")
        
        # 找到窗口，激活它
        self.gui_manager.activate(self.game_window)
        logger.info(f"Found game window: {self.game_window.title}")
        logger.info(f"Window rect: {self.game_window.rect}")
    
    def _capture_screen(self) -> Image.Image:
        """
        截取游戏画面
        """
        if self.gui_manager and self.game_window:
            try:
                # 刷新窗口信息
                self.game_window = self.gui_manager.refresh_window(self.game_window)
                return self.gui_manager.capture(self.game_window)
            except Exception as e:
                logger.warning(f"GUIManager capture failed: {e}")
        
        # 截图失败时返回空白图像（使用校准后的窗口尺寸）
        logger.error("Failed to capture screenshot")
        return Image.new('RGB', (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT), color='black')
    
    def _detect_sun_positions(self, image: Image.Image) -> List[Tuple[int, int]]:
        """
        检测当前画面中的阳光位置
        """
        positions = self.sun_detector.detect(image)
        self._last_sun_positions = positions
        return positions
    
    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)  # 默认大小
    
    def initial_obs(self) -> PvZObs:
        """获取初始观察（截图）
        
        自动点击 Back to Game 按钮以开始游戏
        
        Raises:
            RuntimeError: 如果游戏窗口不可用
        """
        # 再次检查游戏窗口是否可用
        if self.game_window is None:
            raise RuntimeError("Game window is not available. Cannot get initial observation.")
        
        # 等待游戏就绪
        time.sleep(1.0)
        
        # 尝试刷新窗口确保它仍然存在
        try:
            self.game_window = self.gui_manager.refresh_window(self.game_window)
        except Exception as e:
            raise RuntimeError(f"Game window lost: {e}. Please make sure the game is still running.")
        
        # 自动点击 Back to Game 按钮以开始游戏
        logger.info("Clicking Back to Game button to start the game...")
        try:
            # 创建点击动作
            click_action = GUI_action(
                action_type=ActionType.CLICK,
                parameters={"x": BACK_TO_GAME_X, "y": BACK_TO_GAME_Y, "button": "left"}
            )
            self.gui_manager.execute(self.game_window, click_action)
            logger.info(f"Clicked Back to Game button at ({BACK_TO_GAME_X}, {BACK_TO_GAME_Y})")
            time.sleep(0.5)  # 等待游戏响应
        except Exception as e:
            logger.warning(f"Failed to click Back to Game button: {e}")
            logger.warning("继续执行，假设游戏已经开始...")
        
        # 截图
        image = self._capture_screen()
        
        obs = PvZObs(
            image=image,
            log_obs="Game started",
            game_state="playing",
            terminated=False
        )
        return obs
    
    def obs2text(self, obs: PvZObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        return obs.to_text()
    
    def parse_action(self, text: str) -> PvZAction:
        """
        解析 LLM 输出文本为动作
        
        Args:
            text: LLM 输出的文本
            
        Returns:
            PvZAction 对象
        """
        if self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            return self._parse_semantic_action(text)
    
    def _parse_gui_action(self, text: str) -> PvZAction:
        """
        解析 GUI 模式的动作
        
        期望格式: {"action_type": "CLICK", "parameters": {"x": 100, "y": 200}}
        或者动作列表: [{"action_type": "CLICK", ...}, ...]
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
            
            # 坐标转换逻辑 (如果启用，在坐标限制之前进行)
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
            
            # 限制坐标：超过800×600的动作都退化为799或599
            for gui_action in gui_actions:
                if 'x' in gui_action.parameters:
                    x = gui_action.parameters['x']
                    if x is not None and x > 800:
                        gui_action.parameters['x'] = 799
                if 'y' in gui_action.parameters:
                    y = gui_action.parameters['y']
                    if y is not None and y > 600:
                        gui_action.parameters['y'] = 599
            
            return PvZAction(
                action_type="gui",
                gui_actions=gui_actions,
                raw_text=text,
                mode="gui"
            )
            
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse GUI action: {e}")
            return PvZAction(action_type="wait", raw_text=text, mode="gui")
    
    def _parse_semantic_action(self, text: str) -> PvZAction:
        """
        解析语义动作模式的动作
        
        支持的格式（3种动作）：
        1. plant <slot> at (<row>, <col>) - 种植（1-based: slot 1-8, row 1-5, col 1-9）
        2. collect / collect sun - 收集阳光
        3. wait - 等待
        
        **新增: 支持多步操作序列**
        - 用换行符分隔: "collect\nplant 1 at (2,3)\nplant 2 at (4,5)"
        - 用分号分隔: "collect; plant 1 at (2,3); plant 2 at (4,5)"
        - 框架会按顺序执行所有动作
        
        注意：LLM 输入使用 1-based 索引，内部转换为 0-based
        """
        text_lower = text.lower().strip()
        
        # **关键修复: 先提取 ### Actions 部分**
        # 查找 "### actions" 标记（不区分大小写）
        actions_match = re.search(r'###\s*actions?\s*\n(.*)', text_lower, re.DOTALL | re.IGNORECASE)
        if actions_match:
            # 只解析 ### Actions 之后的内容
            actions_text = actions_match.group(1).strip()
        else:
            # 如果没有找到 ### Actions 标记，使用整个文本（向后兼容）
            actions_text = text_lower
        
        # 分割多个动作（支持换行符或分号）
        # 先尝试按换行符分割
        action_lines = [line.strip() for line in actions_text.split('\n') if line.strip()]
        
        # 如果没有多行，尝试按分号分割
        if len(action_lines) == 1:
            action_lines = [line.strip() for line in actions_text.split(';') if line.strip()]
        
        # 如果只有一个动作，使用原有的单动作解析逻辑
        if len(action_lines) == 1:
            return self._parse_single_semantic_action(text_lower, text)
        
        # 多个动作：逐个解析并合并 GUI 动作序列
        logger.info(f"Parsing multi-step action sequence: {len(action_lines)} actions")
        all_gui_actions = []
        action_descriptions = []
        
        for idx, action_line in enumerate(action_lines):
            logger.info(f"  [{idx+1}/{len(action_lines)}] Parsing: {action_line}")
            single_action = self._parse_single_semantic_action(action_line, text)
            
            # 合并 GUI 动作
            all_gui_actions.extend(single_action.gui_actions)
            action_descriptions.append(single_action.get_semantic_description())
            
            # 在动作之间添加短暂延迟（除了最后一个动作）
            if idx < len(action_lines) - 1:
                all_gui_actions.append(
                    GUI_action(
                        action_type=ActionType.WAIT,
                        parameters={"duration": 0.3}
                    )
                )
        
        # 返回合并后的动作
        return PvZAction(
            action_type="multi_step",
            parameters={"steps": action_descriptions},
            gui_actions=all_gui_actions,
            raw_text=text,
            mode="semantic"
        )
    
    def _parse_single_semantic_action(self, text_lower: str, original_text: str) -> PvZAction:
        """
        解析单个语义动作
        
        Args:
            text_lower: 小写的动作文本
            original_text: 原始文本（用于日志）
        
        Returns:
            PvZAction 对象
        
        注意：LLM 输出使用 1-based 索引 (slot 1-8, row 1-5, col 1-9)
              内部转换为 0-based 索引 (slot 0-7, row 0-4, col 0-8)
        """
        # ========== 1. 种植动作 ==========
        # 格式: "plant 1 at (2, 3)" 或 "plant slot 1 at (2, 3)"
        plant_match = re.search(
            r'plant\s+(?:slot\s+)?(\d+)\s+at\s*\(?\s*(\d+)\s*,\s*(\d+)\s*\)?',
            text_lower
        )
        if plant_match:
            slot = int(plant_match.group(1)) - 1  # 转换为 0-based
            row = int(plant_match.group(2)) - 1   # 转换为 0-based
            col = int(plant_match.group(3)) - 1   # 转换为 0-based
            return self._create_plant_action(slot, row, col, original_text)
        
        # 备选格式: "plant slot 1 at row 2 col 3"
        plant_match2 = re.search(
            r'plant\s+(?:slot\s+)?(\d+)\s+at\s+row\s*(\d+)\s+col\s*(\d+)',
            text_lower
        )
        if plant_match2:
            slot = int(plant_match2.group(1)) - 1  # 转换为 0-based
            row = int(plant_match2.group(2)) - 1   # 转换为 0-based
            col = int(plant_match2.group(3)) - 1   # 转换为 0-based
            return self._create_plant_action(slot, row, col, original_text)
        
        # ========== 2. 收集阳光动作 ==========
        if 'collect' in text_lower:
            return self._create_collect_action(original_text)
        
        # ========== 3. 等待动作 ==========
        # 默认或明确的 wait
        return PvZAction(action_type="wait", raw_text=original_text, mode="semantic")
    
    def _create_plant_action(self, slot: int, row: int, col: int, raw_text: str) -> PvZAction:
        """
        创建种植动作
        
        动作序列：
        1. 点击卡槽中第slot个植物
        2. 移动鼠标到目标格子
        3. 点击目标格子完成种植
        
        坐标计算使用 constants.py 中的校准值，避免魔法数字
        
        Args:
            slot: 卡槽索引 (0-based 内部索引, 范围: 0 到 NUM_PLANT_SLOTS-1)
            row: 草坪行号 (0-based 内部索引, 范围: 0 到 GRID_ROWS-1)
            col: 草坪列号 (0-based 内部索引, 范围: 0 到 GRID_COLS-1)
            raw_text: 原始LLM输出
        """
        # 使用 constants.py 中的验证函数
        if not is_valid_slot_index(slot):
            logger.warning(f"Invalid slot index: {slot}, must be 0-{NUM_PLANT_SLOTS-1}")
            return PvZAction(action_type="wait", raw_text=raw_text, mode="semantic")
        
        if not is_valid_grid_position(row, col):
            logger.warning(f"Invalid grid position: ({row}, {col}), must be (0-{GRID_ROWS-1}, 0-{GRID_COLS-1})")
            return PvZAction(action_type="wait", raw_text=raw_text, mode="semantic")
        
        # 使用 constants.py 中的坐标转换函数获取屏幕坐标
        slot_x, slot_y = get_plant_slot_position(slot)
        grid_x, grid_y = grid_to_screen(row, col)
        
        # 创建 GUI 动作序列
        gui_actions = [
            # 1. 点击卡槽选择植物
            GUI_action(
                action_type=ActionType.CLICK,
                parameters={"x": slot_x, "y": slot_y, "button": "left"}
            ),
            # 2. 短暂等待
            GUI_action(
                action_type=ActionType.WAIT,
                parameters={"duration": 0.1}
            ),
            # 3. 移动到目标格子
            GUI_action(
                action_type=ActionType.MOVE_TO,
                parameters={"x": grid_x, "y": grid_y}
            ),
            # 4. 短暂等待
            GUI_action(
                action_type=ActionType.WAIT,
                parameters={"duration": 0.05}
            ),
            # 5. 点击完成种植
            GUI_action(
                action_type=ActionType.CLICK,
                parameters={"x": grid_x, "y": grid_y, "button": "left"}
            )
        ]
        
        return PvZAction(
            action_type="plant",
            parameters={"slot": slot, "row": row, "col": col},
            gui_actions=gui_actions,
            raw_text=raw_text,
            mode="semantic"
        )
    
    def _create_collect_action(self, raw_text: str) -> PvZAction:
        """
        创建收集阳光的动作
        
        **实时截图检测阳光位置**，然后依次点击收集
        不使用缓存的位置，因为阳光会移动
        """
        # 实时截图并检测阳光位置（不使用缓存！）
        try:
            image = self._capture_screen()
            sun_positions = self._detect_sun_positions(image)
            logger.info(f"[COLLECT] Real-time detection: found {len(sun_positions)} sun(s) at {sun_positions}")
        except Exception as e:
            logger.warning(f"Failed to detect sun: {e}")
            sun_positions = []
        
        if not sun_positions:
            logger.info("[COLLECT] No sun detected on screen")
            return PvZAction(
                action_type="collect",
                parameters={"sun_positions": []},
                gui_actions=[],
                raw_text=raw_text,
                mode="semantic"
            )
        
        # 为每个阳光位置创建点击动作
        gui_actions = []
        for x, y in sun_positions:
            gui_actions.append(
                GUI_action(
                    action_type=ActionType.CLICK,
                    parameters={"x": x, "y": y, "button": "left"}
                )
            )
            # 每次点击之间短暂延迟
            gui_actions.append(
                GUI_action(
                    action_type=ActionType.WAIT,
                    parameters={"duration": 0.05}
                )
            )
        
        return PvZAction(
            action_type="collect",
            parameters={"sun_positions": sun_positions},
            gui_actions=gui_actions,
            raw_text=raw_text,
            mode="semantic"
        )
    
    def step(self, action: PvZAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        通过 GUIManager 发送鼠标事件，执行动作。
        每次 step 后会自动检测画面中的阳光位置（使用YOLO）。
        
        Raises:
            RuntimeError: 如果游戏窗口丢失
        """
        self.step_count += 1
        
        # 检查游戏窗口是否仍然可用
        if self.game_window is None:
            raise RuntimeError("Game window is not available. Cannot execute step.")
        
        # 尝试刷新窗口确保它仍然存在
        try:
            self.game_window = self.gui_manager.refresh_window(self.game_window)
        except Exception as e:
            raise RuntimeError(f"Game window lost during step {self.step_count}: {e}")
        
        # 执行 GUI 动作序列
        self._execute_action(action)
        
        # 等待游戏响应
        time.sleep(self.cfg.screenshot_interval)
        
        # 截图
        image = self._capture_screen()
        
        # 保存截图
        image_path = f"{self.log_path}/obs_image/step_{self.step_count:04d}.png"
        image.save(image_path)
        
        # 检查游戏是否结束（超时检查）
        elapsed_time = time.time() - self.start_time
        terminated = elapsed_time > self.cfg.timeout
        
        obs = PvZObs(
            image=image,
            log_obs=f"Step {self.step_count} completed.",
            game_state="playing" if not terminated else "timeout",
            terminated=terminated,
            info={"elapsed_time": elapsed_time}
        )
        
        return obs, 0, terminated, False, {"action": action.to_json()}
    
    def _execute_action(self, action: PvZAction):
        """执行 GUI 动作序列"""
        if self.gui_manager is None or self.game_window is None:
            logger.warning("GUI manager not available, cannot execute action")
            return
        
        # 刷新窗口信息
        try:
            self.game_window = self.gui_manager.refresh_window(self.game_window)
        except Exception as e:
            logger.warning(f"Failed to refresh window: {e}")
        
        # 激活窗口
        self.gui_manager.activate(self.game_window)
        time.sleep(0.1)
        
        # 执行每个 GUI 动作
        for gui_action in action.gui_actions:
            try:
                # 处理等待动作
                if gui_action.action_type == ActionType.WAIT:
                    duration = gui_action.parameters.get("duration", 0.1)
                    time.sleep(duration)
                    continue
                
                # 执行动作
                success = self.gui_manager.execute(self.game_window, gui_action)
                
                if success:
                    logger.info(f"Executed action: {gui_action.to_dict()}")
                else:
                    logger.warning(f"Failed to execute action: {gui_action.to_dict()}")
                
                # 动作之间的短暂延迟
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error executing action {gui_action.to_dict()}: {e}")
    
    def evaluate(self, obs: PvZObs) -> Tuple[float, bool]:
        """
        评估当前状态（已废弃结束判定，仅返回固定值）
        
        Returns:
            (score, done) 元组 - done 始终为 False
        """
        # 不再判定游戏是否结束，由 max_steps 控制
        return 0.0, False
    
    def get_game_info(self) -> dict:
        """获取游戏信息，用于填充 prompt"""
        window_width, window_height = self._get_window_size()
        return {
            "prev_state_str": None,
            "task_description": self.cfg.task,
            "grid_size": f"{self.cfg.grid_rows}x{self.cfg.grid_cols}",
            "action_mode": self.action_mode,
            "window_width": window_width,
            "window_height": window_height
        }
    
    def close(self):
        """关闭环境"""
        if self.game_process is not None:
            try:
                self.game_process.terminate()
            except Exception as e:
                logger.warning(f"Failed to terminate game process: {e}")
        
        logger.info("PvZ Environment closed")


# ======================== 辅助函数 ========================

def create_pvz_env(config_path: str = None, **kwargs) -> PvzEnv:
    """
    工厂函数：创建 PvZ 环境实例
    
    Args:
        config_path: 配置文件路径
        **kwargs: 额外的配置参数
        
    Returns:
        PvzEnv 实例
    """
    import yaml
    
    if config_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.yaml")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # 合并额外参数
    env_config = config.get('env', {})
    env_config.update(kwargs)
    
    # 创建配置对象
    cfg = PvzEnv.Config(
        log_path=config.get('log_path', './logs'),
        task=env_config.get('task', 'Defend your house from zombies'),
        window_title=env_config.get('window_title', 'Plants vs. Zombies'),
        game_path=env_config.get('game_path', ''),
        action_mode=env_config.get('action_mode', 'semantic'),
        timeout=env_config.get('timeout', 600),
        screenshot_interval=env_config.get('screenshot_interval', 0.5),
        auto_collect_sun=env_config.get('auto_collect_sun', False),
    )
    
    # 创建环境
    env = PvzEnv()
    env.cfg = cfg
    env.configure()
    
    return env
