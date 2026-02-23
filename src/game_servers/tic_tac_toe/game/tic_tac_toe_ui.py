"""
井字棋图形界面实现 - 适配GeneralGameBench
使用tkinter创建轻量级界面
"""
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont
import os
import threading
import time
import multiprocessing
import queue
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class TicTacToeUI:
    """井字棋图形界面类 - 适配GeneralGameBench"""
    
    def __init__(self, game, player_mark: str = 'X', title: str = "Tic Tac Toe - GeneralGameBench"):
        """
        初始化界面
        
        Args:
            game: TicTacToeGame实例
            player_mark: 玩家标记 ('X' 或 'O')
            title: 窗口标题
        """
        self.game = game
        self.player_mark = player_mark
        self.ai_mark = 'O' if player_mark == 'X' else 'X'
        self.title = title
        
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("500x650")
        self.root.resizable(False, False)
        
        # 设置窗口在屏幕右侧
        self.root.geometry("+800+100")
        
        # 创建信息标签
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=10)
        
        self.info_label = tk.Label(
            info_frame,
            text=f"GeneralGameBench - Tic Tac Toe\nPlayer: {self.player_mark} | AI: {self.ai_mark}",
            font=('Arial', 12),
            justify=tk.CENTER
        )
        self.info_label.pack()
        
        # 创建画布
        self.canvas = tk.Canvas(self.root, width=500, height=500, bg='white')
        self.canvas.pack(pady=10)
        
        # 绑定点击事件
        self.canvas.bind("<Button-1>", self._on_cell_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        
        # 创建状态标签
        player_text = f"Current Player: {self.game.current_player}"
        self.status_label = tk.Label(
            self.root, 
            text=player_text, 
            font=('Arial', 14, 'bold')
        )
        self.status_label.pack(pady=5)
        
        # 创建步数标签
        self.step_label = tk.Label(
            self.root,
            text="Step: 0",
            font=('Arial', 10)
        )
        self.step_label.pack()
        
        # 点击回调函数（由环境设置）
        self.click_callback = None
        
        # 绘制初始棋盘
        self._draw_board()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 控制变量
        self.is_running = True
        self.step_count = 0
        self.cell_size = 150
        self.margin = 50
    
    def _on_cell_click(self, event):
        """处理单元格点击事件"""
        if not self.is_running or self.game.is_finished:
            return
        
        # 计算点击位置对应的行列
        col = (event.x - self.margin) // self.cell_size
        row = (event.y - self.margin) // self.cell_size
        
        # 验证坐标是否在有效范围内
        if 0 <= row < 3 and 0 <= col < 3:
            # 检查位置是否为空
            board_2d = self.game.get_board_2d()
            if board_2d[row][col] == ' ':
                # 如果有回调函数，调用它
                if self.click_callback:
                    self.click_callback(row, col, event.x, event.y)
            else:
                logger.info(f"Cell ({row}, {col}) is already occupied!")
        else:
            logger.info(f"Click outside board area: ({event.x}, {event.y})")
    
    def _on_mouse_move(self, event):
        """处理鼠标移动事件（用于显示悬停效果）"""
        # 可以在这里添加悬停高亮效果
        pass
    
    def set_click_callback(self, callback):
        """设置点击回调函数"""
        self.click_callback = callback
    
    def _draw_board(self):
        """绘制棋盘"""
        self.canvas.delete("all")
        
        # 绘制网格线
        cell_size = self.cell_size
        margin = self.margin
        
        # 垂直线
        for i in range(1, 3):
            x = margin + i * cell_size
            self.canvas.create_line(x, margin, x, margin + 3 * cell_size, width=3)
        
        # 水平线
        for i in range(1, 3):
            y = margin + i * cell_size
            self.canvas.create_line(margin, y, margin + 3 * cell_size, y, width=3)
        
        # 绘制坐标标签（放大字号，方便视觉模型读取）
        font_size = 20
        for i in range(3):
            # 行标签 (A, B, C)
            self.canvas.create_text(
                25, margin + i * cell_size + cell_size // 2,
                text=chr(65 + i), font=('Arial', font_size, 'bold')
            )
            # 列标签 (1, 2, 3)
            self.canvas.create_text(
                margin + i * cell_size + cell_size // 2, 25,
                text=str(i + 1), font=('Arial', font_size, 'bold')
            )
        
        # 绘制棋子 - 使用2D格式获取棋盘状态
        board_2d = self.game.get_board_2d()
        for i in range(3):
            for j in range(3):
                cell_value = board_2d[i][j]
                if cell_value != ' ':
                    x = margin + j * cell_size + cell_size // 2
                    y = margin + i * cell_size + cell_size // 2
                    
                    if cell_value == 'X':
                        # 绘制X (红色)
                        self.canvas.create_text(
                            x, y, text='X',
                            font=('Arial', 60, 'bold'),
                            fill='red'
                        )
                    elif cell_value == 'O':
                        # 绘制O (蓝色)
                        self.canvas.create_text(
                            x, y, text='O',
                            font=('Arial', 60, 'bold'),
                            fill='blue'
                        )
    
    def update_display(self, step_count: Optional[int] = None):
        """更新显示"""
        if not self.is_running:
            return
            
        try:
            self._draw_board()
            
            if step_count is not None:
                self.step_count = step_count
                self.step_label.config(text=f"Step: {self.step_count}")
            
            if self.game.is_finished:
                if self.game.winner == self.player_mark:
                    self.status_label.config(text="Player Wins!", fg='green')
                elif self.game.winner == self.ai_mark:
                    self.status_label.config(text="AI Wins!", fg='red')
                else:
                    self.status_label.config(text="It's a Tie!", fg='orange')
            else:
                current_player = self.game.current_player
                if current_player == self.player_mark:
                    self.status_label.config(text=f"Current Player: {current_player} (Human)", fg='black')
                else:
                    self.status_label.config(text=f"Current Player: {current_player} (AI)", fg='blue')
            
            # 强制更新UI
            self.root.update()
            
        except tk.TclError:
            # 窗口已被关闭
            self.is_running = False
    
    def show_move_info(self, move: str, player: str):
        """显示移动信息"""
        if not self.is_running:
            return
            
        try:
            move_text = f"Last Move: {player} -> {move}"
            if hasattr(self, 'move_label'):
                self.move_label.config(text=move_text)
            else:
                self.move_label = tk.Label(
                    self.root,
                    text=move_text,
                    font=('Arial', 10),
                    fg='gray'
                )
                self.move_label.pack()
            
            self.root.update()
        except tk.TclError:
            self.is_running = False
    
    def _on_closing(self):
        """窗口关闭事件"""
        self.is_running = False
        try:
            self.root.destroy()
        except:
            pass
    
    def is_window_open(self) -> bool:
        """检查窗口是否仍然打开"""
        return self.is_running
    
    def close(self):
        """关闭窗口"""
        self.is_running = False
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass


class TicTacToeUIManager:
    """简化的UI管理器 - 避免线程问题"""
    
    def __init__(self, game, player_mark: str = 'X'):
        self.game = game
        self.player_mark = player_mark
        self.is_running = False
        self.game_history = []  # 记录游戏历史
    
    def start_ui(self):
        """启动UI - 记录开始状态"""
        self.is_running = True
        self.game_history = []
        print(f"TicTacToe UI Manager started (Player: {self.player_mark})")
    
    def update_display(self, step_count: Optional[int] = None):
        """记录显示更新 - 避免实时UI操作"""
        if self.is_running and step_count is not None:
            board_state = self.game.get_board_2d()
            self.game_history.append({
                'step': step_count,
                'board': [row[:] for row in board_state],  # 深拷贝
                'current_player': self.game.current_player,
                'finished': self.game.is_finished,
                'winner': self.game.winner
            })
            
            # 打印当前状态到控制台
            print(f"\n=== Step {step_count} ===")
            print(self._format_board(board_state))
            if self.game.is_finished:
                if self.game.winner:
                    print(f"Game Over! Winner: {self.game.winner}")
                else:
                    print("Game Over! It's a tie!")
                # 游戏结束时显示最终UI
                self._show_final_ui()
    
    def show_move_info(self, move: str, player: str):
        """显示移动信息"""
        if self.is_running:
            if move.startswith("INVALID"):
                print(f"*** {move} by {player} ***")
            elif move == "NO ACTION":
                print(f"*** NO ACTION PROVIDED by {player} ***")
            else:
                print(f"Move: {player} -> {move}")
    
    def _format_board(self, board_2d):
        """格式化棋盘显示"""
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
    
    def _show_final_ui(self):
        """在游戏结束时显示最终UI"""
        try:
            # 直接在当前线程中显示最终结果UI
            self._create_final_ui()
        except Exception as e:
            print(f"Failed to show final UI: {e}")
    
    def _create_final_ui(self):
        """创建最终结果UI"""
        try:
            # 创建简单的结果窗口
            root = tk.Tk()
            root.title("Tic Tac Toe - Game Result")
            root.geometry("400x500")
            root.resizable(False, False)
            
            # 游戏结果
            if self.game.winner:
                result_text = f"Game Over!\nWinner: {self.game.winner}"
                color = 'green' if self.game.winner == self.player_mark else 'red'
            else:
                result_text = "Game Over!\nIt's a Tie!"
                color = 'orange'
            
            result_label = tk.Label(
                root,
                text=result_text,
                font=('Arial', 16, 'bold'),
                fg=color
            )
            result_label.pack(pady=20)
            
            # 最终棋盘
            canvas = tk.Canvas(root, width=300, height=300, bg='white')
            canvas.pack(pady=10)
            
            # 绘制最终棋盘
            self._draw_final_board(canvas)
            
            # 游戏统计
            stats_text = f"Total Steps: {len(self.game_history)}\nPlayer Mark: {self.player_mark}"
            stats_label = tk.Label(
                root,
                text=stats_text,
                font=('Arial', 10)
            )
            stats_label.pack(pady=10)
            
            # 关闭按钮
            close_button = tk.Button(
                root,
                text="Close",
                command=root.destroy,
                font=('Arial', 12)
            )
            close_button.pack(pady=10)
            
            # 10秒后自动关闭
            root.after(10000, root.destroy)
            
            # 运行UI
            root.mainloop()
            
        except Exception as e:
            print(f"Error creating final UI: {e}")
    
    def _draw_final_board(self, canvas):
        """绘制最终棋盘"""
        cell_size = 90
        margin = 30
        
        # 绘制网格线
        for i in range(1, 3):
            x = margin + i * cell_size
            canvas.create_line(x, margin, x, margin + 3 * cell_size, width=2)
        
        for i in range(1, 3):
            y = margin + i * cell_size
            canvas.create_line(margin, y, margin + 3 * cell_size, y, width=2)
        
        # 绘制棋子
        board_2d = self.game.get_board_2d()
        for i in range(3):
            for j in range(3):
                cell_value = board_2d[i][j]
                if cell_value != ' ':
                    x = margin + j * cell_size + cell_size // 2
                    y = margin + i * cell_size + cell_size // 2
                    
                    if cell_value == 'X':
                        canvas.create_text(
                            x, y, text='X',
                            font=('Arial', 36, 'bold'),
                            fill='red'
                        )
                    elif cell_value == 'O':
                        canvas.create_text(
                            x, y, text='O',
                            font=('Arial', 36, 'bold'),
                            fill='blue'
                        )
    
    def stop_ui(self):
        """停止UI"""
        self.is_running = False
        print("TicTacToe UI Manager stopped")
    
    def is_ui_running(self) -> bool:
        """检查UI是否正在运行"""
        return self.is_running
