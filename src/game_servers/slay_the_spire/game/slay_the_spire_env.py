import os
import re
import ast
import glob
import json
import time
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, List, Optional
from PIL import Image

from dacite import from_dict

from game_servers.base_env import BaseEnv
from game_servers.utils.types.game_io import Action, Obs

# GUI Manager for screenshot and GUI action execution
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.utils.coordinate import transform_coordinate

from game_servers.slay_the_spire.game.communication.coordinator import Coordinator
from game_servers.slay_the_spire.game.communication.action import StartGameAction
from game_servers.slay_the_spire.game.rule_agent.agent import SimpleAgent
from game_servers.slay_the_spire.game.spire.screen import ScreenType
from game_servers.slay_the_spire.game.spire.game import Game, RoomPhase
from game_servers.slay_the_spire.game.spire.character import PlayerClass

from game_servers.slay_the_spire.game.communication.action import Action as Skill
from game_servers.slay_the_spire.game.communication.action import PlayCardAction, EndTurnAction, ChooseAction, StateAction, CardRewardAction, CancelAction, ProceedAction


logger = logging.getLogger(__name__)

@dataclass
class SlayTheSpireObs(Obs):
    game: Game
    image: Image.Image

    def to_text(self):
        '''
        screenshot do not update the dead monsters' index, so we only use text info here
        only in semantic mode prompt
        '''
        is_combat = self.game.play_available
        # is_combat = self.game.play_available or self.game.end_available
        is_card_choice = self.game.choice_available and self.game.screen_type == ScreenType.CARD_REWARD and self.game.room_phase == RoomPhase.COMPLETE

        if is_combat:
            return self.get_combat_prompt()
        
        if is_card_choice:
            return "card choice stage"

        raise NotImplementedError

    # def powers2str(self, powers):
    #     if len(powers) == 0:
    #         return "- Powers: None\n"

    #     text = "- Powers:\n"
    #     for power in powers:
    #         text += f"  - {power.power_name}: {power.description}\n"
    #     return text

    def get_combat_prompt(self):
        # player_status_text = (
        #     f"Player:\n"
        #     f"- Class: {self.game.character.name}\n"
        #     f"- HP: {self.game.player.current_hp}/{self.game.player.max_hp}\n"
        #     f"- Block: {self.game.player.block}\n"
        #     f"- Energy: {self.game.player.energy}\n"
        #     # f"{self.powers2str(self.game.player.powers)}"
        
        # )

        # relics_text = "\n".join(
        #     [
        #         f"Relic {index + 1}:\n"
        #         f"- Name: {relic.name}\n"
        #         f"- Description: {relic.description}\n"

        #         for index, relic in enumerate(self.game.relics)
        #     ]
        # )

        # cards_in_hand_text = "\n".join(
        #     [
        #         f"Card index {index + 1}:\n"
        #         f"- Name: {card.name}\n"
        #         f"- Type: {card.type.name.lower()}\n"
        #         f"- Description: {card.description}\n"
        #         f"- Cost: {card.cost}\n"
        #         f"- Has Target: {card.has_target}\n"

        #         for index, card in enumerate(self.game.hand)
        #     ]
        # )

        monsters_text = "\n".join(
            [
                f"Monster index {index + 1}:\n"
                # f"- Name: {monster.name}\n"
                # f"- HP: {monster.current_hp}/{monster.max_hp}\n"
                # f"- Block: {monster.block}\n"
                # f"- Intent: {monster.intent.name.lower()}\n"
                # f"- Is gone: {monster.is_gone}\n"
                # f"- Is half dead: {monster.half_dead}\n"
                # f"- Move base damage: {monster.move_base_damage}\n"
                # f"- Move adjust damage: {monster.move_adjusted_damage}\n"
                # f"- Move hits: {monster.move_hits}\n"
                # f"{self.powers2str(monster.powers)}"

                if not monster.is_gone or monster.half_dead else

                f"Monster index {index + 1}:\n"
                "- Is gone: True\n"

                for index, monster in enumerate(self.game.monsters)
            ]
        )

        prompt = (
            # f"COMBAT STATE (Turn {self.game.turn})\n\n"
            # f"{player_status_text}\n"
            # f"Relics:\n"
            # f"{relics_text}\n"
            # f"Cards in hand:\n"
            # f"{cards_in_hand_text}\n"
            f"Monsters:\n"
            f"{monsters_text}\n"
            f"Valid actions:\n"
            f"- PLAY <card_index>\n"
            f"- PLAY <card_index> <target_index>\n"
            f"- END\n"
        )

        return prompt

    # def get_card_choice_prompt(self):
    #     player_status_text = (
    #         f"Player:\n"
    #         f"- Class: {self.game.character.name}\n"
    #         f"- HP: {self.game.current_hp}/{self.game.max_hp}\n"
    #     )

    #     relics_text = "\n".join(
    #         [
    #             f"Relic {index + 1}:\n"
    #             f"- Name: {relic.name}\n"
    #             f"- Description: {relic.description}\n"

    #             for index, relic in enumerate(self.game.relics)
    #         ]
    #     )

    #     deck_text = ""
    #     for index, card in enumerate(self.game.deck):
    #         deck_text += f"Card index {index + 1}:\n- Name: {card.name}\n- Description: {card.description}\n"

    #     cards_text = ""
    #     for index, card in enumerate(self.game.screen.cards):
    #         cards_text += (
    #             f"Card index {index + 1}:\n"
    #             f"- Name: {card.name}\n"
    #             f"- Type: {card.type.name.lower()}\n"
    #             f"- Description: {card.description}\n"
    #             f"- Cost: {card.cost}\n"
    #         )

    #     prompt = (
    #         f"CARD REWARD SELECTION STATE\n\n"
    #         f"Floor: {self.game.floor}/50\n"
    #         f"{player_status_text}\n"
    #         f"Relics:\n"
    #         f"{relics_text}\n"
    #         f"Deck:\n"
    #         f"{deck_text}\n"
    #         f"Available Card Rewards:\n"
    #         f"{cards_text}\n"
    #         f"Valid actions:\n"
    #         f"- CHOOSE <card_index>\n"
    #         f"- SKIP\n"
    #     )

    #     return prompt

    def evaluate(self):
        if self.game.screen_type == ScreenType.GAME_OVER:
            if self.game.screen.victory:  # beat boss
                return self.game.floor, True
            else:
                return self.game.floor - 1, True
        return self.game.floor - 1, False


