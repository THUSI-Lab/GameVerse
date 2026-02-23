# GUI Manager

## 目录结构

```
GUI_manager/
├── __init__.py          # 主入口，GUIManager 类
├── README.md            # 本文件
├── example.py           # 使用示例
├── act/
│   ├── __init__.py
│   ├── actions.py       # Action Space 定义
│   ├── executor.py      # ActionExecutor 抽象基类
│   └── platforms/
│       ├── windows.py   # Windows 实现
│       ├── macos.py     # macOS 实现
│       └── linux.py     # Linux 实现
└── observe/
    ├── __init__.py
    ├── window.py        # WindowInfo 和 WindowManager 抽象基类
    ├── screenshot.py    # ScreenCapture 类
    └── platforms/
        ├── windows.py   # Windows 窗口管理
        ├── macos.py     # macOS 窗口管理
        └── linux.py     # Linux 窗口管理
```


## 安装依赖

```bash
pip install pillow mss pyautogui
```

### Windows 额外依赖

```bash
pip install pywin32 pydirectinput
```

### macOS 额外依赖

```bash
pip install pyobjc-framework-Quartz
```

### Linux 额外依赖

```bash
# 系统工具
sudo apt install wmctrl xdotool  # Debian/Ubuntu
```

## Example

```python
from GUI_manager import GUIManager, Action, ActionType

# 初始化
gui = GUIManager()

# 查找窗口（支持正则表达式）
window = gui.find_window(r".*GameName.*")

# 激活窗口
gui.activate(window)

# 截图
screenshot = gui.capture(window, save_path="./screenshot.png")

# 执行动作（坐标为窗口内相对像素坐标）
gui.execute(window, Action(ActionType.CLICK, {"x": 100, "y": 200}))
gui.execute(window, Action(ActionType.PRESS, {"key": "enter", "duration": 0.5}))
```

## Action Space

### 鼠标操作

| Action Type      | 参数                         | 说明               |
| ---------------- | ---------------------------- | ------------------ |
| `MOVE_TO`      | `x, y`                     | 移动鼠标到指定位置 |
| `CLICK`        | `x, y, button, num_clicks` | 点击               |
| `RIGHT_CLICK`  | `x, y`                     | 右键点击           |
| `DOUBLE_CLICK` | `x, y`                     | 双击               |
| `MOUSE_DOWN`   | `button?`                  | 按下鼠标按键       |
| `MOUSE_UP`     | `button?`                  | 释放鼠标按键       |
| `DRAG_TO`      | `x, y`                     | 拖拽到目标位置     |
| `SCROLL`       | `dx, dy`                   | 滚动鼠标滚轮       |

### 键盘操作

| Action Type  | 参数               | 说明                             |
| ------------ | ------------------ | -------------------------------- |
| `TYPING`   | `text, interval` | 逐字符输入文本(可能被输入法影响) |
| `PRESS`    | `key, duration?` | 按下并释放按键（可指定时长）     |
| `KEY_DOWN` | `key`            | 按下按键（不释放）               |
| `KEY_UP`   | `key`            | 释放按键                         |
| `HOTKEY`   | `keys[]`         | 组合键                           |

### 控制流——目前暂时没有用到

| Action Type | 参数         | 说明                    |
| ----------- | ------------ | ----------------------- |
| `WAIT`    | `duration` | 等待指定时间（默认1秒） |
| `DONE`    | -            | 标记任务完成            |
| `FAIL`    | -            | 标记任务失败            |

## 坐标系统

所有坐标参数使用**窗口内相对像素坐标**：

- 原点 `(0, 0)` 为窗口左上角
- X 轴向右为正
- Y 轴向下为正

框架会自动将相对坐标转换为屏幕绝对坐标。

## API 参考

### GUIManager

| 方法                           | 说明                 |
| ------------------------------ | -------------------- |
| `find_window(pattern)`       | 通过标题正则查找窗口 |
| `find_all_windows(pattern)`  | 查找所有匹配窗口     |
| `get_window_by_pid(pid)`     | 通过 PID 获取窗口    |
| `activate(window)`           | 激活窗口             |
| `capture(window, save_path)` | 截图                 |
| `execute(window, action)`    | 执行动作             |
| `list_all_windows()`         | 列出所有窗口         |
| `refresh_window(window)`     | 刷新窗口信息         |

### WindowInfo

| 属性              | 说明                            |
| ----------------- | ------------------------------- |
| `pid`           | 进程 ID                         |
| `title`         | 窗口标题                        |
| `left, top`     | 窗口位置                        |
| `width, height` | 窗口大小                        |
| `rect`          | 返回 (left, top, width, height) |
| `center`        | 返回窗口中心坐标                |
