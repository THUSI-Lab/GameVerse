"""
Tic Tac Toe game module
"""
from .tic_tac_toe_game import TicTacToeGame, MinimaxAI, RandomAI
from .tic_tac_toe_ui import TicTacToeUI, TicTacToeUIManager

# Import environment classes - they should be available when gymnasium is installed
try:
    from .tic_tac_toe_env import TicTacToeEnv, TicTacToeObs, TicTacToeAction
    __all__ = ['TicTacToeGame', 'MinimaxAI', 'RandomAI', 'TicTacToeUI', 'TicTacToeUIManager', 'TicTacToeEnv', 'TicTacToeObs', 'TicTacToeAction']
except ImportError:
    # If gymnasium is not available, only export game classes
    __all__ = ['TicTacToeGame', 'MinimaxAI', 'RandomAI', 'TicTacToeUI', 'TicTacToeUIManager']
