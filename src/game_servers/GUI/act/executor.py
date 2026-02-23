"""
ActionExecutor 抽象基类

定义动作执行器的通用接口和坐标转换逻辑
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from .actions import GUI_action, ActionType


class ActionExecutor(ABC):
    """
    动作执行器抽象基类
    
    负责将相对坐标转换为屏幕绝对坐标，并执行具体动作
    """
    
    def __init__(self, window):
        """
        初始化执行器
        
        Args:
            window: WindowInfo对象，包含窗口位置信息
        """
        self.window = window
    
    def _to_screen_coords(self, x: Optional[int], y: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
        """
        将窗口内相对坐标转换为屏幕绝对坐标
        
        Args:
            x: 窗口内X坐标
            y: 窗口内Y坐标
            
        Returns:
            (screen_x, screen_y) 屏幕绝对坐标
        """
        if x is None or y is None:
            return (None, None)
        
        screen_x = self.window.left + x
        screen_y = self.window.top + y
        
        return (screen_x, screen_y)
    
    def _validate_coords(self, x: int, y: int) -> bool:
        """
        验证坐标是否在窗口范围内
        
        Args:
            x: 窗口内X坐标
            y: 窗口内Y坐标
            
        Returns:
            是否有效
        """
        return (0 <= x <= self.window.width and 
                0 <= y <= self.window.height)
    
    def execute(self, action: GUI_action) -> bool:
        """
        执行动作
        
        Args:
            action: Action对象
            
        Returns:
            是否执行成功
        """
        action_type = action.action_type
        
        try:
            if action_type == ActionType.MOVE_TO:
                screen_x, screen_y = self._to_screen_coords(action.x, action.y)
                self._do_move(screen_x, screen_y)
                
            elif action_type == ActionType.MOVE_BY:
                # 相对移动不需要坐标转换，直接传递偏移量
                duration = action.duration if action.duration else 0.0
                self._do_move_by(action.dx, action.dy, duration)
                
            elif action_type == ActionType.CLICK:
                if action.x is not None and action.y is not None:
                    screen_x, screen_y = self._to_screen_coords(action.x, action.y)
                else:
                    screen_x, screen_y = None, None
                self._do_click(screen_x, screen_y, action.button, action.num_clicks)
                
            elif action_type == ActionType.RIGHT_CLICK:
                if action.x is not None and action.y is not None:
                    screen_x, screen_y = self._to_screen_coords(action.x, action.y)
                else:
                    screen_x, screen_y = None, None
                self._do_click(screen_x, screen_y, 'right', 1)
                
            elif action_type == ActionType.DOUBLE_CLICK:
                if action.x is not None and action.y is not None:
                    screen_x, screen_y = self._to_screen_coords(action.x, action.y)
                else:
                    screen_x, screen_y = None, None
                self._do_click(screen_x, screen_y, 'left', 2)
                
            elif action_type == ActionType.MOUSE_DOWN:
                self._do_mouse_down(action.button)
                
            elif action_type == ActionType.MOUSE_UP:
                self._do_mouse_up(action.button)
                
            elif action_type == ActionType.DRAG_TO:
                screen_x, screen_y = self._to_screen_coords(action.x, action.y)
                self._do_drag(screen_x, screen_y)
                
            elif action_type == ActionType.SCROLL:
                self._do_scroll(action.dx, action.dy)
                
            elif action_type == ActionType.TYPING:
                self._do_type(action.text, action.interval)
                
            elif action_type == ActionType.PRESS:
                self._do_press(action.key, action.duration)
                
            elif action_type == ActionType.KEY_DOWN:
                self._do_key_down(action.key)
                
            elif action_type == ActionType.KEY_UP:
                self._do_key_up(action.key)
                
            elif action_type == ActionType.HOTKEY:
                self._do_hotkey(action.keys)
                
            elif action_type == ActionType.WAIT:
                duration = action.duration if action.duration else 1.0
                time.sleep(duration)
                
            elif action_type == ActionType.DONE:
                return True
                
            elif action_type == ActionType.FAIL:
                return False
            
            else:
                raise ValueError(f"Unknown action type: {action_type}")
            
            return True
            
        except Exception as e:
            print(f"Error executing action {action_type}: {e}")
            return False
    
    # ============ 抽象方法：由平台特定实现 ============
    
    @abstractmethod
    def _do_move(self, x: int, y: int) -> None:
        """移动鼠标到屏幕绝对坐标"""
        pass
    
    @abstractmethod
    def _do_move_by(self, dx: int, dy: int, duration: float = 0.0) -> None:
        """相对移动鼠标（用于视角/相机控制）"""
        pass
    
    @abstractmethod
    def _do_click(self, x: Optional[int], y: Optional[int], 
                  button: str, clicks: int) -> None:
        """点击鼠标"""
        pass
    
    @abstractmethod
    def _do_mouse_down(self, button: str) -> None:
        """按下鼠标按键"""
        pass
    
    @abstractmethod
    def _do_mouse_up(self, button: str) -> None:
        """释放鼠标按键"""
        pass
    
    @abstractmethod
    def _do_drag(self, x: int, y: int) -> None:
        """拖拽到目标位置"""
        pass
    
    @abstractmethod
    def _do_scroll(self, dx: int, dy: int) -> None:
        """滚动鼠标滚轮"""
        pass
    
    @abstractmethod
    def _do_type(self, text: str, interval: float) -> None:
        """输入文本"""
        pass
    
    @abstractmethod
    def _do_press(self, key: str, duration: Optional[float]) -> None:
        """按下并释放按键"""
        pass
    
    @abstractmethod
    def _do_key_down(self, key: str) -> None:
        """按下按键"""
        pass
    
    @abstractmethod
    def _do_key_up(self, key: str) -> None:
        """释放按键"""
        pass
    
    @abstractmethod
    def _do_hotkey(self, keys: list) -> None:
        """按下组合键"""
        pass