@dataclass
class SlayTheSpireAction(Action):
    """
    Slay the Spire 游戏动作类
    
    支持两种独立的动作模式:
    - semantic 模式: 使用 Skill 对象列表与 mod 通信
    - gui 模式: 使用 GUI_action 列表模拟鼠标/键盘操作（支持多个连续动作）
    """
    # semantic 模式使用（与 mod 通信）
    actions: List[Skill] = field(default_factory=list)
    
    # gui 模式使用（模拟鼠标/键盘，支持多个连续动作）
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    # 动作模式
    mode: str = "semantic"

    def __iter__(self) -> Iterator[Skill]:
        return iter(self.actions)

    def __getitem__(self, index: int) -> Skill:
        return self.actions[index]

    def __len__(self) -> int:
        return len(self.actions)
    
    def to_json(self) -> str:
        if self.gui_actions:
            return json.dumps([a.to_dict() for a in self.gui_actions])
        return json.dumps([str(a) for a in self.actions])


class SlayTheSpireEnv(BaseEnv):
    """
    Slay the Spire 游戏环境
    
    支持两种动作模式:
    - semantic: LLM 输出语义命令 (PLAY/END/CHOOSE)，通过 mod 通信执行
    - gui: LLM 输出 JSON 格式的鼠标/键盘动作，通过 GUIManager 执行
    """
    @dataclass
    class Config:
        task: str
        log_path: str
        action_mode: str  # "semantic" or "gui"
        mod_input_path: str
        mod_output_path: str
        window_title: str = "Modded Slay the Spire"

        player_class: str = "IRONCLAD"
        ascension_level: int = 0  # hard mode
        seed: int = 0
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)

    cfg: Config

    def configure(self):
        self.player_class = PlayerClass[self.cfg.player_class.upper()]
        self.ascension_level = self.cfg.ascension_level
        self.seed = self.cfg.seed
        self.action_mode = self.cfg.action_mode
        self.mod_input_path = self.cfg.mod_input_path
        self.mod_output_path = self.cfg.mod_output_path
        self.log_path = self.cfg.log_path
        self.step_count = 0
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # 初始化 GUI 管理器（用于截图和 GUI 动作执行）
        self.gui_manager = None
        self.game_window = None
        self._init_gui_manager()
        
        # 两种模式都需要 coordinator 与 mod 通信（用于获取游戏状态和评估）
        self.coordinator = Coordinator(self.mod_input_path, self.mod_output_path)
        self.rule_agent = SimpleAgent(chosen_class=self.player_class)
        self.start_game(self.coordinator, self.rule_agent)
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器"""
        self.gui_manager = GUIManager()
        
        # 查找游戏窗口
        window_pattern = self.cfg.window_title
        self.game_window = self.gui_manager.find_window(window_pattern)

        if self.game_window is None:
            logger.warning(f"Cannot find game window: {self.cfg.window_title}")
        else:
            # 激活游戏窗口
            self.gui_manager.activate(self.game_window)
            logger.info(f"Found game window: {self.game_window.title}")
    
    def _capture_screen(self) -> Optional[Image.Image]:
        """使用 GUIManager 截取游戏画面"""
        if self.gui_manager and self.game_window:
            try:
                # 刷新窗口信息
                self.game_window = self.gui_manager.refresh_window(self.game_window)
                image = self.gui_manager.capture(self.game_window)
                
                # 保存截图到日志目录
                self.step_count += 1
                image_path = os.path.join(self.log_path, "obs_images", f"step_{self.step_count:04d}.png")
                image.save(image_path)
                
                return image
            except Exception as e:
                logger.warning(f"GUIManager capture failed: {e}")
                return None
        return None
    
    def _get_window_size(self) -> tuple:
        """获取游戏窗口大小"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (1920, 1080)  # 默认大小

    def start_game(self, coordinator, agent):
        coordinator.register_state_change_callback(agent.get_next_action_in_game)

        coordinator.clear_actions()
        logger.info("start_game")
        if not coordinator.in_game:
            logger.info("StartGameAction starts")
            StartGameAction(self.player_class, self.ascension_level, self.seed).execute(coordinator)
            coordinator.receive_game_state_update(block=True)

    def is_awaken_one_half_dead(self, game_state: Game) -> bool:
        if game_state.room_type == "MonsterRoomBoss" and game_state.floor == 50:
            for monster in game_state.monsters:
                if monster.name == "Awakened One" and monster.half_dead:
                    return True
        return False

    def is_handled_by_rules(self, game_state: Game) -> bool:
        logger.info(f"game_state.play_available: {game_state.play_available}")
        logger.info(f"game_state.end_available: {game_state.end_available}")
        logger.info(f"game_state.choice_available: {game_state.choice_available}")
        logger.info(f"game_state.screen_type: {game_state.screen_type}")

        is_combat = game_state.play_available
        is_card_choice = game_state.choice_available and game_state.screen_type == ScreenType.CARD_REWARD and game_state.room_phase == RoomPhase.COMPLETE

        return not is_combat and not is_card_choice

    def initial_obs(self) -> SlayTheSpireObs:
        """
        获取初始观察
        
        两种模式都通过 mod 通信获取游戏状态，等待可操作状态后返回 Obs
        区别在于：
        - semantic 模式: 在循环中执行 action_queue 中的多个动作
        - gui 模式: 使用专用的轮询逻辑获取状态
        """
        if self.action_mode == "gui":
            return self._get_obs_from_game_gui(timeout=10.0, require_update=False)
        else:
            return self._get_obs_from_game_semantic()
    
    def _get_obs_from_game_semantic(self) -> SlayTheSpireObs:
        """
        从游戏获取观察状态（Semantic 模式专用）
        
        Args:
            execute_actions: 是否执行 action_queue 中的动作
                - semantic 模式: True，循环执行队列中的所有动作
        """
        while True:
            logger.info("Start while loop")
            logger.info(f"action_queue: {self.coordinator.action_queue}")

            if self.coordinator.last_error is not None:
                logger.info(f"Game-side action error occured: {self.coordinator.last_error}")
                logger.info(f"Clear action queue.")
                self.coordinator.clear_actions()
                StateAction().execute(self.coordinator)

            # 执行 action_queue 中的动作
            if (len(self.coordinator.action_queue) > 0):
                logger.info(f"self.coordinator.action_queue[0].requires_game_ready: {self.coordinator.action_queue[0].requires_game_ready}")
                logger.info(f"self.coordinator.game_is_ready: {self.coordinator.game_is_ready}")
            if len(self.coordinator.action_queue) > 0 and self.coordinator.action_queue[0].can_be_executed(self.coordinator):
                logger.info("Execute action in action queue")
                try:
                    self.coordinator.execute_next_action()
                except Exception as e:
                    logger.info(f"Agent-side action error occured: {e}")
                    logger.info(f"Clear action queue.")
                    self.coordinator.clear_actions()
                    StateAction().execute(self.coordinator)
                continue

            if len(self.coordinator.action_queue) > 0:
                logger.info("Action queue is not empty, but game is not ready. Wait until state update.")
                self.coordinator.receive_game_state_update(block=True)
                continue

            logger.info("Action queue is empty")
            logger.info("Receive game state update")
            self.coordinator.receive_game_state_update(block=True)

            game_state = self.coordinator.last_game_state
            if self.is_awaken_one_half_dead(game_state):
                # when Awakened One is half dead, the game returns play_available = True,
                # even though the play is not available
                # so we manually end the turn
                self.coordinator.clear_actions()
                self.coordinator.add_action_to_queue(EndTurnAction())
                continue

            if not self.is_handled_by_rules(game_state):
                # if boss room and potion is available, use potion first
                logger.info("Find game state!!")
                logger.info(f"game_state: {game_state.__dict__}")
                self.coordinator.clear_actions()

                if game_state.room_type == "MonsterRoomBoss" and len(game_state.get_real_potions()) > 0:
                # if len(game_state.get_real_potions()) > 0:
                    potion_action = self.rule_agent.use_next_potion()
                    if potion_action is not None:
                        self.coordinator.add_action_to_queue(potion_action)
                        continue

                # 始终获取图像
                time.sleep(1.0)
                image = self._capture_screen()
                
                return SlayTheSpireObs(game=game_state, image=image)
        
            if game_state.screen_type == ScreenType.GAME_OVER:
                logger.info("Game Over")
                self.coordinator.clear_actions()

                time.sleep(1.0)
                image = self._capture_screen()
                
                return SlayTheSpireObs(game=game_state, image=image)
    
    def _get_obs_from_game_gui(self, timeout: float = 5.0, require_update: bool = False) -> SlayTheSpireObs:
        """
        GUI模式从游戏获取观察状态
        
        GUI 模式下，LLM 的动作通过 GUIManager 执行，
        但非战斗/非卡牌选择状态，仍然由 rule_agent 通过 coordinator 自动处理。
        
        流程：
        1. 轮询获取最新的游戏状态
        2. 如果是非 LLM 可操作状态，使用 rule_agent 自动处理
        3. 如果是战斗或卡牌选择状态，返回给 LLM 决策
        
        Args:
            timeout: 等待状态更新的超时时间（秒）
            require_update: 是否强制等待至少一次状态更新（用于 step 后确认动作生效）
        
        Returns:
            SlayTheSpireObs: 游戏观察状态
        """
        start_time = time.time()
        
        # 如果要求强制更新（通常在执行动作后），尝试等待新的状态包
        if require_update:
            try:
                # 等待动作的即时反馈（如 能量减少、进入敌方回合等）
                # 5秒足够 Mod 发送状态更新；如果超时，可能是无效点击或 Mod 无响应
                update_received = self.coordinator.receive_game_state_update(block=True, timeout=5.0)
                if not update_received:
                    logger.warning("GUI mode: No immediate state update received after action. Assuming invalid action or no state change.")
            except Exception as e:
                logger.warning(f"GUI mode: Error waiting for immediate update: {e}")

        while True:
            elapsed = time.time() - start_time
            
            # 如果有错误，清空并请求状态
            if self.coordinator.last_error is not None:
                logger.info(f"GUI mode: Game-side error occurred: {self.coordinator.last_error}")
                self.coordinator.clear_actions()
                StateAction().execute(self.coordinator)
            
            # 执行 action_queue 中由 rule_agent 生成的动作
            if len(self.coordinator.action_queue) > 0:
                if self.coordinator.action_queue[0].can_be_executed(self.coordinator):
                    logger.info(f"GUI mode: Executing rule_agent action: {self.coordinator.action_queue[0]}")
                    try:
                        self.coordinator.execute_next_action()
                    except Exception as e:
                        logger.warning(f"GUI mode: Error executing action: {e}")
                        self.coordinator.clear_actions()
                        StateAction().execute(self.coordinator)
                    continue
                else:
                    # 动作队列非空但无法执行，等待状态更新
                    logger.info("GUI mode: Action queue not empty, waiting for game ready")
                    self.coordinator.receive_game_state_update(block=True, timeout=1.0)
                    continue
            
            # 先尝试非阻塞获取状态更新（清空队列中可能的旧状态）
            while self.coordinator.receive_game_state_update(block=False):
                pass
            
            # 阻塞等待新的状态更新
            try:
                remaining_timeout = max(0.1, timeout - elapsed)
                self.coordinator.receive_game_state_update(block=True, timeout=min(1.0, remaining_timeout))
            except Exception as e:
                logger.warning(f"GUI mode: Timeout waiting for game state update: {e}")
            
            game_state = self.coordinator.last_game_state
            
            if game_state is None:
                if elapsed > timeout:
                    logger.warning("GUI mode: Timeout - No game state received")
                    time.sleep(0.5)
                    image = self._capture_screen()
                    return SlayTheSpireObs(game=game_state, image=image)
                continue
            
            logger.info(f"GUI mode: received game state, screen_type={game_state.screen_type}")
            
            # 检查是否游戏结束
            if game_state.screen_type == ScreenType.GAME_OVER:
                logger.info("GUI mode: Game Over")
                time.sleep(0.5)
                image = self._capture_screen()
                return SlayTheSpireObs(game=game_state, image=image)
            
            # 处理 Awakened One 半死状态
            if self.is_awaken_one_half_dead(game_state):
                logger.info("GUI mode: Awakened One is half dead, ending turn")
                self.coordinator.clear_actions()
                self.coordinator.add_action_to_queue(EndTurnAction())
                continue
            
            # 检查是否是 LLM 可操作的状态（战斗或卡牌选择）
            is_combat = game_state.play_available
            is_card_choice = (game_state.choice_available and 
                            game_state.screen_type == ScreenType.CARD_REWARD and 
                            game_state.room_phase == RoomPhase.COMPLETE)
            
            if is_combat or is_card_choice:
                logger.info(f"GUI mode: Found LLM actionable state (combat={is_combat}, card_choice={is_card_choice})")
                self.coordinator.clear_actions()
                
                # Boss 战中自动使用药水
                if game_state.room_type == "MonsterRoomBoss" and len(game_state.get_real_potions()) > 0:
                    potion_action = self.rule_agent.use_next_potion()
                    if potion_action is not None:
                        logger.info(f"GUI mode: Using potion in boss fight: {potion_action}")
                        self.coordinator.add_action_to_queue(potion_action)
                        continue
                
                # 等待动画和状态稳定 (2.0s)
                # 这样做是为了过滤掉瞬态的 True 状态（例如点击回合结束时的瞬间），
                # 并确保截图时动画已完成（如抽牌动画）。
                logger.info("GUI mode: Waiting for state stability and animations (2.0s)...")
                time.sleep(2.0)
                
                # 消耗掉等待期间所有积压的状态更新，获取最新的状态
                while self.coordinator.receive_game_state_update(block=False):
                    pass
                
                current_game_state = self.coordinator.last_game_state
                
                # 如果状态为空（理论上不应发生），继续循环
                if current_game_state is None:
                    continue

                # 再次检查最新状态是否仍为可操作状态
                current_is_combat = current_game_state.play_available
                current_is_card_choice = (current_game_state.choice_available and 
                                current_game_state.screen_type == ScreenType.CARD_REWARD and 
                                current_game_state.room_phase == RoomPhase.COMPLETE)

                # 如果在等待期间状态变成了不可操作（例如进入了敌方回合），则视为之前的 True 是瞬态噪声，忽略并继续等待
                if not (current_is_combat or current_is_card_choice):
                     logger.info(f"GUI mode: State changed during wait (Actionable -> Not Actionable). "
                                 f"Combat: {is_combat}->{current_is_combat}, "
                                 f"Card: {is_card_choice}->{current_is_card_choice}. Continuing loop.")
                     continue
                
                # 状态稳定且可操作，截图返回
                image = self._capture_screen()
                return SlayTheSpireObs(game=current_game_state, image=image)
            
            # --- 增加防抖逻辑，防止 Rule Agent 在回合初秒过回合 ---
            # 如果处于 Combat 阶段，play_available 为 False，但 end_available 为 True
            # 这极有可能是回合开始的抽牌阶段，或者动画阶段。
            # 为了防止 Rule Agent 误判并秒过回合，我们需要进行“防抖”等待。
            if (not is_combat 
                and not is_card_choice 
                # and game_state.room_phase == RoomPhase.COMBAT # RoomPhase.COMBAT 可能更新不及时，去掉
                and game_state.screen_type == ScreenType.NONE 
                and game_state.end_available):
                
                logger.info("GUI mode: Detected potential unstable combat state (end_available=True but play_available=False + COMBAT state). Assuming draw phase. Waiting for state update without ending turn.")
                time.sleep(2.0)
                
                # 刷新并获取最新状态
                while self.coordinator.receive_game_state_update(block=False): pass
                # 尝试获取最新状态
                receive_success = self.coordinator.receive_game_state_update(block=True, timeout=1.0)
                
                if receive_success:
                    game_state = self.coordinator.last_game_state
                    # 重新检查 is_combat
                    current_is_combat = game_state.play_available
                    
                    if current_is_combat:
                        logger.info("GUI mode: State stabilized to COMBAT (play_available=True). Handing over to LLM instead of Rule Agent.")
                        logger.info("GUI mode: Valid LLM state detected after wait. Looping back.")
                        continue
                else: 
                     logger.info("GUI mode: No new state received after wait. Continuing loop (retrying) instead of defaulting to Rule Agent.")
                     continue
            # -----------------------------------------------------

            # 非 LLM 可操作状态，使用 rule_agent 自动处理
                logger.info("GUI mode: Valid LLM state detected after wait. Looping back.")
                continue
            else: 
                logger.info("GUI mode: No new state received after wait. Continuing loop (retrying) instead of defaulting to Rule Agent.")
                continue
            # -----------------------------------------------------

            # # 非 LLM 可操作状态，使用 rule_agent 自动处理
            # logger.info(f"GUI mode: Non-LLM state, using rule_agent to handle")
            # self.coordinator.clear_actions()
            
            # # 调用 rule_agent 获取下一个动作
            # next_action = self.rule_agent.get_next_action_in_game(game_state)
            # if next_action is not None:
            #     logger.info(f"GUI mode: rule_agent returned action: {next_action}")
            #     self.coordinator.add_action_to_queue(next_action)
            #     continue
            
            # # rule_agent 返回 None（不应该发生，因为我们已经排除了战斗和卡牌选择）
            # # 尝试使用 proceed 或 cancel
            # if game_state.proceed_available:
            #     logger.info("GUI mode: Using ProceedAction")
            #     self.coordinator.add_action_to_queue(ProceedAction())
            #     continue
            # elif game_state.cancel_available:
            #     logger.info("GUI mode: Using CancelAction")
            #     self.coordinator.add_action_to_queue(CancelAction())
            #     continue
            
            # # 超时检查
            # if elapsed > timeout:
            #     logger.warning(f"GUI mode: Timeout waiting for actionable state, returning current state")
            #     time.sleep(0.5)
            #     image = self._capture_screen()
            #     return SlayTheSpireObs(game=game_state, image=image)
            
            # logger.info(f"GUI mode: Waiting for state change... (elapsed={elapsed:.1f}s)")
            # time.sleep(0.3)

    def obs2text(self, obs: SlayTheSpireObs) -> str:
        """将观察转换为文本（用于日志记录）"""
        try:
            return obs.to_text()
        except Exception as e:
            logger.warning(f"Failed to convert obs to text: {e}")
            return f"Game state: floor={obs.game.floor if obs.game else 'unknown'}"

    def parse_action(self, text: str) -> SlayTheSpireAction:
        """
        解析 LLM 输出文本为动作
        
        根据 action_mode 分别处理:
        - semantic: 解析 PLAY/END/CHOOSE 等命令
        - gui: 解析 JSON 格式的 GUI_action
        """
        if self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            return self._parse_semantic_action(text)
    
    def _parse_gui_action(self, text: str) -> SlayTheSpireAction:
        """解析 GUI 模式的动作（JSON 格式，支持单个或多个动作）"""
        try:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 尝试直接查找 JSON 数组或对象
                # 先尝试匹配数组
                array_match = re.search(r'\[\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*\]', text, re.DOTALL)
                if array_match:
                    json_str = array_match.group(0)
                else:
                    # 尝试匹配单个对象
                    obj_match = re.search(r'\{[^{}]*"action_type"[^{}]*\}', text, re.DOTALL)
                    if obj_match:
                        json_str = obj_match.group(0)
                    else:
                        json_str = text
            
            parsed_data = json.loads(json_str)
            
            # 支持数组或单个对象
            if isinstance(parsed_data, list):
                gui_actions = [GUI_action.from_dict(item) for item in parsed_data]
            else:
                gui_actions = [GUI_action.from_dict(parsed_data)]

            logger.info(f"Parsed {len(gui_actions)} GUI actions")
            action = SlayTheSpireAction(gui_actions=gui_actions, mode="gui")
            

            # 坐标转换逻辑
            if self.cfg.coor_trans and gui_actions:
                # 获取当前窗口实际大小
                width, height = self._get_window_size()
                
                for i, gui_act in enumerate(gui_actions):
                    # 转换 X 坐标
                    if "x" in gui_act.parameters:
                        original_x = gui_act.parameters["x"]
                        new_x = transform_coordinate(original_x, width)
                        gui_act.parameters["x"] = new_x
                        logger.info(f"Action {i} X transformed: {original_x} -> {new_x} (Width: {width})")
                    
                    # 转换 Y 坐标
                    if "y" in gui_act.parameters:
                        original_y = gui_act.parameters["y"]
                        new_y = transform_coordinate(original_y, height)
                        gui_act.parameters["y"] = new_y
                        logger.info(f"Action {i} Y transformed: {original_y} -> {new_y} (Height: {height})")
            
            return action
        except Exception as e:
            logger.warning(f"Failed to parse GUI action: {e}, text: {text}")
            # 返回一个空操作
            return SlayTheSpireAction(gui_actions=[], mode="gui")
    
    def _parse_semantic_action(self, text: str) -> SlayTheSpireAction:
        """解析 semantic 模式的动作（PLAY/END/CHOOSE 命令）"""
        actions = []

        # 处理字面 \n 和真正的换行符
        # LLM 有时会输出字面的 \n 而不是真正的换行符
        text = text.replace("\\n", "\n")
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("PLAY"):
                pattern = r"^PLAY (\d+)(?: (\d+))?$"
                match = re.match(pattern, line)

                if match:
                    # card_index: 1-index (1-index in prompt)
                    # target_index: 0-index (1-index in prompt)
                    card_index = int(match.group(1))
                    target_index = int(match.group(2)) - 1 if match.group(2) is not None else None

                    # convert index to card object, since the card can be changed in the game
                    if card_index < 1 or card_index > len(self.coordinator.last_game_state.hand):
                        logger.info(f"Invalid card index: {card_index}")
                        return SlayTheSpireAction(actions=[StateAction()], mode="semantic")
                    card = self.coordinator.last_game_state.hand[card_index - 1]
                    actions.append(PlayCardAction(card=card, target_index=target_index))
                else:
                    logger.info(f"Invalid command: {line}")
                    return SlayTheSpireAction(actions=[StateAction()], mode="semantic")
            elif line.startswith("END"):
                actions.append(EndTurnAction())
            elif line.startswith("CHOOSE"):
                # ensure ChooseAction is called only once
                if len(actions) > 0 and isinstance(actions[0], ChooseAction):
                    # if there is already a ChooseAction in the action queue, skip this action
                    continue

                pattern = r"^CHOOSE (\d+|.+)$"
                match = re.match(pattern, line)

                if match:
                    choice_value = match.group(1).strip()

                    if choice_value.isdigit():
                        # card choose index: 0-index (1-index in prompt)
                        actions.append(ChooseAction(choice_index=int(choice_value) - 1))
                    else:
                        actions.append(ChooseAction(name=choice_value))
                else:
                    logger.info(f"Invalid command: {line}")
                    return SlayTheSpireAction(actions=[StateAction()], mode="semantic")
            elif line.startswith("SKIP"):
                if self.coordinator.last_game_state.screen.can_bowl:
                    actions.append(CardRewardAction(bowl=True))
                else:
                    actions.append(ProceedAction())
            else:
                logger.info(f"Invalid command: {line}")
                return SlayTheSpireAction(actions=[StateAction()], mode="semantic")
        
        return SlayTheSpireAction(actions=actions, mode="semantic")

    def get_game_info(self) -> dict:
        """获取游戏信息，用于填充 prompt"""
        task_description = "Your objective is to reach floor 50 in Slay the Spire."
        
        # 如果启用坐标转换，返回归一化尺寸 1000x1000
        # 否则返回实际窗口大小
        if self.cfg.coor_trans:
            window_width, window_height = 1000, 1000
        else:
            window_width, window_height = self._get_window_size()

        return {
            "task_description": task_description,
            "window_width": window_width,
            "window_height": window_height,
        }

    def step(
        self, action: SlayTheSpireAction
    ) -> tuple[SlayTheSpireObs, float, bool, bool, dict[str, Any]]:
        """
        执行动作并返回新的观察
        
        根据 action_mode 分别处理:
        - semantic: 将动作放入 action_queue，由 initial_obs 循环执行
        - gui: 直接通过 GUIManager 执行单个动作，然后获取状态
        """
        if self.action_mode == "gui":
            return self._step_gui(action)
        else:
            return self._step_semantic(action)
    
    def _step_gui(self, action: SlayTheSpireAction) -> tuple[SlayTheSpireObs, float, bool, bool, dict[str, Any]]:
        """
        GUI 模式下执行动作
        
        依次执行多个 gui_actions，然后通过 mod 通信获取新状态
        使用专用的 _get_obs_from_game_gui 方法轮询状态更新
        """
        # 1. 消耗掉所有积压的旧消息，确保接下来读到的一定是动作之后产生的
        while self.coordinator.receive_game_state_update(block=False):
            pass

        if action.gui_actions and self.gui_manager and self.game_window:
            for i, gui_action in enumerate(action.gui_actions):
                try:
                    logger.info(f"Executing GUI action {i+1}/{len(action.gui_actions)}: {gui_action}")
                    self.gui_manager.execute(self.game_window, gui_action)
                    # 等待动作执行完成
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Failed to execute GUI action {i+1}: {e}")
            # 所有动作执行完后等待动画播放
            time.sleep(0.5)
        else:
            logger.warning("No valid GUI actions to execute or GUI manager not initialized")
            time.sleep(0.3)
        
        # 使用 GUI 专用方法获取新状态
        # require_update=True 确保我们等待动作生效后的状态更新
        # 避免在点击 "End Turn" 后立即使用旧的 "Player Turn" 状态截图
        obs = self._get_obs_from_game_gui(timeout=20.0, require_update=True)
        return obs, 0, False, False, {}
    
    def _step_semantic(self, action: SlayTheSpireAction) -> tuple[SlayTheSpireObs, float, bool, bool, dict[str, Any]]:
        """
        Semantic 模式下执行动作
        
        将动作放入 action_queue，由 _get_obs_from_game_semantic 循环执行
        """
        self.coordinator.clear_actions()
        self.coordinator.action_queue.extend(action.actions)
        
        # 执行 action_queue 中的动作并获取状态
        obs = self._get_obs_from_game_semantic()

        return obs, 0, False, False, {}

    def evaluate(self, obs: SlayTheSpireObs):
        """评估游戏状态（两种模式都通过 mod 获取状态进行评估）"""
        return obs.evaluate()
