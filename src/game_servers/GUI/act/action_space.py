from enum import Enum

class ActionType(str, Enum):
    """动作类型枚举"""
    MOVE_TO = "MOVE_TO"
    MOVE_BY = "MOVE_BY"

    CLICK = "CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"

    DRAG_TO = "DRAG_TO"
    
    SCROLL = "SCROLL"
    
    TYPING = "TYPING"

    HOTKEY = "HOTKEY"
    
    # 更低层级的动作
    MOUSE_DOWN = "MOUSE_DOWN"
    MOUSE_UP = "MOUSE_UP"
    
    PRESS = "PRESS"
    KEY_DOWN = "KEY_DOWN"
    KEY_UP = "KEY_UP"
    
    # 控制流
    WAIT = "WAIT"
    DONE = "DONE"
    FAIL = "FAIL"


# 支持的键盘按键列表
KEYBOARD_KEYS = [
    # 特殊字符
    '\t', '\n', '\r', ' ', '!', '"', '#', '$', '%', '&', "'", '(',
    ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?',
    '@', '[', '\\', ']', '^', '_', '`', '{', '|', '}', '~',
    
    # 数字
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    
    # 字母
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
    'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    
    # 功能键
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10',
    'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19',
    'f20', 'f21', 'f22', 'f23', 'f24',
    
    # 控制键
    'alt', 'altleft', 'altright',
    'ctrl', 'ctrlleft', 'ctrlright',
    'shift', 'shiftleft', 'shiftright',
    'win', 'winleft', 'winright',
    'command', 'option', 'optionleft', 'optionright',  # macOS
    
    # 编辑键
    'backspace', 'delete', 'del', 'insert',
    'home', 'end', 'pageup', 'pagedown', 'pgup', 'pgdn',
    
    # 方向键
    'up', 'down', 'left', 'right',
    
    # 其他常用键
    'enter', 'return', 'tab', 'space',
    'escape', 'esc',
    'capslock', 'numlock', 'scrolllock',
    'pause', 'printscreen', 'prntscrn', 'prtsc', 'prtscr',
    
    # 小键盘
    'num0', 'num1', 'num2', 'num3', 'num4',
    'num5', 'num6', 'num7', 'num8', 'num9',
    'add', 'subtract', 'multiply', 'divide', 'decimal',
    
    # 媒体键
    'volumeup', 'volumedown', 'volumemute',
    'playpause', 'prevtrack', 'nexttrack', 'stop',
    
    # 浏览器键
    'browserback', 'browserforward', 'browserrefresh',
    'browserhome', 'browsersearch', 'browserfavorites', 'browserstop',
    
    # 其他
    'accept', 'apps', 'clear', 'convert', 'execute', 'final',
    'fn', 'hanguel', 'hangul', 'hanja', 'help', 'junja',
    'kana', 'kanji', 'launchapp1', 'launchapp2', 'launchmail',
    'launchmediaselect', 'modechange', 'nonconvert', 'select',
    'separator', 'sleep', 'yen',
]

MOUSE_BUTTONS = ['left', 'right', 'middle']

ACTION_SPACE = [
    {
        "action_type": ActionType.MOVE_TO,
        "note": "Move mouse to specified position",
        "parameters": {
            "x": {"type": int, "required": True, "description": "Target X coordinate (relative to window)"},
            "y": {"type": int, "required": True, "description": "Target Y coordinate (relative to window)"},
        }
    },
    {
        "action_type": ActionType.MOVE_BY,
        "note": "Move mouse relatively from current position (for camera/view control)",
        "parameters": {
            "dx": {"type": int, "required": True, "description": "Horizontal offset in pixels (positive=right, negative=left)"},
            "dy": {"type": int, "required": True, "description": "Vertical offset in pixels (positive=down, negative=up)"},
            "duration": {"type": float, "required": False, "default": 0.0, "description": "Movement duration in seconds (0 for instant)"},
        }
    },
    {
        "action_type": ActionType.CLICK,
        "note": "Mouse click, can specify position, button and click count",
        "parameters": {
            "x": {"type": int, "required": False, "description": "Click X coordinate, uses current position if not specified"},
            "y": {"type": int, "required": False, "description": "Click Y coordinate, uses current position if not specified"},
            "button": {"type": str, "required": False, "default": "left", "choices": MOUSE_BUTTONS},
            "num_clicks": {"type": int, "required": False, "default": 1},
        }
    },
    {
        "action_type": ActionType.RIGHT_CLICK,
        "note": "Right mouse click",
        "parameters": {
            "x": {"type": int, "required": False},
            "y": {"type": int, "required": False},
        }
    },
    {
        "action_type": ActionType.DOUBLE_CLICK,
        "note": "Double click",
        "parameters": {
            "x": {"type": int, "required": False},
            "y": {"type": int, "required": False},
        }
    },
    {
        "action_type": ActionType.MOUSE_DOWN,
        "note": "Press mouse button (without releasing)",
        "parameters": {
            "button": {"type": str, "required": False, "default": "left", "choices": MOUSE_BUTTONS},
        }
    },
    {
        "action_type": ActionType.MOUSE_UP,
        "note": "Release mouse button",
        "parameters": {
            "button": {"type": str, "required": False, "default": "left", "choices": MOUSE_BUTTONS},
        }
    },
    {
        "action_type": ActionType.DRAG_TO,
        "note": "Drag to specified position (hold left button and drag from current position)",
        "parameters": {
            "x": {"type": int, "required": True, "description": "Target X coordinate"},
            "y": {"type": int, "required": True, "description": "Target Y coordinate"},
        }
    },
    {
        "action_type": ActionType.SCROLL,
        "note": "Scroll mouse wheel up or down",
        "parameters": {
            "dx": {"type": int, "required": True, "description": "Horizontal scroll amount (positive for right, negative for left)"},
            "dy": {"type": int, "required": True, "description": "Vertical scroll amount (positive for up, negative for down)"},
        }
    },
    {
        "action_type": ActionType.TYPING,
        "note": "Type text character by character",
        "parameters": {
            "text": {"type": str, "required": True, "description": "Text to type"},
            "interval": {"type": float, "required": False, "default": 0.05, "description": "Interval between characters (seconds)"},
        }
    },
    {
        "action_type": ActionType.PRESS,
        "note": "Press and release a key",
        "parameters": {
            "key": {"type": str, "required": True, "choices": KEYBOARD_KEYS},
            "duration": {"type": float, "required": False, "description": "Hold duration (seconds), releases immediately if not specified"},
        }
    },
    {
        "action_type": ActionType.KEY_DOWN,
        "note": "Press key (without releasing)",
        "parameters": {
            "key": {"type": str, "required": True, "choices": KEYBOARD_KEYS},
        }
    },
    {
        "action_type": ActionType.KEY_UP,
        "note": "Release key",
        "parameters": {
            "key": {"type": str, "required": True, "choices": KEYBOARD_KEYS},
        }
    },
    {
        "action_type": ActionType.HOTKEY,
        "note": "Press key combination",
        "parameters": {
            "keys": {"type": list, "required": True, "description": "List of keys, e.g. ['ctrl', 'c']"},
        }
    },
    {
        "action_type": ActionType.WAIT,
        "note": "Wait for specified duration"
    },
    {
        "action_type": ActionType.DONE,
        "note": "Mark task as completed"
    },
    {
        "action_type": ActionType.FAIL,
        "note": "Mark task as failed"
    },
]
