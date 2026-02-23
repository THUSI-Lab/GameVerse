"""
井字棋游戏逻辑实现
适配GeneralGameBench框架
"""
from typing import Optional, Tuple, List
import random


class TicTacToeGame:
    """井字棋游戏逻辑类"""
    
    def __init__(self, first_player: str = 'X'):
        """
        初始化游戏
        
        Args:
            first_player: 先手玩家标记 ('X' 或 'O')，默认为 'X'
        """
        # 使用一维数组，初始值为1-9表示空位
        self.board = [i + 1 for i in range(9)]
        self.first_player = first_player  # 保存初始玩家设置
        self.current_player = first_player
        self.winner = None
        self.is_finished = False
        self.moves_history = []
    
    def reset(self):
        """重置游戏"""
        self.board = [i + 1 for i in range(9)]
        self.current_player = self.first_player  # 使用保存的初始玩家设置
        self.winner = None
        self.is_finished = False
        self.moves_history = []
    
    def make_move(self, index: int, player: str) -> bool:
        """
        执行一步移动（使用索引0-8）
        
        Args:
            index: 位置索引 (0-8)
            player: 玩家标记 ('X' 或 'O')
        
        Returns:
            bool: 移动是否成功
        """
        if self.board[index] not in ['X', 'O'] and not self.is_finished:
            self.board[index] = player
            self.moves_history.append((index, player))
            # 切换当前玩家
            self.current_player = 'O' if player == 'X' else 'X'
            self._check_winner()
            return True
        return False
    
    def make_move_2d(self, row: int, col: int, player: str) -> bool:
        """
        执行一步移动（使用2D坐标）
        
        Args:
            row: 行索引 (0-2)
            col: 列索引 (0-2)
            player: 玩家标记 ('X' 或 'O')
        
        Returns:
            bool: 移动是否成功
        """
        index = row * 3 + col
        return self.make_move(index, player)
    
    def _check_winner(self):
        """检查是否有玩家获胜"""
        # 定义所有可能的获胜位置
        win_positions = [
            (0, 1, 2),  # 第一行
            (3, 4, 5),  # 第二行
            (6, 7, 8),  # 第三行
            (0, 3, 6),  # 第一列
            (1, 4, 7),  # 第二列
            (2, 5, 8),  # 第三列
            (0, 4, 8),  # 主对角线
            (2, 4, 6)   # 副对角线
        ]
        
        # 检查是否有获胜者
        for pos in win_positions:
            if self.board[pos[0]] == self.board[pos[1]] == self.board[pos[2]]:
                self.winner = self.board[pos[0]]
                self.is_finished = True
                return
        
        # 检查是否平局（所有格子都被填满且没有获胜者）
        if all(cell in ['X', 'O'] for cell in self.board) and not self.winner:
            self.is_finished = True
            self.winner = None
    
    def get_board_2d(self) -> List[List[str]]:
        """获取2D格式的棋盘状态"""
        result = []
        for i in range(0, 9, 3):
            row = []
            for j in range(3):
                cell = self.board[i + j]
                if cell in ['X', 'O']:
                    row.append(cell)
                else:
                    row.append(' ')
            result.append(row)
        return result
    
    def get_valid_moves(self) -> List[int]:
        """获取所有有效移动（返回索引列表）"""
        moves = []
        for i in range(9):
            if self.board[i] not in ['X', 'O']:
                moves.append(i)
        return moves
    
    def get_valid_moves_2d(self) -> List[Tuple[int, int]]:
        """获取所有有效移动（返回2D坐标列表）"""
        moves = []
        for i in range(9):
            if self.board[i] not in ['X', 'O']:
                row = i // 3
                col = i % 3
                moves.append((row, col))
        return moves
    
    def is_valid_move(self, row: int, col: int) -> bool:
        """检查移动是否有效"""
        index = row * 3 + col
        return 0 <= index < 9 and self.board[index] not in ['X', 'O']
    
    def get_board_string(self) -> str:
        """获取棋盘的字符串表示"""
        board_2d = self.get_board_2d()
        lines = []
        lines.append("  1   2   3")
        for i, row in enumerate(board_2d):
            row_str = chr(65 + i) + " "  # A, B, C
            for j, cell in enumerate(row):
                if j > 0:
                    row_str += " | "
                row_str += cell if cell != ' ' else ' '
            lines.append(row_str)
            if i < 2:
                lines.append("  ---------")
        return "\n".join(lines)


