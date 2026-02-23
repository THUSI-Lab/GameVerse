import json
import time
import os
import re
import shutil
import random

import logging
from PIL import Image
from dataclasses import dataclass, field
from typing import Any, List, Tuple, Optional, Iterator

from game_servers.base_env import BaseEnv
from game_servers.gameio.window_capture import WindowCapture
from game_servers.utils.types.game_io import Action, Obs

# GUI Manager for screenshot and GUI action execution
from game_servers.GUI.GUI_manager import GUIManager
from game_servers.GUI.act.actions import GUI_action
from game_servers.GUI.act.action_space import ActionType
from game_servers.utils.coordinate import transform_coordinate

from game_servers.pwaat.game.fileio import (
    ActiveKeyTypeLoader,
    ConversationLogLoader,
    MultiChoiceLoader,
    RecordEvidenceLogLoader,
    RecordProfileLogLoader,
    FlagChecker,
    AutoInputFileCreator,
    CurrentSavepageIndexLoader,
    ConfirmInitialCursorLoader,
    OptionCursorLoader,
)

logger = logging.getLogger(__name__)

SPK_ID_TO_NAME = {
    "0": "System Description",
    "1": "???",
    "2": "Phoenix Wright",
    "7": "Mia Fey",
    "8": "Judge",
    "10": "Winston Payne",
    "25": "Larry Butz",
    "26": "Frank Sahwit",
    "balloon_2": "Balloon (Objection)",
    "balloon_3": "Balloon (Objection)",
    "balloon_4": "Balloon (TakeThat)",
    "balloon_12": "Balloon (HoldIt)",
}


NICKNAMES = {
    "Alias": ["Phoenix Wright", "P. Wright", "Phoenix", "Wright"],
    "Bravo": ["Mia Fey", "M. Fey", "Mia", "Fey"],
    "Charlie": ["Winston Payne", "W. Payne", "Winston", "Payne"],
    "Delta": ["Larry Butz", "L. Butz", "Larry", "Butz"],
    "Echo": ["Frank Sahwit", "F. Sahwit", "Frank", "Sahwit"],
    "Foxtrot": ["Cindy Stone", "C. Stone", "Cindy", "Stone"],
}


def replace_character_names(text):
    patterns = []
    for letter, names in NICKNAMES.items():
        for name in names:
            patterns.append((name, letter))

    patterns.sort(key=lambda x: len(x[0]), reverse=True)

    result_text = text
    for pattern, letter in patterns:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)
        result_text = regex.sub(letter, result_text)

    return result_text


KEYTYPE_TO_KEYNAME = {
    "R": "Tab",
    "A": "Ok",
    "B": "Back",
    "Start": "ESC",
    "Down": "Down",
    "Up": "Up",
    "Left": "Left",
    "Right": "Right",
    "X": "Present the selected evidence",
    "L": "Press at the moment of testimony"
}


KEYNAME_TO_KEYTYPE = {value: key for key, value in KEYTYPE_TO_KEYNAME.items()}


KEYTYPE_TO_KEYFUNC = {
    "GENERAL": {
        key: "GetKeyDown"
        for key in KEYTYPE_TO_KEYNAME.keys()
    },
    # "GENERAL_RECORD": {
    #     key: "GetKeyDown"
    #     for key in KEYTYPE_TO_KEYNAME.keys()
    # },
    "MULTI_CHOICE": {
        key: "GetKeyDown"
        for key in KEYTYPE_TO_KEYNAME.keys()
    },
    "CROSS_EXAMINATION_RECORD": {
        key: ("GetKey" if key in ["Down", "Up",
              "Left", "Right"] else "GetKeyDown")
        for key in KEYTYPE_TO_KEYNAME.keys()
    }
}


GENERAL = "GENERAL"
# GENERAL_RECORD = "GENERAL_RECORD"
MULTI_CHOICE = "MULTI_CHOICE"
CROSS_EXAMINATION_RECORD = "CROSS_EXAMINATION_RECORD"


STATE_TEMPLATES = {
    GENERAL: (
        "[Recent Conversations]\n{conversations}"
    ),
    # GENERAL_RECORD: (
    #     "[Recent Conversations]\n{conversations}"
    # ),
    MULTI_CHOICE: (
        "[Multi-Choice Question]\n{multi_choice_question}"
    ),
    CROSS_EXAMINATION_RECORD: (
        "[Recent Conversations]\n{conversations}"
    )
}


LAST_RECORD_TEMPLATES = (
    "**Last Check Time**: {timestamp}\n"
    "**Court Record - Evidence**:\n{record_evidence}\n"
    "**Court Record - Profile**:\n{record_profile}"
)


