"""
Windows 平台窗口管理实现

使用 win32gui 和 pyautogui 实现
"""

import re
from typing import List, Optional, Tuple

from ..window import WindowInfo, WindowManager

# 延迟导入 Windows 特定模块
win32gui = None
win32process = None
win32con = None
pyautogui = None


def _ensure_imports():
    """确保 Windows 依赖已导入"""
    global win32gui, win32process, win32con, pyautogui
    if win32gui is None:
        import win32gui as wg
        import win32process as wp
        import win32con as wc
        import pyautogui as pag
        win32gui = wg
        win32process = wp
        win32con = wc
        pyautogui = pag


class WindowsWindowManager(WindowManager):
    """
    Windows 平台窗口管理器
    """
    
    def __init__(self):
        _ensure_imports()
    
    def find_windows_by_pattern(self, title_pattern: str) -> List[WindowInfo]:
        """通过标题正则表达式查找窗口"""
        results = []
        pattern = re.compile(title_pattern)
        
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and pattern.search(title):
                    window_info = self._hwnd_to_window_info(hwnd)
                    if window_info:
                        results.append(window_info)
        
        win32gui.EnumWindows(enum_callback, None)
        return results
    
    def get_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """通过进程ID获取窗口"""
        result = None
        
        def enum_callback(hwnd, _):
            nonlocal result
            if win32gui.IsWindowVisible(hwnd):
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid:
                    window_info = self._hwnd_to_window_info(hwnd)
                    if window_info:
                        result = window_info
        
        win32gui.EnumWindows(enum_callback, None)
        return result
    
    def activate_window(self, window: WindowInfo) -> bool:
        """激活指定窗口"""
        try:
            hwnd = window.handle
            
            # 如果窗口最小化，先恢复
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # 激活窗口
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            print(f"Failed to activate window: {e}")
            return False
    
    def get_window_rect(self, window: WindowInfo) -> Tuple[int, int, int, int]:
        """
        获取窗口客户区位置和大小（不包含标题栏和边框）
        
        返回 (left, top, width, height)，其中坐标是屏幕坐标
        """
        hwnd = window.handle
        # 获取客户区大小
        client_rect = win32gui.GetClientRect(hwnd)
        client_left, client_top, client_right, client_bottom = client_rect
        client_width = client_right - client_left
        client_height = client_bottom - client_top
        
        # 将客户区左上角坐标转换为屏幕坐标
        screen_left, screen_top = win32gui.ClientToScreen(hwnd, (0, 0))
        
        return (screen_left, screen_top, client_width, client_height)
    
    def refresh_window(self, window: WindowInfo) -> WindowInfo:
        """刷新窗口信息"""
        hwnd = window.handle
        new_info = self._hwnd_to_window_info(hwnd)
        if new_info:
            return new_info
        return window  # 如果刷新失败，返回原窗口信息
    
    def list_all_windows(self) -> List[WindowInfo]:
        """列出所有可见窗口"""
        results = []
        
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # 只列出有标题的窗口
                    window_info = self._hwnd_to_window_info(hwnd)
                    if window_info:
                        results.append(window_info)
        print(results)
        win32gui.EnumWindows(enum_callback, None)
        return results
    
    def _hwnd_to_window_info(self, hwnd) -> Optional[WindowInfo]:
        """
        将 HWND 转换为 WindowInfo
        
        注意：返回的是窗口客户区坐标（不包含标题栏和边框），
        这样可以确保截图只包含游戏内容，不包含窗口装饰。
        """
        try:
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # 获取客户区大小（不包含标题栏和边框）
            client_rect = win32gui.GetClientRect(hwnd)
            client_left, client_top, client_right, client_bottom = client_rect
            client_width = client_right - client_left
            client_height = client_bottom - client_top
            
            # 将客户区左上角坐标转换为屏幕坐标
            # ClientToScreen 将客户区坐标(0,0)转换为屏幕坐标
            screen_left, screen_top = win32gui.ClientToScreen(hwnd, (0, 0))
            
            return WindowInfo(
                pid=pid,
                title=title,
                left=screen_left,
                top=screen_top,
                width=client_width,
                height=client_height,
                handle=hwnd
            )
        except Exception:
            return None