class MinimaxAI:
    """使用Minimax算法的AI对手"""
    
    def __init__(self, bot: str = 'O', opponent: str = 'X'):
        """
        初始化AI
        
        Args:
            bot: AI的标记 ('O')
            opponent: 玩家的标记 ('X')
        """
        self.bot = bot
        self.opponent = opponent
    
    @staticmethod
    def generate_plugin(lst, cols):
        """将列表分割成指定列数的2D列表"""
        return [lst[i:i + cols] for i in range(0, len(lst), cols)]
    
    @staticmethod
    def generate_1d(row, col):
        """将2D坐标转换为1D索引"""
        return row * 3 + col
    
    def generate_2d(self, board):
        """将1D棋盘转换为2D格式（用于minimax算法）"""
        return self.generate_plugin([
            '_' if cell not in [self.bot, self.opponent] else cell
            for cell in board
        ], 3)
    
    @staticmethod
    def is_moves_left(board):
        """检查是否还有可移动的位置"""
        return any(cell == '_' for row in board for cell in row)
    
    def evaluate(self, board):
        """评估棋盘状态"""
        # 检查行
        for row in board:
            if row[0] == row[1] == row[2]:
                if row[0] == self.bot:
                    return 10
                elif row[0] == self.opponent:
                    return -10
        
        # 检查列
        for col in range(3):
            if board[0][col] == board[1][col] == board[2][col]:
                if board[0][col] == self.bot:
                    return 10
                elif board[0][col] == self.opponent:
                    return -10
        
        # 检查主对角线
        if board[0][0] == board[1][1] == board[2][2]:
            if board[0][0] == self.bot:
                return 10
            elif board[0][0] == self.opponent:
                return -10
        
        # 检查副对角线
        if board[0][2] == board[1][1] == board[2][0]:
            if board[0][2] == self.bot:
                return 10
            elif board[0][2] == self.opponent:
                return -10
        
        return 0
    
    def minimax(self, board, depth, is_max):
        """Minimax算法递归函数"""
        score = self.evaluate(board)
        
        if score == 10 or score == -10:
            return score
        
        if not self.is_moves_left(board):
            return 0
        
        if is_max:
            best = -1000
            for i in range(3):
                for j in range(3):
                    if board[i][j] == '_':
                        board[i][j] = self.bot
                        best = max(best, self.minimax(board, depth + 1, not is_max))
                        board[i][j] = '_'
            return best
        else:
            best = 1000
            for i in range(3):
                for j in range(3):
                    if board[i][j] == '_':
                        board[i][j] = self.opponent
                        best = min(best, self.minimax(board, depth + 1, not is_max))
                        board[i][j] = '_'
            return best
    
    def find_best_move(self, game: TicTacToeGame) -> Optional[int]:
        """
        找到最佳移动（返回1D索引）
        
        Args:
            game: 游戏实例
        
        Returns:
            最佳移动的索引，如果没有有效移动则返回None
        """
        # 将1D棋盘转换为2D格式
        game_match = self.generate_2d(game.board)
        
        best_val = -1000
        best_move = (-1, -1)
        
        for i in range(3):
            for j in range(3):
                if game_match[i][j] == '_':
                    game_match[i][j] = self.bot
                    move_val = self.minimax(game_match, 1, False)
                    game_match[i][j] = '_'
                    if move_val > best_val:
                        best_move = (i, j)
                        best_val = move_val
        
        if best_move == (-1, -1):
            return None
        
        return self.generate_1d(best_move[0], best_move[1])
    
    def find_best_move_2d(self, game: TicTacToeGame) -> Optional[Tuple[int, int]]:
        """
        找到最佳移动（返回2D坐标）
        
        Args:
            game: 游戏实例
        
        Returns:
            最佳移动的(row, col)坐标，如果没有有效移动则返回None
        """
        index = self.find_best_move(game)
        if index is None:
            return None
        row = index // 3
        col = index % 3
        return (row, col)


class RandomAI:
    """随机AI对手"""
    
    def __init__(self, bot: str = 'O', opponent: str = 'X'):
        """
        初始化随机AI
        
        Args:
            bot: AI的标记 ('O')
            opponent: 玩家的标记 ('X')
        """
        self.bot = bot
        self.opponent = opponent
    
    def find_best_move(self, game: TicTacToeGame) -> Optional[int]:
        """
        随机选择一个有效移动
        
        Args:
            game: 游戏实例
        
        Returns:
            随机选择的移动索引，如果没有有效移动则返回None
        """
        valid_moves = game.get_valid_moves()
        if not valid_moves:
            return None
        return random.choice(valid_moves)
    
    def find_best_move_2d(self, game: TicTacToeGame) -> Optional[Tuple[int, int]]:
        """
        随机选择一个有效移动（返回2D坐标）
        
        Args:
            game: 游戏实例
        
        Returns:
            随机选择的移动(row, col)坐标，如果没有有效移动则返回None
        """
        index = self.find_best_move(game)
        if index is None:
            return None
        row = index // 3
        col = index % 3
        return (row, col)