POSSIBLE_OPTIONS = {
    GENERAL: "**Possible Options** (Active Key Types):\n{option_list}",
    # GENERAL_RECORD: "**Possible Options** (Active Key Types):\n{option_list}",
    MULTI_CHOICE: "**Possible Options** (Answer Candidates):\n{option_list}",
    CROSS_EXAMINATION_RECORD: "**Possible Options** (Evidence Items):\n{option_list}",
}


REWARD_CHECKER = {
    "multiple_choice_idx": 0,
    "multiple_choice": "Correct.",
    "multiple_choice_start": "The test will consist of a few simple questions. Answer them clearly and concisely.",
    "multiple_choice_end": "You've answered all my questions. I see no reason why we shouldn't proceed.",
    "cross_examination_1_idx": 1,
    "cross_examination_1": "You found the body at 1:00 PM. You're sure?",
    "cross_examination_1_start": "Open the Court Record with <color=#ff0000>         </color>, then point out <color=#ff0000>contradictions</color> in the testimony!",
    "cross_examination_1_end": "You found the body at 1:00 PM. You're sure?",
    "cross_examination_1_fail": "That's enough!",
    "cross_examination_2_idx": 2,
    "cross_examination_2": "Hold it right there!",
    "cross_examination_2_start": "I've got this one.",
    "cross_examination_2_end": "Hold it right there!",
    "cross_examination_2_fail": "That's enough!",
    "cross_examination_3_idx": 3,
    "cross_examination_3": "Wait just a moment!",
    "cross_examination_3_start": "Gladly.",
    "cross_examination_3_end": "Wait just a moment!",
    "cross_examination_3_fail": "That's enough!",
    "cross_examination_4_idx": 4,
    "cross_examination_4": "This case has certainly turned out differently than we all expected.",
    "cross_examination_4_start": "",
    "cross_examination_4_end": "This case has certainly turned out differently than we all expected.",
    "cross_examination_4_fail": "That's enough!",
    # Full game task - no specific start/end checkers, play from beginning
    "full_game_idx": -1,  # No specific save file index
    "full_game": None,  # No specific reward checker
    "full_game_start": None,  # No specific start checker
    "full_game_end": None,  # No specific end checker (will use max_steps or manual termination)
    "full_game_fail": None,  # No specific fail checker
}


def check_reward(checker:str, conversation:str, ):
    if checker is None:
        return False
    return checker.lower() == conversation[-1]["conversation"].lower().strip().replace("\n", " ")


def format_conversation_entry(entry: dict, is_latest: bool, only_text: bool = False) -> str:
    """Format a single conversation entry with timestamp, speaker, and message.
    
    Args:
        entry (dict): Conversation entry containing timestamp, speaker, and conversation
        is_latest (bool): Whether this is the most recent conversation entry
        
    Returns:
        str: Formatted conversation string
    """
    timestamp = entry.get('timestamp')
    if is_latest:
        timestamp = f"**The Conversation Currently on Screen** - {timestamp}"
    if only_text:
        return replace_character_names(entry.get('conversation'))
    return f"[{timestamp}] {replace_character_names(SPK_ID_TO_NAME[entry.get('speaker')])}: {replace_character_names(entry.get('conversation'))}"


