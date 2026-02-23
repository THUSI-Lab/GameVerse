"""
Plants vs. Zombies 游戏常量定义

包含游戏区域布局和坐标转换函数

注意：以下像素坐标是通过 scripts/pvz_calibrate.py 校准得到的
如果游戏窗口大小不同，需要重新运行校准脚本
"""

from typing import Tuple


# ============================================================
# 游戏窗口布局常量 (通过 pvz_calibrate.py 校准得到)
# 校准时间: 2025-12-10 (基于客户区坐标，不含标题栏)
# ============================================================

# --- 游戏窗口尺寸 (客户区大小) ---
DEFAULT_WINDOW_WIDTH = 800
DEFAULT_WINDOW_HEIGHT = 600

# --- Back to Game 按钮配置 ---
# 用于自动点击继续游戏（测试者需要在暂停界面准备，框架会自动点击此按钮开始）
# 通过 pvz_calibrate.py 校准得到
BACK_TO_GAME_X = 400  # Back to Game 按钮中心 X 坐标 (默认值，需要通过校准确认)
BACK_TO_GAME_Y = 500  # Back to Game 按钮中心 Y 坐标 (默认值，需要通过校准确认)

# --- 草坪网格配置 ---
# 草坪是 5行 x 9列 的网格
# 注意：内部使用 0-based 索引 (0-4, 0-8)
#       用户接口使用 1-based 索引 (1-5, 1-9)
GRID_ROWS = 5  # 行数 (内部 0-4, 用户 1-5, 从上到下)
GRID_COLS = 9  # 列数 (内部 0-8, 用户 1-9, 从左到右)
GRID_CELL_WIDTH = 81  # 每个格子的宽度 (像素)
GRID_CELL_HEIGHT = 99  # 每个格子的高度 (像素)
GRID_OFFSET_X = 37  # 草坪(0,0)格子中心X减去半格宽度
GRID_OFFSET_Y = 78  # 草坪(0,0)格子中心Y减去半格高度

# --- 植物卡槽栏配置 ---
# 通过点击前3个卡槽中心校准得到
# 注意：内部使用 0-based 索引 (Slot 0-7)
#       用户接口使用 1-based 索引 (Slot 1-8)
# Slot 0 (用户视角为 Slot 1) 中心: (121, 42)
# Slot 1 (用户视角为 Slot 2) 中心: (180, 43)
# Slot 2 (用户视角为 Slot 3) 中心: (238, 44)
PLANT_SLOT_WIDTH = 58  # 每个卡槽的宽度 (像素) - 从连续卡槽测量
NUM_PLANT_SLOTS = 8  # 可用的植物卡槽数量
SLOT_CENTER_Y = 43  # 卡槽中心的 Y 坐标 (直接用于点击)


# ============================================================
# 坐标转换函数
# ============================================================

def grid_to_screen(row: int, col: int) -> Tuple[int, int]:
    """
    将草坪格子坐标转换为屏幕坐标（格子中心）
    
    Args:
        row: 行号 (内部 0-based: 0-4, 从上到下)
        col: 列号 (内部 0-based: 0-8, 从左到右)
        
    Returns:
        (screen_x, screen_y) 格子中心的屏幕坐标
    
    注意：此函数使用 0-based 索引，用户输入的 1-based 索引已在调用前转换
    """
    x = GRID_OFFSET_X + col * GRID_CELL_WIDTH + GRID_CELL_WIDTH // 2
    y = GRID_OFFSET_Y + row * GRID_CELL_HEIGHT + GRID_CELL_HEIGHT // 2
    return (x, y)


def get_plant_slot_position(slot_index: int) -> Tuple[int, int]:
    """
    获取植物卡槽的中心屏幕坐标
    
    Args:
        slot_index: 卡槽索引 (内部 0-based: 0 到 NUM_PLANT_SLOTS-1)
        
    Returns:
        (x, y) 卡槽中心的屏幕坐标
        
    注意：此函数使用 0-based 索引，用户输入的 1-based 索引已在调用前转换
        
    校准参考 (基于客户区坐标):
        Slot 0 (用户 Slot 1) 中心: (121, 42)
        Slot 1 (用户 Slot 2) 中心: (180, 43)  
        Slot 2 (用户 Slot 3) 中心: (238, 44)
    """
    # 使用直接测量的公式: slot 0 中心x = 121, 每个slot宽58
    x = 121 + slot_index * PLANT_SLOT_WIDTH
    y = SLOT_CENTER_Y  # 直接使用校准的卡槽中心Y
    return (x, y)


# ============================================================
# 验证函数
# ============================================================

def is_valid_grid_position(row: int, col: int) -> bool:
    """检查格子坐标是否有效"""
    return 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS


def is_valid_slot_index(slot: int) -> bool:
    """检查卡槽索引是否有效"""
    return 0 <= slot < NUM_PLANT_SLOTS
