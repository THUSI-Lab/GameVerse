"""
Windows 平台动作执行器

使用 pydirectinput 实现，适合游戏输入
"""

import time
from typing import Optional

from ..executor import ActionExecutor

# Windows-specific imports (延迟导入以支持跨平台)
pydirectinput = None
pyautogui = None


def _ensure_imports():
    """确保 Windows 依赖已导入"""
    global pydirectinput, pyautogui
    if pydirectinput is None:
        import pydirectinput as pdi
        import pyautogui as pag
        pydirectinput = pdi
        pyautogui = pag
        
        # 禁用 failsafe
        pydirectinput.FAILSAFE = False
        pyautogui.FAILSAFE = False


class WindowsActionExecutor(ActionExecutor):
    """
    Windows 平台动作执行器
    
    使用 pydirectinput 进行键盘操作，游戏兼容性更好
    使用 pyautogui 进行鼠标和文本输入操作
    """
    
    def __init__(self, window):
        super().__init__(window)
        _ensure_imports()
    
    def _do_move(self, x: int, y: int) -> None:
        """移动鼠标"""
        pydirectinput.moveTo(x, y)
    
    def _do_move_by(self, dx: int, dy: int, duration: float = 0.0) -> None:
        """相对移动鼠标（用于视角/相机控制）"""
        pydirectinput.move(dx, dy)  # pydirectinput doesn't support duration for relative move
    
    def _do_click(self, x: Optional[int], y: Optional[int], 
                  button: str, clicks: int) -> None:
        """点击鼠标"""
        if x is not None and y is not None:
            pydirectinput.click(x=x, y=y, button=button, clicks=clicks)
        else:
            pydirectinput.click(button=button, clicks=clicks)
    
    def _do_mouse_down(self, button: str) -> None:
        """按下鼠标按键"""
        pydirectinput.mouseDown(button=button)
    
    def _do_mouse_up(self, button: str) -> None:
        """释放鼠标按键"""
        pydirectinput.mouseUp(button=button)
    
    def _do_drag(self, x: int, y: int) -> None:
        """拖拽到目标位置"""
        pyautogui.drag(
            x - pyautogui.position()[0], 
            y - pyautogui.position()[1], 
            duration=1.0
        )
    
    def _do_scroll(self, dx: int, dy: int) -> None:
        """滚动鼠标滚轮"""
        # pydirectinput only supports vertical scroll in some versions, check compatibility
        # For safety, use pyautogui for scroll as it's less likely to be blocked by anticheat for UI ops
        if dy != 0:
            pyautogui.scroll(dy)
        if dx != 0:
            pyautogui.hscroll(dx)
    
    def _do_type(self, text: str, interval: float) -> None:
        """输入文本"""
        pyautogui.typewrite(text, interval=interval)
    
    def _do_press(self, key: str, duration: Optional[float]) -> None:
        """按下并释放按键"""
        if duration is not None and duration > 0:
            pydirectinput.keyDown(key)
            time.sleep(duration)
            pydirectinput.keyUp(key)
        else:
            pydirectinput.press(key)
    
    def _do_key_down(self, key: str) -> None:
        """按下按键"""
        pydirectinput.keyDown(key)
    
    def _do_key_up(self, key: str) -> None:
        """释放按键"""
        pydirectinput.keyUp(key)
    
    def _do_hotkey(self, keys: list) -> None:
        """按下组合键"""
        pydirectinput.hotkey(*keys)
