"""
GUI Manager - 跨平台游戏GUI操作框架

支持 Windows / macOS / Linux 平台的:
- 窗口定位与管理
- 屏幕截图
- GUI动作执行 (鼠标、键盘)
"""

import platform
from typing import Optional, List, Union
from PIL import Image

from .observe.window import WindowInfo, WindowManager
from .observe.screenshot import ScreenCapture
from .act.actions import GUI_action, ActionType
from .act.executor import ActionExecutor


def _get_platform() -> str:
    """获取当前运行平台"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        raise NotImplementedError(f"Unsupported platform: {system}")


def _create_window_manager() -> WindowManager:
    """根据平台创建对应的WindowManager实例"""
    plat = _get_platform()
    if plat == "windows":
        from .observe.platforms.windows import WindowsWindowManager
        return WindowsWindowManager()
    elif plat == "macos":
        from .observe.platforms.macos import MacOSWindowManager
        return MacOSWindowManager()
    elif plat == "linux":
        from .observe.platforms.linux import LinuxWindowManager
        return LinuxWindowManager()


def _create_action_executor(window: WindowInfo) -> ActionExecutor:
    """根据平台创建对应的ActionExecutor实例"""
    plat = _get_platform()
    if plat == "windows":
        from .act.platforms.windows import WindowsActionExecutor
        return WindowsActionExecutor(window)
    elif plat == "macos":
        from .act.platforms.macos import MacOSActionExecutor
        return MacOSActionExecutor(window)
    elif plat == "linux":
        from .act.platforms.linux import LinuxActionExecutor
        return LinuxActionExecutor(window)


class GUIManager:
    """
    统一的GUI管理器接口
    
    Usage:
        gui = GUIManager()
        window = gui.find_window(r".*Game.*")
        gui.activate(window)
        screenshot = gui.capture(window)
        gui.execute(window, Action("CLICK", {"x": 100, "y": 200}))
    """
    
    def __init__(self):
        self.platform = _get_platform()
        self._window_manager = _create_window_manager()
        self._screen_capture = ScreenCapture()
        self._executors: dict = {}  # 缓存每个窗口的executor
    
    def find_window(self, title_pattern: str) -> Optional[WindowInfo]:
        """
        通过标题正则表达式查找窗口
        
        Args:
            title_pattern: 窗口标题的正则表达式
            
        Returns:
            匹配的第一个窗口，如果没找到返回None
        """
        windows = self._window_manager.find_windows_by_pattern(title_pattern)
        if windows:
            return windows[0]
        return None
    
    def find_all_windows(self, title_pattern: str) -> List[WindowInfo]:
        """
        通过标题正则表达式查找所有匹配的窗口
        
        Args:
            title_pattern: 窗口标题的正则表达式
            
        Returns:
            所有匹配的窗口列表
        """
        return self._window_manager.find_windows_by_pattern(title_pattern)
    
    def get_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """
        通过进程ID获取窗口
        
        Args:
            pid: 进程ID
            
        Returns:
            对应的窗口，如果没找到返回None
        """
        return self._window_manager.get_window_by_pid(pid)
    
    def activate(self, window: WindowInfo) -> bool:
        """
        激活（置于前台）指定窗口
        
        Args:
            window: 目标窗口
            
        Returns:
            是否成功激活
        """
        
        return self._window_manager.activate_window(window)
    
    def get_window_rect(self, window: WindowInfo) -> tuple:
        """
        获取窗口的位置和大小
        
        Args:
            window: 目标窗口
            
        Returns:
            (left, top, width, height) 元组
        """
        return self._window_manager.get_window_rect(window)
    
    def refresh_window(self, window: WindowInfo) -> WindowInfo:
        """
        刷新窗口信息（位置可能已变化）
        
        Args:
            window: 目标窗口
            
        Returns:
            更新后的窗口信息
        """
        return self._window_manager.refresh_window(window)
    
    def capture(self, window: Optional[WindowInfo] = None, 
                save_path: Optional[str] = None) -> Image.Image:
        """
        截取屏幕或指定窗口
        
        Args:
            window: 目标窗口，如果为None则截取全屏
            save_path: 保存路径，如果提供则保存截图
            
        Returns:
            PIL Image对象
        """
        if window is None:
            return self._screen_capture.capture_fullscreen(save_path)
        else:
            # 先刷新窗口位置信息
            window = self.refresh_window(window)
            return self._screen_capture.capture_window(window, save_path)
    
    def execute(self, window: WindowInfo, action: Union[GUI_action, dict]) -> bool:
        """
        在指定窗口执行动作
        
        Args:
            window: 目标窗口（动作坐标为窗口内相对坐标）
            action: Action对象或字典格式的动作
            
        Returns:
            是否执行成功
        """
        # 支持字典格式输入
        # {
        #     'action_type': str or ActionType
        #     'parameters': 
        # }
        if isinstance(action, dict):
            action = GUI_action.from_dict(action)
        
        # 获取或创建executor
        executor = self._get_executor(window)
        
        return executor.execute(action)
    
    def _get_executor(self, window: WindowInfo) -> ActionExecutor:
        """获取窗口对应的ActionExecutor，使用缓存"""
        # 使用pid作为key，因为同一进程的窗口使用同一个executor
        key = window.pid
        if key not in self._executors:
            self._executors[key] = _create_action_executor(window)
        else:
            # 更新窗口信息
            self._executors[key].window = window
        return self._executors[key]
    
    def list_all_windows(self) -> List[WindowInfo]:
        """列出所有可见窗口"""
        return self._window_manager.list_all_windows()
