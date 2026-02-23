"""
Maze Game - 可配置大小的黑白迷宫游戏逻辑
实现迷宫生成、路径查找和游戏状态管理
"""
import random
import collections
from typing import Tuple, List, Optional
from copy import deepcopy


class MazeGenerator:
    """生成可配置大小的迷宫，保证起点到终点有解，黑色墙壁超过50%"""
    
    def __init__(self, size: int = 4):
        self.size = size
    
    def generate(self) -> List[List[int]]:
        """
        使用DFS算法生成迷宫，然后添加墙壁确保黑色超过50%
        返回: size×size矩阵，0表示墙（黑色），1表示路径（白色）
        """
        # 初始化：全部是墙
        maze = [[0 for _ in range(self.size)] for _ in range(self.size)]
        
        # 使用DFS生成迷宫
        stack = [(0, 0)]  # 从起点开始
        maze[0][0] = 1  # 起点是路径
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # 右、下、左、上
        
        while stack:
            current = stack[-1]
            row, col = current
            
            # 获取未访问的邻居（距离为2的格子，因为要打通墙）
            neighbors = []
            for dr, dc in directions:
                nr, nc = row + 2 * dr, col + 2 * dc
                if 0 <= nr < self.size and 0 <= nc < self.size and maze[nr][nc] == 0:
                    neighbors.append((nr, nc, dr, dc))
            
            if neighbors:
                # 随机选择一个邻居
                next_row, next_col, dr, dc = random.choice(neighbors)
                
                # 打通路径（包括中间的墙）
                maze[row + dr][col + dc] = 1  # 中间的墙变成路径
                maze[next_row][next_col] = 1  # 目标格子变成路径
                
                stack.append((next_row, next_col))
            else:
                # 回溯
                stack.pop()
        
        # 确保终点是路径
        maze[self.size - 1][self.size - 1] = 1
        
        # 验证起点到终点是否连通
        if not self._is_connected(maze, (0, 0), (self.size - 1, self.size - 1)):
            # 如果不连通，强制打通一条路径
            self._force_path(maze, (0, 0), (self.size - 1, self.size - 1))
        
        # 确保黑色墙壁超过50%
        self._ensure_black_over_50_percent(maze)
        
        # 再次验证起点到终点是否连通（因为_ensure_black_over_50_percent可能破坏了连通性）
        # 确保 (0,0) 和 (size-1, size-1) 是路径
        maze[0][0] = 1
        maze[self.size - 1][self.size - 1] = 1
        if not self._is_connected(maze, (0, 0), (self.size - 1, self.size - 1)):
            # 如果不连通，强制打通一条路径
            self._force_path(maze, (0, 0), (self.size - 1, self.size - 1))
        
        return maze
    
    def _ensure_black_over_50_percent(self, maze: List[List[int]]):
        """
        确保黑色墙壁超过50%
        通过随机将一些路径格子改为墙壁，但保持连通性
        """
        total_cells = self.size * self.size
        target_black = total_cells // 2 + 1  # 超过50%
        
        # 统计当前黑色数量
        current_black = sum(sum(1 for cell in row if cell == 0) for row in maze)
        
        if current_black >= target_black:
            return  # 已经满足要求
        
        # 收集所有路径位置（除了起点和终点，它们会在后面确定）
        # 保护默认起点(0,0)和终点(size-1, size-1)，避免被改为墙
        protected_positions = {(0, 0), (self.size - 1, self.size - 1)}
        path_positions = []
        for row in range(self.size):
            for col in range(self.size):
                if maze[row][col] == 1 and (row, col) not in protected_positions:
                    path_positions.append((row, col))
        
        # 随机打乱路径位置
        random.shuffle(path_positions)
        
        # 尝试将一些路径改为墙壁，但保持连通性
        needed_black = target_black - current_black
        changed = 0
        
        for row, col in path_positions:
            if changed >= needed_black:
                break
            
            # 临时将路径改为墙壁
            maze[row][col] = 0
            
            # 检查是否仍然连通
            # 1. 检查所有路径是否仍然连通
            # 2. 特别检查默认起点(0,0)和终点(size-1, size-1)是否连通
            default_start = (0, 0)
            default_end = (self.size - 1, self.size - 1)
            if (self._all_paths_connected(maze) and 
                self._is_connected(maze, default_start, default_end)):
                changed += 1
            else:
                # 如果不连通，恢复为路径
                maze[row][col] = 1
    
    def _all_paths_connected(self, maze: List[List[int]]) -> bool:
        """检查所有路径格子是否连通"""
        # 收集所有路径位置
        path_positions = []
        for row in range(self.size):
            for col in range(self.size):
                if maze[row][col] == 1:
                    path_positions.append((row, col))
        
        if len(path_positions) == 0:
            return False
        
        # 从第一个路径位置开始BFS
        start = path_positions[0]
        visited = set()
        queue = collections.deque([start])
        visited.add(start)
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        
        while queue:
            row, col = queue.popleft()
            
            for dr, dc in directions:
                nr, nc = row + dr, col + dc
                if (0 <= nr < self.size and 0 <= nc < self.size and 
                    maze[nr][nc] == 1 and (nr, nc) not in visited):
                    visited.add((nr, nc))
                    queue.append((nr, nc))
        
        # 如果访问的路径数量等于总路径数量，说明所有路径连通
        return len(visited) == len(path_positions)
    
    def _is_connected(self, maze: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """使用BFS检查两点是否连通"""
        if maze[start[0]][start[1]] == 0 or maze[end[0]][end[1]] == 0:
            return False
        
        visited = set()
        queue = collections.deque([start])
        visited.add(start)
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        
        while queue:
            row, col = queue.popleft()
            if (row, col) == end:
                return True
            
            for dr, dc in directions:
                nr, nc = row + dr, col + dc
                if (0 <= nr < self.size and 0 <= nc < self.size and 
                    maze[nr][nc] == 1 and (nr, nc) not in visited):
                    visited.add((nr, nc))
                    queue.append((nr, nc))
        
        return False
    
    def _force_path(self, maze: List[List[int]], start: Tuple[int, int], end: Tuple[int, int]):
        """强制打通从起点到终点的路径"""
        row, col = start
        end_row, end_col = end
        
        # 先向右移动，再向下移动
        while col < end_col:
            maze[row][col] = 1
            col += 1
        while row < end_row:
            maze[row][col] = 1
            row += 1
        maze[end_row][end_col] = 1


class PathFinder:
    """计算从起点到终点的最佳步数（单格移动）"""
    
    def __init__(self, maze: List[List[int]], size: int = 4):
        self.maze = maze
        self.size = size
    
    def find_best_steps(self, start: Tuple[int, int], end: Tuple[int, int]) -> int:
        """
        使用BFS计算最佳步数（单格移动）
        """
        if self.maze[start[0]][start[1]] == 0 or self.maze[end[0]][end[1]] == 0:
            return -1  # 起点或终点是墙，无解
        
        # BFS - 单格移动
        queue = collections.deque([(start[0], start[1], 0)])  # (row, col, steps)
        visited = set([start])
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # 右、下、左、上
        
        while queue:
            row, col, steps = queue.popleft()
            
            if (row, col) == end:
                return steps
            
            # 尝试四个方向（单格移动）
            for dr, dc in directions:
                next_row, next_col = row + dr, col + dc
                
                # 检查是否出界或撞墙
                if (0 <= next_row < self.size and 0 <= next_col < self.size and 
                    self.maze[next_row][next_col] == 1 and 
                    (next_row, next_col) not in visited):
                    visited.add((next_row, next_col))
                    queue.append((next_row, next_col, steps + 1))
        
        return -1  # 无解


class MazeGame:
    """迷宫游戏逻辑类，管理游戏状态和移动"""
    
    def __init__(self, size: int = 4):
        self.size = size
        self.maze = None
        self.ball_pos = None  # 小球起始位置（随机生成）
        self.target_pos = None  # 目标位置（随机生成）
        self.won = False
        self.step_count = 0
        self.best_steps = -1
        
        # 生成迷宫
        generator = MazeGenerator(size)
        self.maze = generator.generate()
        
        # 随机选择起点和终点（确保都是路径且有解）
        self._generate_start_and_target()
        
        # 计算最佳步数
        path_finder = PathFinder(self.maze, size)
        self.best_steps = path_finder.find_best_steps(self.ball_pos, self.target_pos)
    
    def _generate_start_and_target(self):
        """随机生成起点和终点，确保都是路径、有解，且最优步数至少大于size+2"""
        # 收集所有路径位置
        path_positions = []
        for row in range(self.size):
            for col in range(self.size):
                if self.maze[row][col] == 1:  # 路径
                    path_positions.append((row, col))
        
        if len(path_positions) < 2:
            # 如果路径太少，使用默认位置，但需要确保这些位置是路径
            default_start = (0, 0)
            default_end = (self.size - 1, self.size - 1)
            # 确保默认位置是路径（如果不是，强制设置为路径）
            if self.maze[default_start[0]][default_start[1]] == 0:
                self.maze[default_start[0]][default_start[1]] = 1
            if self.maze[default_end[0]][default_end[1]] == 0:
                self.maze[default_end[0]][default_end[1]] = 1
            self.ball_pos = default_start
            self.target_pos = default_end
            return
        
        # 随机选择起点和终点，确保有解且最优步数>size+2
        max_attempts = 500  # 增加尝试次数，因为需要满足步数要求
        path_finder = PathFinder(self.maze, self.size)
        min_steps = self.size + 2  # 最优步数至少为 size+3
        
        for attempt in range(max_attempts):
            # 随机选择两个不同的路径位置
            start, target = random.sample(path_positions, 2)
            
            # 检查是否有解且最优步数>size+2
            best_steps = path_finder.find_best_steps(start, target)
            if best_steps > min_steps:  # 有解且最优步数至少为 size+3
                self.ball_pos = start
                self.target_pos = target
                return
        
        # 如果多次尝试都失败，尝试使用距离较远的位置
        # 计算所有路径位置之间的距离，选择距离最远的
        best_pair = None
        max_steps = 0
        
        for i, start in enumerate(path_positions):
            for target in path_positions[i+1:]:
                steps = path_finder.find_best_steps(start, target)
                if steps > max_steps:
                    max_steps = steps
                    best_pair = (start, target)
        
        if best_pair and max_steps > min_steps:
            self.ball_pos, self.target_pos = best_pair
        else:
            # 如果还是找不到，使用默认位置（但可能不满足步数要求）
            # 确保默认位置是路径（如果不是，强制设置为路径）
            default_start = (0, 0)
            default_end = (self.size - 1, self.size - 1)
            if self.maze[default_start[0]][default_start[1]] == 0:
                self.maze[default_start[0]][default_start[1]] = 1
            if self.maze[default_end[0]][default_end[1]] == 0:
                self.maze[default_end[0]][default_end[1]] = 1
            self.ball_pos = default_start
            self.target_pos = default_end
    
    def move(self, direction: str) -> bool:
        """
        执行单格移动
        direction: "up", "down", "left", "right"
        返回: 是否成功移动
        """
        if self.won:
            return False
        
        direction_map = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1)
        }
        
        if direction not in direction_map:
            return False
        
        dr, dc = direction_map[direction]
        new_row = self.ball_pos[0] + dr
        new_col = self.ball_pos[1] + dc
        
        # 检查是否出界或撞墙
        if (new_row < 0 or new_row >= self.size or 
            new_col < 0 or new_col >= self.size or 
            self.maze[new_row][new_col] == 0):
            return False  # 无法移动
        
        # 执行移动
        self.ball_pos = (new_row, new_col)
        self.step_count += 1
        
        # 检查是否获胜
        if self.ball_pos == self.target_pos:
            self.won = True
        
        return True
    
    def get_state(self) -> dict:
        """获取游戏状态"""
        return {
            "maze": deepcopy(self.maze),
            "ball_pos": self.ball_pos,
            "target_pos": self.target_pos,
            "won": self.won,
            "step_count": self.step_count,
            "best_steps": self.best_steps,
            "terminated": self.won
        }
    
    def reset(self):
        """重置游戏"""
        self.won = False
        self.step_count = 0
        
        # 重新生成迷宫
        generator = MazeGenerator(self.size)
        self.maze = generator.generate()
        
        # 重新随机选择起点和终点
        self._generate_start_and_target()
        
        # 重新计算最佳步数
        path_finder = PathFinder(self.maze, self.size)
        self.best_steps = path_finder.find_best_steps(self.ball_pos, self.target_pos)

