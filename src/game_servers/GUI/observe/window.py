"""
窗口管理模块

定义 WindowInfo 数据类和 WindowManager 抽象基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass
class WindowInfo:
    """
    窗口信息数据类
    
    Attributes:
        pid: 进程ID
        title: 窗口标题
        left: 窗口左边界X坐标
        top: 窗口上边界Y坐标
        width: 窗口宽度
        height: 窗口高度
        handle: 平台特定的窗口句柄
    """
    pid: int
    title: str
    left: int
    top: int
    width: int
    height: int
    handle: Any = None  # 平台特定句柄 (HWND on Windows, window dict on macOS, window id on Linux)
    
    @property
    def right(self) -> int:
        """窗口右边界X坐标"""
        return self.left + self.width
    
    @property
    def bottom(self) -> int:
        """窗口下边界Y坐标"""
        return self.top + self.height
    
    @property
    def center(self) -> Tuple[int, int]:
        """窗口中心坐标"""
        return (self.left + self.width // 2, self.top + self.height // 2)
    
    @property
    def rect(self) -> Tuple[int, int, int, int]:
        """返回 (left, top, width, height)"""
        return (self.left, self.top, self.width, self.height)
    
    def __repr__(self) -> str:
        return (f"WindowInfo(pid={self.pid}, title='{self.title}', "
                f"rect=({self.left}, {self.top}, {self.width}, {self.height}))")


class WindowManager(ABC):
    """
    窗口管理器抽象基类
    
    定义跨平台窗口操作的通用接口
    """
    
    @abstractmethod
    def find_windows_by_pattern(self, title_pattern: str) -> List[WindowInfo]:
        """
        通过标题正则表达式查找窗口
        
        Args:
            title_pattern: 窗口标题的正则表达式
            
        Returns:
            匹配的窗口列表
        """
        pass
    
    @abstractmethod
    def get_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """
        通过进程ID获取窗口
        
        Args:
            pid: 进程ID
            
        Returns:
            对应的窗口，如果没找到返回None
        """
        pass
    
    @abstractmethod
    def activate_window(self, window: WindowInfo) -> bool:
        """
        激活（置于前台）指定窗口
        
        Args:
            window: 目标窗口
            
        Returns:
            是否成功激活
        """
        pass
    
    @abstractmethod
    def get_window_rect(self, window: WindowInfo) -> Tuple[int, int, int, int]:
        """
        获取窗口的位置和大小
        
        Args:
            window: 目标窗口
            
        Returns:
            (left, top, width, height) 元组
        """
        pass
    
    @abstractmethod
    def refresh_window(self, window: WindowInfo) -> WindowInfo:
        """
        刷新窗口信息（窗口可能已移动或调整大小）
        
        Args:
            window: 目标窗口
            
        Returns:
            更新后的窗口信息
        """
        pass
    
    @abstractmethod
    def list_all_windows(self) -> List[WindowInfo]:
        """
        列出所有可见窗口
        
        Returns:
            所有窗口列表
        """
        pass
