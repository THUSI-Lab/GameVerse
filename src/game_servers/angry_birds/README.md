# Angry Birds Integration for GeneralGameBench

本模块实现了 Angry Birds 游戏与 GeneralGameBench 框架的交互。

## 功能特点

- **截图观察**: 通过 `GUIManager` 截取游戏窗口作为 LLM 的唯一观察输入
- **极简设计**: 参考 PVZ 实现,只提供基本游戏说明和截图,无辅助信息
- **双模式支持**: 
  - **Semantic 模式**: LLM 输出 `shoot(angle=X, power=Y)` 等语义动作,框架转换为 GUI 操作
  - **GUI 模式**: LLM 直接输出 JSON 格式的鼠标键盘操作
- **红鸟专属**: 只使用标准红色小鸟,简化游戏逻辑
- **自动检测**: 使用 OpenCV 模板匹配自动识别弹弓位置,适配不同分辨率和窗口大小

## 设计理念

**纯视觉观察**:
- LLM 只能看到游戏截图,没有任何辅助信息
- 不提供小鸟数量、猪的位置等结构化信息
- 完全模拟人类玩家的视角

**基本游戏说明**:
- 游戏目标: 消灭所有绿色的猪
- 游戏玩法: 拉动弹弓发射小鸟,撞击建筑和猪
- 界面信息: 小鸟在左边,猪在右边(绿色)

## 动作格式

### 模式 1: 语义动作模式 (Semantic Mode)

LLM 输出高层语义动作,框架自动转换为 GUI 操作。

**输出格式:**
```
### Reasoning
<分析猪的位置、结构弱点、选择的弹道>

### Actions
[shoot(angle=45, power=0.8)]
```

**可用动作:**
- `shoot(angle=X, power=Y)`: 发射小鸟
  - `angle`: 0-90度 (0=水平, 90=垂直)
  - `power`: 0.0-1.0 (力度)
- `wait()`: 等待并观察物理模拟

**转换机制:**
框架会将 `shoot(angle=45, power=0.8)` 自动转换为:
1. 鼠标按下弹弓位置
2. 向后拖拽(根据angle和power计算方向和距离)
3. 释放鼠标

### 模式 2: GUI 动作模式 (GUI Mode)

LLM 直接输出 JSON 格式的鼠标键盘操作。

**输出格式:**
```
### Reasoning
<your analysis>

### Actions
```json
[
  {"action_type": "MOUSE_DOWN", "parameters": {"x": 0.15, "y": 0.65}},
  {"action_type": "DRAG_TO", "parameters": {"x": 0.10, "y": 0.68}},
  {"action_type": "MOUSE_UP", "parameters": {}}
]
```
```

**可用 GUI 动作:**
- `CLICK`: 点击
- `MOUSE_DOWN`: 鼠标按下
- `DRAG_TO`: 拖拽到目标位置
- `MOUSE_UP`: 释放鼠标
- `WAIT`: 等待

**坐标系统:**
使用相对坐标 (0.0-1.0),其中 (0,0) 是左上角, (1,1) 是右下角

## 运行方式

### 1. 准备工作

1. 启动 Angry Birds 游戏
2. 确保游戏窗口可见且标题包含 "Angry Birds"
3. 进入要测试的关卡

### 2. 运行测试

```bash
# 测试环境基本功能
python scripts/test_angry_birds.py --test env

# 测试射击动作（需要游戏运行）
python scripts/test_angry_birds.py --test shoot
```

### 3. 完整运行

```bash
python scripts/play_game.py --config configs/angry_birds/config.yaml
```

## 配置说明

### 游戏服务器配置 (`src/game_servers/angry_birds/config.yaml`)

```yaml
env:
  window_title: "Angry Birds"    # 游戏窗口标题
  slingshot_pos_x: 0.15          # 弹弓 X 坐标（相对窗口）
  slingshot_pos_y: 0.65          # 弹弓 Y 坐标（相对窗口）
  max_pull_distance: 0.15        # 最大拉弓距离
  wait_after_shot: 5.0           # 射击后等待时间
```

### 关卡配置 (`src/game_servers/angry_birds/game/level_config.json`)

包含每关的小鸟类型、数量和弹弓位置信息。

## 小鸟类型

本实现只使用 **红色小鸟 (Red Bird)**:
- 标准小鸟,无特殊技能
- 适用于直接撞击和推倒结构
- LLM 需要通过精确的角度和力度控制来完成关卡

## 文件结构

```
src/
├── game_servers/
│   └── angry_birds/
│       ├── config.yaml           # 游戏服务器配置
│       ├── __init__.py
│       └── game/
│           ├── __init__.py
│           ├── angry_birds_env.py      # 主环境实现
│           ├── slingshot_detector.py   # 弹弓自动检测器
│           ├── level_config.json       # 关卡配置
│           └── images/
│               └── slingshot.png       # 弹弓模板图片
│
├── agent_servers/
│   └── angry_birds/
│       ├── config.yaml           # Agent 配置
│       ├── __init__.py
│       └── prompts/
│           ├── image/            # 图像输入模式 prompts
│           │   └── zeroshot_agent/
│           │       ├── action_inference_system.py
│           │       └── action_inference_user.py
│           └── semantic/         # 语义模式 prompts
│               └── zeroshot_agent/
│                   ├── action_inference_system.py
│                   └── action_inference_user.py
│
configs/
└── angry_birds/
    └── config.yaml               # 运行配置

scripts/
└── test_angry_birds.py           # 测试脚本
```

## 自动检测机制

### 弹弓位置检测

系统使用 OpenCV 模板匹配自动识别弹弓位置,适配不同分辨率:

1. **模板准备**: 提取弹弓区域保存为 `images/slingshot.png`
2. **自动检测**: 每场游戏开始时自动运行多尺度模板匹配
3. **位置更新**: 检测成功后更新弹弓坐标(相对坐标 0.0-1.0)
4. **可视化调试**: 保存检测结果到 `log_path/slingshot_detection.png`

**检测参数:**
- 匹配阈值: 0.6 (可在代码中调整)
- 缩放范围: 0.5x - 1.5x (20步)
- 输出格式: 相对坐标 (x, y)

**Fallback 机制:**
- 检测失败时使用配置文件中的默认值
- 日志会记录检测状态和位置对比

### 窗口识别

- 支持正则表达式匹配窗口标题 (如 `Angry Birds.*` 匹配 "Angry Birds(800x600)")
- 自动获取窗口大小和位置
- 截图时自动适配窗口尺寸

## 注意事项

1. **窗口检测**: 确保游戏窗口标题包含 "Angry Birds"
2. **模板准备**: 首次使用需准备清晰的弹弓模板图片
3. **等待时间**: 复杂关卡可能需要更长的物理模拟等待时间
4. **检测调试**: 检查 `slingshot_detection.png` 验证检测精度

## 参考

- DeepPHY 项目的 Angry Birds 实现
- GeneralGameBench 2048 游戏的 GUI 交互模式
