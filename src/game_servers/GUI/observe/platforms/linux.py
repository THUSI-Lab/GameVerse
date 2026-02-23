"""
Linux 平台窗口管理实现

使用 wmctrl 和 xdotool 作为主要实现方案
"""

import re
import subprocess
import shutil
from typing import List, Optional, Tuple

from ..window import WindowInfo, WindowManager


def _has_wmctrl() -> bool:
    """检查是否安装了 wmctrl"""
    return shutil.which("wmctrl") is not None


def _has_xdotool() -> bool:
    """检查是否安装了 xdotool"""
    return shutil.which("xdotool") is not None


class LinuxWindowManager(WindowManager):
    """
    Linux 平台窗口管理器

    使用 wmctrl 和 xdotool 作为主要实现方案
    """

    def __init__(self):
        self._use_wmctrl = _has_wmctrl()
        self._use_xdotool = _has_xdotool()

        if not self._use_wmctrl:
            raise RuntimeError(
                "Linux window management requires wmctrl. "
                "Install with: sudo apt install wmctrl"
            )
    
    def find_windows_by_pattern(self, title_pattern: str) -> List[WindowInfo]:
        """通过标题正则表达式查找窗口"""
        pattern = re.compile(title_pattern)
        return self._find_windows_wmctrl(pattern)
    
    def get_window_by_pid(self, pid):

        try:
            output = subprocess.check_output(
                ["wmctrl", "-l", "-p"],
                text=True
            )
            # wmctrl output: 0x04400008  0  pid:7117   <user>  <window title>
            for line in output.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(None, 4)
                if len(parts) >= 5:
                    window_id_str = parts[0]
                    pid_now = int(parts[2])
                    title = parts[4]

                    if pid == pid_now:
                        # 获取窗口几何信息
                        geometry = self._get_window_geometry_xdotool(window_id_str)
                        if geometry:
                            left, top, width, height = geometry
                            return (WindowInfo(
                                pid=pid,
                                title=title,
                                left=left,
                                top=top,
                                width=width,
                                height=height,
                                handle=window_id_str
                            ))
                    
                print("no pid matched")
        except Exception as e:
            print("get_window_by_pid failed")
            print(f"wmctrl failed: {e}")
    
    def _find_windows_wmctrl(self, pattern: re.Pattern) -> List[WindowInfo]:
        """使用 wmctrl 查找窗口"""
        results = []

        try:
            output = subprocess.check_output(
                ["wmctrl", "-l", "-p"],
                text=True
            )
            # wmctrl output: 0x04400008  0  pid:7117   <user>  <window title>
            for line in output.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(None, 4)
                if len(parts) >= 5:
                    window_id_str = parts[0]
                    pid = int(parts[2])
                    title = parts[4]

                    if pattern.search(title):
                        # 获取窗口几何信息
                        geometry = self._get_window_geometry_xdotool(window_id_str)
                        if geometry:
                            left, top, width, height = geometry
                            results.append(WindowInfo(
                                pid=pid,
                                title=title,
                                left=left,
                                top=top,
                                width=width,
                                height=height,
                                handle=window_id_str
                            ))
        except Exception as e:
            print(f"wmctrl failed: {e}")

        return results
    
    def activate_window(self, window: WindowInfo) -> bool:
        """激活指定窗口"""
        try:
            if self._use_wmctrl:
                # wmctrl -i -a <window_id>
                subprocess.run(
                    ["wmctrl", "-i", "-a", str(window.handle)],
                    check=True
                )
                return True
            elif self._use_xdotool:
                # xdotool windowactivate <window_id>
                subprocess.run(
                    ["xdotool", "windowactivate", str(window.handle)],
                    check=True
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
        if self._use_xdotool:
            geometry = self._get_window_geometry_xdotool(window.handle)
            if geometry:
                left, top, width, height = geometry
                return WindowInfo(
                    pid=window.pid,
                    title=window.title,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    handle=window.handle
                )

        return window
    
    def list_all_windows(self) -> List[WindowInfo]:
        """列出所有可见窗口"""
        results = []

        try:
            output = subprocess.check_output(
                ["wmctrl", "-l", "-p"],
                text=True
            )

            for line in output.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(None, 4)
                if len(parts) >= 5:
                    window_id_str = parts[0]
                    pid = int(parts[2])
                    title = parts[4]

                    geometry = self._get_window_geometry_xdotool(window_id_str)
                    if geometry:
                        left, top, width, height = geometry
                        results.append(WindowInfo(
                            pid=pid,
                            title=title,
                            left=left,
                            top=top,
                            width=width,
                            height=height,
                            handle=window_id_str
                        ))
        except Exception:
            pass

        return results

    def _get_window_geometry_xdotool(self, window_id: str) -> Optional[Tuple[int, int, int, int]]:
        """
        使用 xdotool 获取窗口几何信息
        
        注意: xdotool getwindowgeometry 返回的是窗口内容区域的坐标，
        不包含窗口装饰(标题栏、边框)。为了获取准确的截图区域，
        我们使用 xwininfo 来获取绝对坐标。
        """
        if not self._use_xdotool:
            return None
        
        try:
            # 首先尝试使用 xwininfo 获取更准确的坐标（包含窗口装饰）
            try:
                output = subprocess.check_output(
                    ["xwininfo", "-id", str(window_id)],
                    text=True,
                    stderr=subprocess.DEVNULL
                )
                
                abs_x = abs_y = width = height = None
                for line in output.split("\n"):
                    line = line.strip()
                    if "Absolute upper-left X:" in line:
                        abs_x = int(line.split(":")[-1].strip())
                    elif "Absolute upper-left Y:" in line:
                        abs_y = int(line.split(":")[-1].strip())
                    elif "Width:" in line:
                        width = int(line.split(":")[-1].strip())
                    elif "Height:" in line:
                        height = int(line.split(":")[-1].strip())
                
                if all(v is not None for v in [abs_x, abs_y, width, height]):
                    return (abs_x, abs_y, width, height)
            except Exception:
                pass  # 回退到 xdotool
            
            # 回退: 使用 xdotool getwindowgeometry
            output = subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", str(window_id)],
                text=True
            )
            
            values = {}
            for line in output.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = int(value)
            
            return (
                values.get("X", 0),
                values.get("Y", 0),
                values.get("WIDTH", 0),
                values.get("HEIGHT", 0)
            )
        except Exception:
            return None
