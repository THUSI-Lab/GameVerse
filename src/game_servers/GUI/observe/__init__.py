"""
Observe 模块 - 窗口管理和屏幕截图

包含跨平台窗口定位和截图功能
"""

from .window import WindowInfo, WindowManager
from .screenshot import ScreenCapture

__all__ = [
    'WindowInfo',
    'WindowManager',
    'ScreenCapture',
]
