"""
Linux 平台动作执行器

使用 pyautogui 实现
"""

import time
from typing import Optional

from ..executor import ActionExecutor

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError as e:
    raise ImportError("pyautogui is required on Linux platform. Please install it via 'pip install pyautogui'") from e


class LinuxActionExecutor(ActionExecutor):
    """
    Linux 平台动作执行器
    
    使用 pyautogui 进行所有操作
    注意：在 Linux 上 pyautogui 依赖 python3-xlib
    """
    
    def __init__(self, window):
        super().__init__(window)
    
    def _do_move(self, x: int, y: int) -> None:
        """移动鼠标"""
        pyautogui.moveTo(x, y)
    
    def _do_move_by(self, dx: int, dy: int, duration: float = 0.0) -> None:
        """相对移动鼠标（用于视角/相机控制）"""
        pyautogui.move(dx, dy, duration=duration)
    
    def _do_click(self, x: Optional[int], y: Optional[int], 
                  button: str, clicks: int) -> None:
        """点击鼠标"""
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        else:
            pyautogui.click(button=button, clicks=clicks)
    
    def _do_mouse_down(self, button: str) -> None:
        """按下鼠标按键"""
        pyautogui.mouseDown(button=button)
    
    def _do_mouse_up(self, button: str) -> None:
        """释放鼠标按键"""
        pyautogui.mouseUp(button=button)
    
    def _do_drag(self, x: int, y: int) -> None:
        """拖拽到目标位置"""
        pyautogui.drag(
            x - pyautogui.position()[0], 
            y - pyautogui.position()[1], 
            duration=1.0,
        )
    
    def _do_scroll(self, dx: int, dy: int) -> None:
        """滚动鼠标滚轮"""
        if dy != 0:
            pyautogui.scroll(dy)
        if dx != 0:
            pyautogui.hscroll(dx) # 水平滚动
    
    def _do_type(self, text: str, interval: float) -> None:
        """输入文本"""
        pyautogui.typewrite(text, interval=interval)
    
    def _do_press(self, key: str, duration: Optional[float]) -> None:
        """按下并释放按键"""
        if duration is not None and duration > 0:
            pyautogui.keyDown(key)
            time.sleep(duration)
            pyautogui.keyUp(key)
        else:
            pyautogui.press(key)
    
    def _do_key_down(self, key: str) -> None:
        """按下按键"""
        pyautogui.keyDown(key)
    
    def _do_key_up(self, key: str) -> None:
        """释放按键"""
        pyautogui.keyUp(key)
    
    def _do_hotkey(self, keys: list) -> None:
        """按下组合键"""
        pyautogui.hotkey(*keys)
