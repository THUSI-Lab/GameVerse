"""
macOS 平台窗口管理实现

使用 Quartz 和 AppKit 实现
"""

import re
import subprocess
from typing import List, Optional, Tuple

from ..window import WindowInfo, WindowManager

# 延迟导入 macOS 特定模块
Quartz = None


def _ensure_imports():
    """确保 macOS 依赖已导入"""
    global Quartz
    if Quartz is None:
        import Quartz as Q
        Quartz = Q


class MacOSWindowManager(WindowManager):
    """
    macOS 平台窗口管理器
    """
    
    def __init__(self):
        _ensure_imports()
    
    def find_windows_by_pattern(self, title_pattern: str) -> List[WindowInfo]:
        """通过标题正则表达式查找窗口"""
        results = []
        pattern = re.compile(title_pattern)
        
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
        
        for window in window_list:
            owner_name = window.get("kCGWindowOwnerName", "")
            window_name = window.get("kCGWindowName", "")
            
            # 尝试匹配窗口名或应用名
            title = window_name or owner_name
            if title and pattern.search(title):
                window_info = self._dict_to_window_info(window)
                if window_info:
                    results.append(window_info)
        
        return results
    
    def get_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """通过进程ID获取窗口"""
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
        
        for window in window_list:
            window_pid = window.get("kCGWindowOwnerPID", 0)
            if window_pid == pid:
                window_info = self._dict_to_window_info(window)
                if window_info:
                    return window_info
        
        return None
    
    def activate_window(self, window: WindowInfo) -> bool:
        """激活指定窗口"""
        try:
            # 获取应用名
            app_name = window.title
            if not app_name:
                return False
            
            # 使用 AppleScript 激活应用
            applescript = f'''
            tell application "{app_name}"
                activate
            end tell
            '''
            
            subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True
            )
            return True
        except Exception as e:
            print(f"Failed to activate window: {e}")
            return False
    
    def get_window_rect(self, window: WindowInfo) -> Tuple[int, int, int, int]:
        """获取窗口位置和大小"""
        return (window.left, window.top, window.width, window.height)
    
    def refresh_window(self, window: WindowInfo) -> WindowInfo:
        """刷新窗口信息"""
        # 通过 PID 查找更新后的窗口
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
        
        for win in window_list:
            if win.get("kCGWindowNumber") == window.handle:
                new_info = self._dict_to_window_info(win)
                if new_info:
                    return new_info
        
        return window
    
    def list_all_windows(self) -> List[WindowInfo]:
        """列出所有可见窗口"""
        results = []
        
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID
        )
        
        for window in window_list:
            owner_name = window.get("kCGWindowOwnerName", "")
            if owner_name:  # 只列出有所有者的窗口
                window_info = self._dict_to_window_info(window)
                if window_info:
                    results.append(window_info)
        
        return results
    
    def _dict_to_window_info(self, window_dict: dict) -> Optional[WindowInfo]:
        """将 Quartz 窗口字典转换为 WindowInfo"""
        try:
            bounds = window_dict.get("kCGWindowBounds", {})
            
            pid = window_dict.get("kCGWindowOwnerPID", 0)
            title = window_dict.get("kCGWindowOwnerName", "") or window_dict.get("kCGWindowName", "")
            left = int(bounds.get("X", 0))
            top = int(bounds.get("Y", 0))
            width = int(bounds.get("Width", 0))
            height = int(bounds.get("Height", 0))
            handle = window_dict.get("kCGWindowNumber")
            
            if width <= 0 or height <= 0:
                return None
            
            return WindowInfo(
                pid=pid,
                title=title,
                left=left,
                top=top,
                width=width,
                height=height,
                handle=handle
            )
        except Exception:
            return None
