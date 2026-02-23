"""
屏幕截图模块

使用 mss 和 pyautogui 实现跨平台截图
"""

import os
import logging
from datetime import datetime
from typing import Optional, Tuple

from PIL import Image

from .window import WindowInfo

logger = logging.getLogger(__name__)

# 延迟导入
mss_module = None
pyautogui_module = None


def _ensure_imports():
    """确保依赖已导入"""
    global mss_module, pyautogui_module
    if mss_module is None:
        import mss
        mss_module = mss
    if pyautogui_module is None:
        import pyautogui
        pyautogui_module = pyautogui


class ScreenCapture:
    """
    屏幕截图类
    
    支持全屏截图和指定窗口截图
    """
    
    def __init__(self):
        _ensure_imports()
    
    def capture_fullscreen(self, save_path: Optional[str] = None) -> Image.Image:
        """
        截取全屏
        
        Args:
            save_path: 保存路径，如果提供则保存截图
            
        Returns:
            PIL Image对象
        """
        with mss_module.mss() as sct:
            # 获取主显示器
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        
        if save_path:
            self._save_image(img, save_path)
        
        return img
    
    def capture_window(self, window: WindowInfo, 
                       save_path: Optional[str] = None) -> Image.Image:
        """
        截取指定窗口区域
        
        Args:
            window: 目标窗口信息
            save_path: 保存路径，如果提供则保存截图
            
        Returns:
            PIL Image对象
        """
        return self.capture_region(
            window.left, window.top, window.width, window.height,
            save_path=save_path
        )
    
    def capture_region(self, left: int, top: int, width: int, height: int,
                       save_path: Optional[str] = None) -> Image.Image:
        """
        截取屏幕指定区域
        
        Args:
            left: 左边界X坐标
            top: 上边界Y坐标
            width: 宽度
            height: 高度
            save_path: 保存路径
            
        Returns:
            PIL Image对象
        """
        try:
            with mss_module.mss() as sct:
                region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                screenshot = sct.grab(region)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        except Exception as e:
            # 如果 mss 失败（例如在 Chrome 应用窗口上），回退到 pyautogui
            logger.warning(f"mss capture failed: {e}, falling back to pyautogui")
            try:
                img = pyautogui_module.screenshot(region=(left, top, width, height))
            except Exception as e2:
                logger.error(f"pyautogui capture also failed: {e2}")
                raise RuntimeError(f"Both mss and pyautogui screenshot methods failed") from e
        
        if save_path:
            self._save_image(img, save_path)
        
        return img
    
    def _save_image(self, img: Image.Image, save_path: str) -> None:
        """
        保存图像
        
        Args:
            img: PIL Image对象
            save_path: 保存路径（可以是目录或完整文件路径）
        """
        # 如果是目录，自动生成文件名
        if os.path.isdir(save_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = os.path.join(save_path, f"screenshot_{timestamp}.png")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        img.save(save_path)
    
    @staticmethod
    def get_screen_size() -> Tuple[int, int]:
        """
        获取屏幕分辨率
        
        Returns:
            (width, height) 元组
        """
        _ensure_imports()
        with mss_module.mss() as sct:
            monitor = sct.monitors[1]
            return (monitor["width"], monitor["height"])