@dataclass
class PwaatObs(Obs):
    ARROW_FLAG: bool
    active_keytype: list
    conversation: list
    last_conversation_str: str
    conversation_history_len: int
    multi_choice: dict
    record_evidence: dict
    record_profile: dict
    is_xexam: bool
    image: Image.Image = None
    _formatted_text: str = field(default="", init=False)

    def parse_obs(self) -> tuple[str, str, str, dict, str, str]:
        task_name = GENERAL
        if self.multi_choice:
            task_name = MULTI_CHOICE
        elif self.record_evidence:
            if self.is_xexam:
                task_name = CROSS_EXAMINATION_RECORD

        # Enumerate active key types as a numbered list
        active_keytype = self.active_keytype
        if task_name == GENERAL:
            active_keytype = [
                key for key in self.active_keytype if key in ['R', 'A', 'L', 'Left']]
        # elif task_name == GENERAL_RECORD:
        #     active_keytype = [
        #         key for key in self.active_keytype if key in ['B']]
        active_key_str = "\n".join(
            f"{idx}: {KEYTYPE_TO_KEYNAME[key]}" for idx, key in enumerate(active_keytype, start=1) if key in KEYTYPE_TO_KEYNAME
        )

        # Format recent conversations (only include non-empty texts)
        recent_conversations = self.conversation[-self.conversation_history_len:]
        conversations_str = "\n".join(
            format_conversation_entry(entry, is_latest=entry is recent_conversations[-1])
            for entry in recent_conversations if entry.get('conversation').strip()
        )

        # Format multi_choice info: question and enumerated options
        multi_choice_question = self.multi_choice.get("question", "")
        multi_choice_options = "\n".join(
            f"{idx}: {replace_character_names(option)}" for idx, option in enumerate(self.multi_choice.get("option", []), start=1)
        )

        # Format record evidence: enumerate each entry (sorted by key) starting at 1
        record_evidence_str = "\n".join(
            f"{idx}: {replace_character_names(data.get('name'))} - {replace_character_names(data.get('desc'))}"
            for idx, (eid, data) in enumerate(sorted(self.record_evidence.items()), start=1)
        )

        # Format record profile: enumerate each entry (sorted by key) starting at 1
        record_profile_str = "\n".join(
            f"{idx}: {replace_character_names(data.get('name'))} - {replace_character_names(data.get('desc'))}"
            for idx, (pid, data) in enumerate(sorted(self.record_profile.items()), start=1)
        )

        # Determine the option list based on the task type
        if task_name == GENERAL:
            option_list_str = active_key_str
        # elif task_name == GENERAL_RECORD:
        #     option_list_str = active_key_str
        elif task_name == MULTI_CHOICE:
            option_list_str = multi_choice_options
        elif task_name == CROSS_EXAMINATION_RECORD:
            # For cross-examination RECORD, list only the evidence names
            option_list_str = record_evidence_str
        else:
            raise ValueError()

        # Select and fill the appropriate template
        template = STATE_TEMPLATES.get(task_name, STATE_TEMPLATES[GENERAL])
        self._formatted_text = template.format(
            active_keytype=active_key_str,
            conversations=conversations_str,
            multi_choice_question=multi_choice_question,
            record_evidence=record_evidence_str,
            record_profile=record_profile_str
        )

        if self.is_xexam:
            self._formatted_text = "**Cross-Examination!**\n" + self._formatted_text

        # logger.info(f"formatted_text: {self._formatted_text}")

        option_dict = {}
        for line in option_list_str.splitlines():
            line = line.strip()
            if line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key_part = parts[0].strip()
                    value_part = parts[1].strip()
                    try:
                        key = int(key_part)
                    except ValueError:
                        key = key_part
                    option_dict[key] = value_part

        return task_name, option_list_str, option_dict, record_evidence_str, record_profile_str

    def to_text(self) -> str:
        return self._formatted_text


@dataclass
class PwaatAction(Action):
    """
    Pwaat 游戏动作类
    
    支持两种动作模式:
    - semantic: 使用 action_sequence 字符串与游戏通信（通过文件I/O）
    - gui: 使用 GUI_action 列表模拟键盘操作（支持多个连续动作）
    """
    # semantic 模式使用（与游戏通信）
    action_sequence: str = ""
    
    # gui 模式使用（模拟键盘，支持多个连续动作）
    gui_actions: List[GUI_action] = field(default_factory=list)
    
    # 动作模式
    mode: str = "semantic"
    
    SEP: str = ","

    @classmethod
    def format(cls, input_list, keyfunc_dict):
        formatted_list = [
            f"{key}:{keyfunc_dict.get(key, 'GetKeyDown')}" for key in input_list
        ]
        return cls.SEP.join(formatted_list)

    def to_list(self):
        return self.action_sequence.split(self.SEP)

    def get_action(self):
        return self.action_sequence

    def is_empty(self):
        if self.mode == "gui":
            return len(self.gui_actions) == 0
        return self.action_sequence == ""

    def is_passed(self):
        return self.action_sequence == "Passed"
    
    def to_json(self) -> str:
        if self.gui_actions:
            return json.dumps([a.to_dict() for a in self.gui_actions])
        return json.dumps([self.action_sequence])


