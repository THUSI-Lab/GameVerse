"""
Action Space 声明式定义

基于 UI-Tars 的设计，定义统一的动作空间
"""
from game_servers.utils.types.game_io import Action
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from.action_space import ActionType

@dataclass
class GUI_action(Action):
    """
    统一的动作定义
    
    Attributes:
        action_type: 动作类型
        parameters: 动作参数字典
    
    Examples:
        # 移动鼠标
        Action(ActionType.MOVE_TO, {"x": 100, "y": 200})
    """
    action_type: Union[ActionType, str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # 自动转换字符串为枚举类型
        if isinstance(self.action_type, str):
            self.action_type = ActionType(self.action_type.upper())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GUI_action':
        """从字典创建Action"""
        """可以用字典模式统一prompt输出"""
        action_type = data.get('action_type', "")
        parameters = data.get('parameters', {})
        
        return cls(action_type=action_type, parameters=parameters)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'action_type': self.action_type.value if isinstance(self.action_type, ActionType) else self.action_type,
            'parameters': self.parameters
        }
    
    # 便捷的参数访问
    @property
    def x(self) -> Optional[int]:
        return self.parameters.get('x')
    
    @property
    def y(self) -> Optional[int]:
        return self.parameters.get('y')
    
    @property
    def button(self) -> str:
        return self.parameters.get('button', 'left')
    
    @property
    def key(self) -> Optional[str]:
        return self.parameters.get('key')
    
    @property
    def keys(self) -> List[str]:
        return self.parameters.get('keys', [])
    
    @property
    def text(self) -> Optional[str]:
        return self.parameters.get('text')
    
    @property
    def duration(self) -> Optional[float]:
        return self.parameters.get('duration')
    
    @property
    def interval(self) -> float:
        return self.parameters.get('interval', 0.05)
    
    @property
    def num_clicks(self) -> int:
        return self.parameters.get('num_clicks', 1)
    
    @property
    def dx(self) -> int:
        return self.parameters.get('dx', 0)
    
    @property
    def dy(self) -> int:
        return self.parameters.get('dy', 0)