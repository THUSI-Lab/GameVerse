from typing import List
from PIL import Image
import json
from dataclasses import field, dataclass

from game_servers.utils.types.game_io import Obs, Action
from game_servers.GUI.act.actions import GUI_action

@dataclass
class BaseObs(Obs):
    """Base observation class for GUI-based games
    
    All GUI game observations should inherit from this class.
    Contains common fields that all GUI games share.
    
    Attributes:
        image: Screenshot of the game window
        step_count: Current step number
    """
    image: Image.Image
    step_count: int = 0
    
    def to_text(self) -> str:
        """Convert observation to text description
        
        Default implementation returns basic step information.
        Subclasses can override to provide more detailed descriptions.
        """
        return f"Step: {self.step_count}"


@dataclass
class BaseAction(Action):
    """Base action class for GUI-based games
    
    All GUI game actions should inherit from this class.
    Contains GUI actions that can be executed through GUIManager.
    
    Attributes:
        gui_actions: List of GUI actions to execute
    """
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    def get_gui_actions(self) -> List[GUI_action]:
        """Get list of GUI actions to execute"""
        return self.gui_actions
    
    def to_json(self) -> str:
        """Convert action to JSON string"""
        return json.dumps([action.to_dict() for action in self.gui_actions], indent=2)