class PwaatEnv(BaseEnv):
    @dataclass
    class Config:
        task: str
        log_path: str
        state_root_dir: str
        conversation_history_len: int
        input_modality: str = "text"
        auto_savedfile: bool = False
        action_mode: str = "gui"  # "semantic" or "gui"
        window_title: str = r"Phoenix Wright.*Ace Attorney Trilogy|逆転裁判123.*成歩堂セレクション"
        milestone_model: str = "gemini-2.0-flash-exp"  # 用于提取里程碑的模型
        coor_trans: bool = False  # 是否启用坐标转换 (1000x1000 -> 实际分辨率)

    cfg: Config
    auto_savedfile: bool = False
    task: str = "multiple_choice"
    reward: int = 0
    done: bool = False
    is_xexam: bool = False
    current_turn: int = 0
    current_task: str = GENERAL
    current_option_list: str = ''
    current_option_dict: dict = {}
    last_record_time: str = ''
    last_record_evidence: str = ''
    last_record_profile: str = ''
    last_decisions: list = []
    input_modality: str = "text"
    action_mode: str = "gui"
    
    # GUI 模式相关
    gui_manager: Optional[GUIManager] = None
    game_window: Optional[Any] = None
    step_count: int = 0

    def configure(self):
        self.task = self.cfg.task
        assert self.task in REWARD_CHECKER.keys() or self.task == "full_game", "Invalid task"
        
        # Full game task doesn't use auto_savedfile
        if self.task == "full_game":
            self.auto_savedfile = False
            self.savedfile_idx = -1
            self.reward_checker = None
            self.starting_checker = None
            self.ending_checker = None
            self.fail_checker = None
        else:
            self.auto_savedfile = self.cfg.auto_savedfile
            self.savedfile_idx = REWARD_CHECKER[self.task+"_idx"]
            self.reward_checker = REWARD_CHECKER[self.task]
            self.starting_checker = REWARD_CHECKER[self.task+"_start"]
            self.ending_checker = REWARD_CHECKER[self.task+"_end"]
            self.fail_checker = REWARD_CHECKER[self.task+"_fail"] if self.task+"_fail" in REWARD_CHECKER.keys() else None
        self.state_root_dir = self.cfg.state_root_dir
        self.conversation_history_len = self.cfg.conversation_history_len
        self.action_mode = self.cfg.action_mode
        self.log_path = self.cfg.log_path
        self.step_count = 0
        
        # 确保日志目录存在
        os.makedirs(self.log_path, exist_ok=True)
        os.makedirs(os.path.join(self.log_path, "obs_images"), exist_ok=True)
        
        # GUI 模式初始化
        if self.action_mode == "gui":
            self._init_gui_manager()
        else:
            # Semantic 模式初始化（原有逻辑）
            self.ARROW_FLAG_checker: FlagChecker = FlagChecker(
                file_path=os.path.join(self.state_root_dir, "ARROW_FLAG.txt"))
            # self.XEXAM_FLAG_checker: FlagChecker = FlagChecker(
            #     file_path=os.path.join(self.state_root_dir, "XEXAM_FLAG.txt"))
            self.active_keytype_lodder: ActiveKeyTypeLoader = ActiveKeyTypeLoader(
                file_path=os.path.join(self.state_root_dir, "active_keytype.txt"), default_output=[])
            self.current_savepage_index_lodder: CurrentSavepageIndexLoader = CurrentSavepageIndexLoader(
                file_path=os.path.join(self.state_root_dir, "current_savepage_index.txt"), default_output=0)
            self.confirm_initial_cursor_lodder: ConfirmInitialCursorLoader = ConfirmInitialCursorLoader(
                file_path=os.path.join(self.state_root_dir, "confirm_initial_cursor.txt"), default_output="Yes")
            self.option_cursor_lodder: OptionCursorLoader = OptionCursorLoader(
                file_path=os.path.join(self.state_root_dir, "option_cursor.txt"), default_output="Save")
            self.conversation_lodder: ConversationLogLoader = ConversationLogLoader(
                file_path=os.path.join(self.state_root_dir, "conversation_log.txt"), default_output=[], max_retries='inf')
            self.multi_choice_lodder: MultiChoiceLoader = MultiChoiceLoader(
                file_path=os.path.join(self.state_root_dir, "multi_choice.json"), default_output={})
            self.record_evidence_lodder: RecordEvidenceLogLoader = RecordEvidenceLogLoader(
                file_path=os.path.join(self.state_root_dir, "record_evidence_log.txt"), default_output=({}, ""))
            self.record_profile_lodder: RecordProfileLogLoader = RecordProfileLogLoader(
                file_path=os.path.join(self.state_root_dir, "record_profile_log.txt"), default_output=({}, ""))
            self.auto_input_creator: AutoInputFileCreator = AutoInputFileCreator(
                file_path=os.path.join(self.state_root_dir, "auto_input.txt"))
            self.input_modality = self.cfg.input_modality
            self.use_image = self.input_modality in ["image", "text_image"]
            if self.use_image:
                self.window_capture = WindowCapture(r"^Phoenix Wright.*Ace Attorney Trilogy.*", mode="bitblt")
    
    def _init_gui_manager(self):
        """初始化 GUI 管理器（仅用于GUI模式）"""
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
        """使用 GUIManager 截取游戏画面（仅用于GUI模式）"""
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
        """获取游戏窗口大小（仅用于GUI模式）"""
        if self.gui_manager and self.game_window:
            try:
                left, top, width, height = self.gui_manager.get_window_rect(self.game_window)
                return (width, height)
            except Exception as e:
                logger.warning(f"Failed to get window size: {e}")
        return (1920, 1080)  # 默认大小
    
    def _get_task_description(self) -> str:
        """获取任务描述（用于GUI模式）"""
        task_descriptions = {
            "multiple_choice": "Answer the multiple-choice questions correctly.",
            "cross_examination_1": "Cross-examine the witness and find contradictions. Present evidence when you identify a contradiction.",
            "cross_examination_2": "Cross-examine the witness and find contradictions. Present evidence when you identify a contradiction.",
            "cross_examination_3": "Cross-examine the witness and find contradictions. Present evidence when you identify a contradiction.",
            "full_game": "Play through the entire game from the beginning. Navigate through all dialogues, make choices, cross-examine witnesses, and present evidence to solve the case. The goal is to complete the full game story.",
        }
        return task_descriptions.get(self.task, f"Complete the task: {self.task}")

    def get_active_keytype(self, wait_for_update=True):
        while True:
            if not self.active_keytype_lodder.exists():
                continue
            time.sleep(0.5)
            active_keytype = self.active_keytype_lodder.load(
                    wait_for_update=wait_for_update, and_delete=True)
            if len(active_keytype) > 0:
                break
            self.active_keytype_lodder.remove()
        return active_keytype

    def get_current_obs(self, wait_for_update=True) -> Obs:
        if self.action_mode == "gui":
            # GUI模式：使用截图作为观察
            image = self._capture_screen()
            if image is None:
                logger.warning("Failed to capture screen, using blank image")
                image = Image.new('RGB', (1920, 1080), color='black')
            
            # 创建一个简化的观察对象（GUI模式主要依赖截图）
            obs = PwaatObs(
                ARROW_FLAG=False,
                active_keytype=[],
                conversation=[],
                last_conversation_str="",
                conversation_history_len=self.conversation_history_len,
                multi_choice={},
                record_evidence={},
                record_profile={},
                is_xexam=False,
                image=image,
            )
            return obs
        else:
            # Semantic模式：原有逻辑
            wait_for_update_conversation = False
            (record_evidence, timestamp) = self.record_evidence_lodder.load(
                and_delete=True)
            if record_evidence != {}:
                self.last_record_time = timestamp
            (record_profile, _) = self.record_profile_lodder.load(
                and_delete=True)

            conversation = self.conversation_lodder.load(
                wait_for_update=wait_for_update_conversation)
            self.last_conversation_str = format_conversation_entry(conversation[-1], is_latest=False, only_text=True)
            self.is_xexam = "color=#00f000" in self.last_conversation_str
            print("[get_current_obs] is_xexam:", self.is_xexam)
            print("[get_current_obs] last_conversation_str:", self.last_conversation_str)

            # if wait_for_update and record_evidence:
            #     wait_for_update_conversation = False
            obs = PwaatObs(
                ARROW_FLAG=self.ARROW_FLAG_checker.exists(),
                active_keytype=self.get_active_keytype(wait_for_update=wait_for_update),
                conversation=conversation,
                last_conversation_str=self.last_conversation_str,
                conversation_history_len=self.conversation_history_len,
                multi_choice=self.multi_choice_lodder.load(and_delete=True),
                record_evidence=record_evidence,
                record_profile=record_profile,
                is_xexam=self.is_xexam,
            )
            
            # parse obs
            obs_result = obs.parse_obs()
            
            # Unpack observation results with descriptive variable names
            self.current_task = obs_result[0]          # Current task type
            self.current_option_list = obs_result[1]    # List of available options
            self.current_option_dict = obs_result[2]    # Dictionary of options
            if obs_result[3] != "":                      # Evidence record string
                self.last_record_evidence = obs_result[3]
            if obs_result[4]  != "":                     # Profile record string
                self.last_record_profile = obs_result[4]
            if self.use_image:
                if self.current_task == GENERAL:
                    if record_evidence != {}:
                        time.sleep(0.5)
                    else:
                        while not self.ARROW_FLAG_checker.exists():
                            time.sleep(0.1)
                else:
                    time.sleep(1)
                obs.image = self.window_capture.capture(log_path=self.log_path)

            return obs

    def _open_tab(self):
        self.auto_input_creator.create_file("R:GetKeyDown")
        time.sleep(1)

    def _close_tab(self):
        while not (self.ARROW_FLAG_checker.exists() and "Start" in self.get_active_keytype(wait_for_update=False)):
            self.auto_input_creator.create_file("R:GetKeyDown")
            time.sleep(1)

    def _access_court_record(self):
        self._open_tab()
        self._close_tab()

    def _move_and_load_savedfile(self):
        # 1) current_idx 파일이 나올 때까지 대기
        while not self.current_savepage_index_lodder.exists():
            if "Start" in self.get_active_keytype(wait_for_update=False):
                self.auto_input_creator.create_file("Start:GetKeyDown")
                time.sleep(0.5)
                current_cursor = self.option_cursor_lodder.load(and_delete=True)
                # print(f"Loaded current_cursor = {current_cursor}")
                if current_cursor == "Save":
                    self.auto_input_creator.create_file("Right:GetKeyDown")
                    time.sleep(0.5)
                self.auto_input_creator.create_file("A:GetKeyDown")
                time.sleep(1.5)
            else:
                self.auto_input_creator.create_file("R:GetKeyDown")
                time.sleep(1)
        
        target_idx = self.savedfile_idx
        # print(f"Target idx = {target_idx}")

        # 2) 파일이 있으면 한 번만 로드
        current_idx = self.current_savepage_index_lodder.load(and_delete=True)
        # print(f"Loaded current_idx = {current_idx}")

        # 3) 새로운 인덱스 변수 초기화
        new_idx = current_idx

        # 4) 목표에 도달할 때까지 Up/Down 키 생성
        while new_idx != target_idx:
            delta = target_idx - new_idx
            # print(f"Moving cursor, delta = {delta}")
            if delta > 0:
                for _ in range(delta):
                    self.auto_input_creator.create_file("Down:GetKey")
                    time.sleep(0.5)
            elif delta < 0:
                for _ in range(-delta):
                    self.auto_input_creator.create_file("Up:GetKey")
                    time.sleep(0.5)

            # 이동 후 새로 파일이 쓰일 때까지 대기
            while not self.current_savepage_index_lodder.exists():
                time.sleep(0.5)
            new_idx = self.current_savepage_index_lodder.load(and_delete=True)
            # print(f"Loaded new_idx = {new_idx}")

        assert new_idx == target_idx, (
            f"Failed to move to target: expected {target_idx}, got {new_idx}"
        )

        # 5) 대화 로그 복사
        base_dir = os.path.dirname(os.path.abspath(__file__))
        source_file = os.path.normpath(os.path.join(
            base_dir,
            "conversation_log_inputs",
            self.task,
            "conversation_log_input.txt"
        ))
        assert os.path.exists(source_file), f"Conversation log input file not found: {source_file}"
        dest_file = os.path.join(self.state_root_dir, "conversation_log_input.txt")
        shutil.copy2(source_file, dest_file)
        while not os.path.exists(dest_file):
            print("Waiting for conversation log input file ...")
            time.sleep(1)

        # 6) 로드 명령 전송
        for idx, key in enumerate(["A:GetKeyDown", "Left:GetKeyDown", "A:GetKeyDown"]):
            if idx == 1:
                current_cursor = self.confirm_initial_cursor_lodder.load(and_delete=True)
                # print(f"Loaded current_cursor = {current_cursor}")
                if current_cursor == "Yes":
                    continue
            self.auto_input_creator.create_file(key)
            time.sleep(0.5)

        # Update conversation log
        self.ARROW_FLAG_checker.remove()
        time.sleep(1)

        # Prepare court record
        self._access_court_record()

    def initial_obs(self) -> Obs:
        if self.action_mode == "gui":
            # GUI模式：等待游戏初始化后返回截图
            time.sleep(1.0)
            obs = self.get_current_obs(wait_for_update=False)
            return obs
        else:
            # Semantic模式：原有逻辑
            if self.task == "full_game":
                # Full game: 不加载存档，从头开始
                obs = self.get_current_obs(wait_for_update=False)
                return obs
            else:
                # 其他任务：原有逻辑
                if self.auto_savedfile:
                    # while True:
                    #     try:
                    self._move_and_load_savedfile()
                    #         break
                    #     except AssertionError as e:
                    #         print(f"AssertionError in move: {e}. Retrying...")
                    #         time.sleep(1)
                    #     except Exception as e:
                    #         print(f"Unexpected error in move: {e}. Retrying...")
                    #         time.sleep(1)
                    print("Loaded savedfile")
                obs = self.get_current_obs(wait_for_update=False)
                while not check_reward(self.starting_checker, obs.conversation):
                    # 7) 사용한 lodder 파일들 삭제
                    self.ARROW_FLAG_checker.remove()
                    time.sleep(1)
                    obs = self.get_current_obs(wait_for_update=False)

                return obs

    def obs2text(self, obs: Obs) -> str:
        return obs.to_text()

    def parse_action(self, text: str) -> Action:
        if self.action_mode == "gui":
            return self._parse_gui_action(text)
        else:
            return self._parse_semantic_action(text)
    
    def _parse_gui_action(self, text: str) -> PwaatAction:
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
            
            # 坐标转换逻辑 (如果启用)
            if self.cfg.coor_trans:
                width, height = self._get_window_size()
                if gui_actions:
                    for i, gui_act in enumerate(gui_actions):
                        # 转换 X 坐标
                        if "x" in gui_act.parameters:
                            original_x = gui_act.parameters["x"]
                            new_x = transform_coordinate(original_x, width)
                            gui_act.parameters["x"] = new_x
                            logger.info(f"Action {i} X coordinate transformed: {original_x} -> {new_x} (Window Width: {width})")
                        
                        # 转换 Y 坐标
                        if "y" in gui_act.parameters:
                            original_y = gui_act.parameters["y"]
                            new_y = transform_coordinate(original_y, height)
                            gui_act.parameters["y"] = new_y
                            logger.info(f"Action {i} Y coordinate transformed: {original_y} -> {new_y} (Window Height: {height})")
            
            logger.info(f"Parsed {len(gui_actions)} GUI actions")
            return PwaatAction(gui_actions=gui_actions, mode="gui")
        except Exception as e:
            logger.warning(f"Failed to parse GUI action: {e}, text: {text}")
            # 返回一个空操作
            return PwaatAction(gui_actions=[], mode="gui")
    
    def _parse_semantic_action(self, text: str) -> PwaatAction:
        """解析 Semantic 模式的动作（原有逻辑）"""
        auto_input_list = []
        try:
            selected_id = int(text)
        except ValueError:
            if self.current_task == GENERAL:
                return PwaatAction(action_sequence="", mode="semantic")
            else:
                selected_id = -1
                _keys_list = []
                for opt_idx in self.current_option_dict.keys():
                    if str(opt_idx) in text:
                        selected_id = int(opt_idx)
                        break
                    _keys_list.append(opt_idx)
                if selected_id == -1:
                    # random select from _keys_list
                    selected_id = random.choice(_keys_list)
            # selected_id = -1
            # for opt_idx in self.current_option_dict.keys():
            #     if str(opt_idx) in text:
            #         selected_id = int(opt_idx)
            #         break

        _answer = self.current_option_dict[selected_id]
        if self.current_task in [GENERAL]:
            if _answer == "Tab":
                # Click Tab key to access the court record
                self._open_tab()
                # Go back to the conversation
                if self.is_xexam:
                    return PwaatAction(action_sequence="Passed", mode="semantic")
                else:
                    # Load record_evidence and record_profile
                    _ = self._wait_for_obs()
                    self._close_tab()
                    auto_input_list.append(KEYNAME_TO_KEYTYPE["Ok"])
            else:
                auto_input_list.append(KEYNAME_TO_KEYTYPE[_answer])
            if _answer == "Press at the moment of testimony":
                self.last_decisions.append(f"You pressed at \"{self.last_conversation_str}\" during Cross-Examination task.")
        elif self.current_task in [MULTI_CHOICE]:
            self.last_decisions.append(f"You selected \"{_answer}\" at \"{self.last_conversation_str}\" as an answer.")
            for _ in range(selected_id-1):
                auto_input_list.append(KEYNAME_TO_KEYTYPE["Down"])
            auto_input_list.append(KEYNAME_TO_KEYTYPE["Ok"])
        elif self.current_task in [CROSS_EXAMINATION_RECORD]:
            self.last_decisions.append(f"You presented \"{_answer}\" at \"{self.last_conversation_str}\" as a piece of evidence during Cross-Examination task.")
            for _ in range(selected_id-1):
                auto_input_list.append(KEYNAME_TO_KEYTYPE["Right"])
            auto_input_list.append(
                KEYNAME_TO_KEYTYPE["Present the selected evidence"])
        else:
            raise ValueError()

        return PwaatAction(
            action_sequence=PwaatAction.format(
                input_list=auto_input_list, keyfunc_dict=KEYTYPE_TO_KEYFUNC[self.current_task]),
            mode="semantic"
        )

    def _is_title(self, text):
        pattern = r'^(?:<color=[^>]+>)?--\s*(.+?)\s*--(?:</color>)?$'
        return bool(re.match(pattern, text))

    def _wait_for_obs(self) -> Obs:
        # Wait until the ARROW_FLAG file exists.
        while not self.ARROW_FLAG_checker.exists():
            if self.record_evidence_lodder.exists() and self.record_profile_lodder.exists():
                break
            time.sleep(0.1)
        obs = self.get_current_obs()
        return obs

    def _safe_commander(self, action: Action):
        actoin_list = action.to_list()
        for action in actoin_list:
            self.auto_input_creator.create_file(action)
            time.sleep(0.3)

    def step(
        self, action: Action
    ) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        if self.action_mode == "gui":
            return self._step_gui(action)
        else:
            return self._step_semantic(action)
    
    def _step_gui(self, action: PwaatAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """GUI 模式下执行动作"""
        self.current_turn += 1
        
        if action.gui_actions and self.gui_manager and self.game_window:
            for i, gui_action in enumerate(action.gui_actions):
                try:
                    logger.info(f"Executing GUI action {i+1}/{len(action.gui_actions)}: {gui_action}")
                    self.gui_manager.execute(self.game_window, gui_action)
                    # 等待动作执行完成
                    time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Failed to execute GUI action {i+1}: {e}")
            # 所有动作执行完后等待游戏响应
            time.sleep(3.0)  # 每个动作执行后等待3秒
        else:
            logger.warning("No valid GUI actions to execute or GUI manager not initialized")
            time.sleep(3.0)  # 即使没有动作也等待3秒
        
        # 截图获取新状态
        obs = self.get_current_obs(wait_for_update=False)
        
        # GUI模式下暂时不检查奖励（需要OCR或mod支持）
        # 这里可以后续添加基于截图的奖励检测
        return obs, 0, False, False, {}
    
    def _step_semantic(self, action: PwaatAction) -> tuple[Obs, float, bool, bool, dict[str, Any]]:
        """Semantic 模式下执行动作（原有逻辑）"""
        self.current_turn += 1

        if action.is_passed():
            pass
        elif action.is_empty():
            logger.error("\n\n Incorrect action! Pressing 'Ok' anyway ... \n\n")
            self.auto_input_creator.create_file("A:GetKeyDown")
            for _ in range(10):
                if self.ARROW_FLAG_checker.exists():
                    time.sleep(0.3)
                else:
                    break
        else:
            self._safe_commander(action)
            for _ in range(10):
                if self.ARROW_FLAG_checker.exists():
                    time.sleep(0.3)
                else:
                    break
        
        # 每个动作执行后等待3秒
        time.sleep(3.0)
        
        while True:
            obs = self._wait_for_obs() if not action.is_passed() else self.get_current_obs()
            if len(obs.conversation[-1]) > 0:
                break
            print("Waiting for conversation ...")
            time.sleep(0.3)
        if self._is_title(obs.conversation[-1]["conversation"]):
            # TODO: testimony 읽어서 전략 세워서 해당하는 전략 수행.
            self.auto_input_creator.create_file("A:GetKeyDown")
            while self.ARROW_FLAG_checker.exists():
                time.sleep(0.3)
            obs = self._wait_for_obs()

        # Full game task: 不检查特定奖励，只根据步数或手动终止
        if self.task == "full_game":
            # Full game模式下，done状态由max_steps控制，不检查特定对话
            return obs, 0, False, False, {}
        else:
            # 其他任务：原有逻辑
            if check_reward(self.reward_checker, obs.conversation):
                self.reward += 1
            if check_reward(self.ending_checker, obs.conversation) or check_reward(self.fail_checker, obs.conversation):
                self.done = True

            return obs, self.reward, self.done, False, {}

    def evaluate(self, obs: Obs):
        if self.auto_savedfile:
            # Create autorun directory and save copy of final_score.json
            autorun_dir = os.path.join("logs", "autorun")
            os.makedirs(autorun_dir, exist_ok=True)
            autorun_path = os.path.join(autorun_dir, f"final_score_{os.path.basename(self.log_path)}.json")
            result = {
                "score": self.reward,
                "final_step": self.current_turn
            }
            with open(autorun_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
        return self.reward, self.done

    def get_game_info(self) -> dict:
        if self.action_mode == "gui":
            # GUI模式：返回任务描述和窗口大小等信息
            task_description = self._get_task_description()
            window_width, window_height = self._get_window_size()
            return {
                "task_description": task_description,
                "window_width": window_width,
                "window_height": window_height,
            }
        else:
            # Semantic模式：原有逻辑
            game_info = {
                "prev_state_str": None,
                "possible_options": POSSIBLE_OPTIONS[self.current_task].format(option_list=self.current_option_list),
                "last_record": None,
                "analysis": None,
                "retrieved_memory_str": None,
                "latest_saved_memory_str": None,
                "last_decisions": "\n".join(
                        f"{i + 1}: {decision}" for i, decision in enumerate(self.last_decisions[-5:])
                    ) if self.last_decisions else None,
            }
            if self.last_record_time != "":
                game_info.update({
                    "last_record": LAST_RECORD_TEMPLATES.format(
                        timestamp=self.last_record_time,
                        record_evidence=self.last_record_evidence,
                        record_profile=self.last_record_profile if self.current_task != CROSS_EXAMINATION_RECORD else "None"
                    )
                })
            return game_info
