# -*- coding: utf-8 -*-
"""
Orak项目 - MCP代理服务器基础实现
===============================

这个模块实现了基于MCP (Model Context Protocol) 的代理服务器。
主要功能包括：
1. 提供MCP工具接口，供客户端调用
2. 管理代理的记忆和技能
3. 处理多模态输入（文本+图像）
4. 支持多种代理模块类型

作者: KRAFTON AI Research Team
"""

import importlib
import sys
import os
import json
from datetime import datetime
import omegaconf
import logging
import base64
from PIL import Image
from io import BytesIO
from typing import Dict, Optional
from dataclasses import field

from agent_servers.memory import GenericMemory
from agent_servers.skill_manager import SkillManager
from agent_servers.reflection_manager import ReflectionManager
from agent_servers.agent_types import AGENT_MODULES, GUI_AGENT_MODULES
from agent_servers.memory_utils import parse_game_state, get_map_memory_dict, replace_filtered_screen_text, replace_map_on_screen_with_full_map

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

logger = logging.getLogger(__name__)

# 代理模块输出格式的前缀定义
# 用于解析LLM响应中的结构化内容
PREFIXS = {
    "self_reflection": {
        "self_reflection": "### Self_reflection", # 自我反思 - Stardew Valley
        "self_reflection_summary": "### Self_reflection_summary", # 自我反思总结 - Stardew Valley
        "critique": "### Critique", # 批评分析 - Minecraft
        "success": "### Success", # 成功状态 - Minecraft
        "analysis": "### Analysis", # 分析结果 - Pwaat
    },
    "knowledge_retrieval": {
        "knowledge": "### Knowledge" # 知识检索 - Minecraft
    },
    "subtask_planning": {
        "history_summary": "### History_summary", # 历史总结 - Stardew Valley
        "subtask_reasoning": "### Subtask_reasoning", # 子任务推理 - Stardew Valley
        "subtask_description": "### Subtask", # 子任务描述 - Stardew Valley, Pwaat
        "subtask": "### Next_subtask", # 下一个子任务 - Minecraft
    },
    "skill_management": {
        "skill_description": "### Skill_description", # 技能描述 - Minecraft
        "retrieved_skills": "### Skill_retrieval" # 检索到的技能 - Minecraft (未使用，用于本地记忆更新)
    },
    "long_term_management": {
        "clue_extraction": "### Clue_Extraction", # 线索提取 - Pwaat
        "saving": "### Saving" # 保存状态 - Pwaat
    },
    "history_summarization":{
        "short_term_summary": "### Short_term_summary", # 短期总结 - Pokemon
    },
    "memory_management":{
        "relevant_memory": "", # 相关记忆 - Pokemon
    },
    "action_execution":{
        "short_term_history": "" # 短期历史 - Pokemon
    },
    "action_inference": {
        "action": "### Actions", # 动作 - 所有游戏
        "reasoning": "### Reasoning", # 推理过程 - Pwaat, GUI模式
        "action_reasoning": "### Action_reasoning", # 动作推理 - Pokemon
        "lessons_learned": "### Lessons_learned", # 学到的经验 - Pokemon
        "state_summary": "### State_summary", # 状态总结 - Pokemon
    },
    "action_inference_with_memory": {
        "action": "### Actions", # 动作 - 所有游戏
        "reasoning": "### Reasoning", # 推理过程
        "new_memory": "### New_memory", # 新的长期记忆（可选）
        "should_save": "### Should_save", # 是否应该保存
    },
    "history_review": {
        "history_summary": "### History_summary", # 短期历史总结回顾
    },
    "reasoning": {
        "reasoning": "### Reasoning", # 推理过程
        "plan": "### Plan", # 计划
    },
    "history_review_reasoning": {
        "history_summary": "### History_summary", # 短期历史总结回顾
        "reasoning": "### Reasoning", # 推理过程
        "plan": "### Plan", # 计划
    },
    "long_term_memory_retrieval": {
        "retrieved_memory": "", # 检索到的长期记忆
    },
    "update_short_term_history": {
        "short_term_history": "", # 更新后的短期历史
    },
    "add_long_term_memory_optional": {
        "new_memory": "### New_memory", # 新的长期记忆（可选）
        "should_save": "### Should_save", # 是否应该保存
    }
}

def load_prompt(prompt_path, module):
    module_name = f"{prompt_path}.{module}"
    _module = importlib.import_module(module_name)
    prompt = getattr(_module, "PROMPT")
    return prompt

def _is_line_key_candidate(line, prefixs):
    # Sort the prefixes by length to prevent long prefixes from matching shorter ones
    sorted_prefixes = sorted(prefixs.items(), key=lambda x: -len(x[1]))

    line = line.strip()
    for key, prefix in sorted_prefixes:
        if line.startswith(prefix):
            return True, key
    return False, None

# Parses the semi-formatted text from model response
def parse_semi_formatted_text(text, prefixs):
    lines = text.split("\n")

    lines = [line.rstrip() for line in lines if line.rstrip()]
    result_dict = {}
    current_key = None
    current_value = []

    for line in lines:
        is_key, key_candidate = _is_line_key_candidate(line, prefixs)

        if is_key:
            if current_key:
                result_dict[current_key] = "\n".join(current_value).strip()

            current_key = key_candidate.replace(" ", "_").lower()
            current_value = []
        else:
            line = line.strip()
            current_value.append(line)

    # Process the last key
    result_dict[current_key] = "\n".join(current_value).strip()

    return result_dict

def extract_memory_entries(reflection: str) -> list[str]:
    import re
    """
    Extracts the memory_entries_to_add list from the LLM's ### Self_reflection block.
    """
    # Step 1: Remove markdown code block markers (```json ... ```)
    json_str = re.sub(r"^```json\s*|\s*```$", "", reflection.strip(), flags=re.DOTALL)
    json_str = re.sub(r"^'''json\s*|\s*'''$", "", json_str.strip(), flags=re.DOTALL)
    
    try:
        reflection_json = json.loads(json_str)
        return reflection_json.get("NewFacts", [])
    except:
        return None

def build_memory_query(goal_description: str, current_state_text: str) -> str:
    """
    Generates a memory retrieval query by combining the current goal and relevant context.
    """
    return f"Information related to 'Goal: {goal_description}' based on 'Context: {current_state_text}'"

def process_state_tool_mcp(obs_str: str, memory: GenericMemory) -> str:
    """
    Processes the state tool to refine the observation string.
    """
    map_memory_dict = memory.map_memory_dict
    dialog_buffer = memory.dialog_buffer
    step_count = memory.step_count

    state_dict = parse_game_state(obs_str)
    map_memory_dict = get_map_memory_dict(state_dict, map_memory_dict)
    current_map = state_dict['map_info']['map_name']

    step_count += 1

    if dialog_buffer != []:
        obs_str = replace_filtered_screen_text(obs_str, dialog_buffer)
        dialog_buffer = []

    if state_dict['state'] == 'Field' and current_map in map_memory_dict.keys():
        obs_str = replace_map_on_screen_with_full_map(obs_str, map_memory_dict[current_map]["explored_map"])

    return obs_str, state_dict, map_memory_dict, step_count, dialog_buffer

def agent_get_local_memory(agent, game_info: Optional[list] = None) -> dict:
    local_memory = {}
    if game_info:
        local_memory.update(game_info)

    local_memory["cur_state_str"] = agent.memory.get_last("observation") or ""
    # update every prefix to local_memory
    for _, dict in PREFIXS.items():
        for key in dict:
            if key in local_memory and agent.memory.get_last(key) is None: # To not update "subtask" to None in zeroshot_agent
                continue
            else:
                local_memory[key] = agent.memory.get_last(key)

    if len(agent.memory.get_all("observation")) > 1:
        local_memory["prev_state_str"] = agent.memory.get_all("observation")[-2]
    else:
        local_memory["prev_state_str"] = None
    if len(agent.memory.get_all("image")) > 0:
        local_memory["cur_image"] = agent.memory.get_last("image")
    if len(agent.memory.get_all("image")) > 1:
        local_memory["prev_image"] = agent.memory.get_all("image")[-2]
    if len(agent.memory.get_all("reasoning")) > 0:
        local_memory.update(
            {
                "prev_reasoning_str": agent.memory.get_all("reasoning")[-1],
            }
        )
    if len(agent.memory.get_all("analysis")) > 0:
        local_memory.update(
            {
                "prev_analysis_str": agent.memory.get_all("analysis")[-1],
            }
        )
    
    # 为可能不存在的字段提供默认值，避免KeyError
    if len(agent.memory.get_all("retrieved_memory")) > 0:
        latest_saved_memory_str = "\n".join(
            f"{idx}: {lmem}" for idx, lmem in enumerate(agent.memory.get_all("long_term_memory")[-agent.long_term_memory_len:], start=1)
        )
        if latest_saved_memory_str == "":
            latest_saved_memory_str = None
        local_memory.update(
            {
                "retrieved_memory_str": agent.memory.get_all("retrieved_memory")[-1],
                "latest_saved_memory_str": latest_saved_memory_str
            }
        )
    else:
        # 提供默认值，避免在reasoning模块执行时出现KeyError
        local_memory["retrieved_memory_str"] = "No long-term memory retrieved yet."
        local_memory["latest_saved_memory_str"] = None
    
    # 为其他可能用到的字段提供默认值
    if "history_summary" not in local_memory or local_memory.get("history_summary") is None:
        local_memory["history_summary"] = "No history summary available yet."
    if "reasoning" not in local_memory or local_memory.get("reasoning") is None:
        local_memory["reasoning"] = "No reasoning available yet."
    if "plan" not in local_memory or local_memory.get("plan") is None:
        local_memory["plan"] = "No plan available yet."
    if "action" not in local_memory or local_memory.get("action") is None:
        local_memory["action"] = "No action executed yet."
    if "task_description" not in local_memory:
        local_memory["task_description"] = ""
    
    # 为history_review模块的特殊字段提供默认值
    if "prev_history_summary" not in local_memory:
        local_memory["prev_history_summary"] = "No previous summary."
    if "recent_pairs_count" not in local_memory:
        local_memory["recent_pairs_count"] = 0
    # 为recent_image/action/observation提供默认值
    for i in range(5):
        if f"recent_image_{i}" not in local_memory:
            local_memory[f"recent_image_{i}"] = None
        if f"recent_action_{i}" not in local_memory:
            local_memory[f"recent_action_{i}"] = "None"
        if f"recent_observation_{i}" not in local_memory:
            local_memory[f"recent_observation_{i}"] = "None"
    
    return local_memory

def agent_update_memory(agent, output: dict) -> None:
    for k, v in output.items():
        agent.memory.add(k, v)

def get_module_prompts(agent, obs_cond=False, system_prompt_filename="self_reflection_system", user_prompt_filename="self_reflection_user"):
    if obs_cond:
        if len(agent.memory.get_all("observation")) <= 1:
            return None, None
        assert (
            len(agent.memory.get_all("observation")) > 1
        ), "Need at least 2 observations for agent reflection"

    # Inject reflection (if enabled)
    local_memory_with_reflection = agent.local_memory.copy()
    if hasattr(agent, 'use_reflection') and agent.use_reflection:
        if hasattr(agent, 'reflection_manager') and agent.reflection_manager:
            # Prioritize reflection_file_path specified in config
            reflection_file_path = getattr(agent, 'reflection_file_path', None)
            game_name = getattr(agent, 'game_name', None)
            reflection_format = getattr(agent, 'reflection_format', 'json')
            
            if reflection_file_path:
                # Use specified file path
                reflection_text, metadata = agent.reflection_manager.load_reflection(file_path=reflection_file_path)
            elif game_name:
                # Build path from game name and format
                reflection_text, metadata = agent.reflection_manager.load_reflection(game_name=game_name, format=reflection_format)
            else:
                reflection_text = None
                metadata = None
            
            if reflection_text:
                local_memory_with_reflection['reflection_experience'] = reflection_text
                
                # Log metadata for traceability
                if metadata:
                    log_info = ["Loaded reflection metadata:"]
                    if "failure_video" in metadata:
                        log_info.append(f"  - Source failure video: {metadata['failure_video']}")
                    if "expert_video" in metadata:
                        log_info.append(f"  - Expert video: {metadata['expert_video']}")
                    if "llm_name" in metadata:
                        log_info.append(f"  - Generated by LLM: {metadata['llm_name']}")
                    logger.info("\n".join(log_info))
                else:
                    logger.info("Loaded reflection but no metadata found.")
            else:
                local_memory_with_reflection['reflection_experience'] = "No prior experience available. Play based on the game rules and your strategic reasoning."
        else:
            local_memory_with_reflection['reflection_experience'] = "No prior experience available. Play based on the game rules and your strategic reasoning."
    else:
        local_memory_with_reflection['reflection_experience'] = "No prior experience available. Play based on the game rules and your strategic reasoning."

    system_prompt = load_prompt(agent.prompt_path, system_prompt_filename).format(**local_memory_with_reflection)
    user_prompt = load_prompt(agent.prompt_path, user_prompt_filename).format(**local_memory_with_reflection)
    return system_prompt, user_prompt

def parse_module_response(response, module_type="self_reflection"):
    output = parse_semi_formatted_text(response, PREFIXS[module_type])
    return output

def agent_add_new_skill(agent, output):
    agent.skill_manager.add_new_skill( # FIXME: "last_action" & "last_action_name" should be delivered from the game_info
        skill_name=agent.local_memory.get("last_action_name", None), # from env
        skill=agent.local_memory.get("last_action", None), # from env
        description=output.get("skill_description", None) # from llm
    )

def agent_retrieve_skills(agent):
    return agent.skill_manager.retrieve_skills(agent.local_memory.get("knowledge", None)) # FIXME: "knowledge" prefix should be from knowledge_retrieval

def agent_add_new_long_term_memory(agent, output):
    memory_text = output.get("clue_extraction", "")
    memory_saving = output.get("saving", "No").lower() == "yes"
    if memory_text and memory_saving:
        agent.memory.add_long_term_memory(memory_text)

def agent_retrieve_long_term_memory(agent):
    return agent.memory.retrieve_long_term_memory(agent.local_memory.get("analysis", None))


if sys.platform == 'win32':
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

def set_log_path(cfg, expand_log_path: bool = True) -> omegaconf.omegaconf.DictConfig:
    if expand_log_path:
        log_path = os.path.join(
            cfg.log_path,
            cfg.env_name,
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        cfg.agent.log_path = log_path
        os.makedirs(log_path, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(cfg.log_path, 'agent_server.log')),
            logging.StreamHandler()
        ],
        force=True
    )

    return cfg

class MCPAgentServer:
    """
    MCP代理服务器类
    
    这个类实现了基于MCP协议的代理服务器，提供以下功能：
    1. 注册MCP工具供客户端调用
    2. 管理代理的记忆和技能
    3. 处理多模态输入
    4. 支持多种代理模块类型
    
    主要MCP工具包括：
    - get-memories: 获取代理记忆
    - set-memories: 设置代理记忆
    - add-observation-to-memory: 添加观察到记忆
    - get-agent-module-prompts: 获取代理模块提示词
    - send-agent-module-response: 发送代理模块响应
    """

    def __init__(self, mcp_server: FastMCP, config_path: str, expand_log_path: bool = True):
        """
        初始化MCP代理服务器
        
        Args:
            mcp_server: FastMCP服务器实例
            config_path: 配置文件路径
            expand_log_path: 是否扩展日志路径
        """
        self.cfg = self.create_config(config_path, expand_log_path)
        logger.info(f"config_path: {config_path}")
        self.mcp = mcp_server
        self.register_tools()  # 注册MCP工具

        # 设置代理相关属性
        self.agent_type = self.cfg.agent.agent_type  # 代理类型
        self.prompt_path = self.cfg.agent.prompt_path  # 提示词路径
        self.agent_modules = AGENT_MODULES[self.agent_type]  # 代理模块列表
        
        # 获取embedding配置
        embedding_model = getattr(self.cfg.agent, 'embedding_model', None)
        embedding_config = getattr(self.cfg.agent, 'embedding_config', {}) or {}
        
        self.memory = GenericMemory(
            path=self.cfg.agent.log_path,
            embedding_model=embedding_model,
            embedding_config=embedding_config
        )  # 记忆管理器
        self.skill_manager = SkillManager(
            path=self.cfg.agent.log_path,
            embedding_model=embedding_model,
            embedding_config=embedding_config
        )  # 技能管理器
        self.long_term_memory_len = self.cfg.agent.long_term_memory_len if hasattr(self.cfg.agent, "long_term_memory_len") else None

        # Video reflection related configuration
        self.use_reflection = getattr(self.cfg.agent, "use_reflection", False) if hasattr(self.cfg, "agent") else False
        self.reflection_format = getattr(self.cfg.agent, "reflection_format", "json") if hasattr(self.cfg, "agent") else "json"
        self.reflection_file_path = getattr(self.cfg.agent, "reflection_file_path", None) if hasattr(self.cfg, "agent") else None
        self.game_name = getattr(self.cfg, "env_name", None)
        
        # Initialize ReflectionManager (if video reflection is enabled)
        if self.use_reflection:
            self.reflection_manager = ReflectionManager()
            logger.info(f"Video reflection enabled, format: {self.reflection_format}, game: {self.game_name}")
        else:
            self.reflection_manager = None
            logger.info("Video reflection disabled")

        # 设置临时变量
        self.module_type = None  # 当前模块类型
        self.last_module = None  # 上一个模块

    def image2str(self, image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def str2image(self, img_str):
        img_data = base64.b64decode(img_str)
        loaded_image = Image.open(BytesIO(img_data))
        image = loaded_image.copy()
        loaded_image.close()
        return image

    def create_config(self, config_path: str, expand_log_path: bool) -> omegaconf.omegaconf.DictConfig:
        cfg = omegaconf.OmegaConf.load(config_path)
        cfg = set_log_path(cfg, expand_log_path)
        return cfg

    def register_tools(self):
        @self.mcp.tool(name="list-agent-module-type", description="List the possible agent module type names.")
        def list_agent_module_type() -> str:
            return "The list of the possible agent module tpyes:\n" + "\n".join([module_type for module_type in self.agent_modules])

        @self.mcp.tool(name="get-memories", description="Get the memories from the agent.")
        def get_memories() -> dict:
            # Create a new memories dict excluding image-related keys
            filtered_memories = {}
            for key, value in self.memory.memories.items():
                if 'image' not in key.lower() and 'img' not in key.lower():
                    filtered_memories[key] = value
            return filtered_memories
        
        @self.mcp.tool(name="set-memories", description="Set the memories to the agent.")
        def set_memories(memories: dict) -> str:
            # Filter out image-related keys before setting
            current_memories = self.memory.memories
            filtered_memories = {}
            
            # Keep existing image-related data
            for key, value in current_memories.items():
                if 'image' in key.lower() or 'img' in key.lower():
                    filtered_memories[key] = value
            
            # Add non-image data from new memories
            for key, value in memories.items():
                if 'image' not in key.lower() and 'img' not in key.lower():
                    filtered_memories[key] = value
            
            self.memory.memories = filtered_memories
            return "Memories set"

        @self.mcp.tool(name="load-map-memories", description="Load the map memories from the agent.")
        def load_map_memories() -> dict:
            return {
                "state_dict": self.memory.state_dict,
                "map_memory_dict": self.memory.map_memory_dict,
                "step_count": self.memory.step_count,
                "dialog_buffer": self.memory.dialog_buffer
            }
        
        @self.mcp.tool(name="set-map-memories", description="Set the map memories to the agent.")
        def set_map_memories(map_memories: dict) -> str:
            self.memory.state_dict = map_memories["state_dict"]
            self.memory.map_memory_dict = map_memories["map_memory_dict"]
            self.memory.step_count = map_memories["step_count"]
            self.memory.dialog_buffer = map_memories["dialog_buffer"]
            return "Map memories set"
        
        @self.mcp.tool(name="add-long-term-memory", description="Add a long term memory to the agent.")
        def add_long_term_memory(memory: str, threshold: float) -> str:
            self.memory.add_long_term_memory(memory, threshold)
            return "Long term memory added"

        @self.mcp.tool(name="add-observation-to-memory", description="Add a observation to the agent.")
        def add_observation_to_memory(obs_str: str, obs_image_str: str) -> str:
            if "Pokemon" in self.cfg.env_name:
                obs_str, self.memory.state_dict, self.memory.map_memory_dict, self.memory.step_count, self.memory.dialog_buffer = process_state_tool_mcp(
                    obs_str, self.memory
                )

            self.memory.add("observation", obs_str)
            if obs_image_str!= "":
                obs_image = self.str2image(obs_image_str)
                self.memory.add("image", obs_image)
            return "Observation added"

        @self.mcp.tool(name="get-agent-module-prompts", description="Get an agent module named module_type and return its system and user prompts to response.")
        def get_agent_module_prompts(module_type: str, game_info: dict) -> str:
            #logger.info(f"[DEBUG] get_agent_module_prompts(), module_type: {self.module_type}")

            self.module_type = module_type
            self.local_memory = agent_get_local_memory(self, game_info)
            call_chat_completion = True
            if self.module_type == "action_inference":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "action_inference_system", "action_inference_user")
            elif self.module_type == "skill_management":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "skill_management_system", "skill_management_user")
                # add a new skill if the previous subtask succeeds
                # TODO: to handle general prefixs
                if not ("true" in str(self.local_memory.get("success", "")).lower()):
                    call_chat_completion = False
            elif self.module_type == "subtask_planning":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "subtask_planning_system", "subtask_planning_user")
            elif self.module_type == "knowledge_retrieval":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "knowledge_retrieval_system", "knowledge_retrieval_user")
            elif self.module_type == "self_reflection":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "self_reflection_system", "self_reflection_user")
            elif self.module_type == "long_term_management":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "long_term_system", "long_term_user")
            elif self.module_type == "history_summarization":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "history_summarization_system", "history_summarization_user")
            elif self.module_type == "history_review":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "history_review_system", "history_review_user")
            elif self.module_type == "reasoning":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "reasoning_system", "reasoning_user")
            elif self.module_type == "history_review_reasoning":
                system_prompt, user_prompt = get_module_prompts(
                    self, True, "history_review_reasoning_system", "history_review_reasoning_user")
            elif self.module_type == "action_inference_with_memory":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "action_inference_with_memory_system", "action_inference_with_memory_user")
            elif self.module_type == "add_long_term_memory_optional":
                system_prompt, user_prompt = get_module_prompts(
                    self, False, "add_long_term_memory_system", "add_long_term_memory_user")
            elif self.module_type == "memory_management" or self.module_type == "action_execution" or self.module_type == "long_term_memory_retrieval" or self.module_type == "update_short_term_history":
                system_prompt, user_prompt = "", ""
                call_chat_completion = False
            else:
                raise ValueError(f"Unknown module: {self.module_type}")
            
            image_strs = {k: self.image2str(self.local_memory[k]) for k in ("cur_image", "prev_image") if k in self.local_memory}
            
            return json.dumps({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "image_strs": image_strs,
                "call_chat_completion": call_chat_completion
            })

        def _parse_module_response(response, module_type, structured_output_kwargs):
            if "guided_json" in structured_output_kwargs:
                output = json.loads(response)
                output = {key: value for key, value in output.items() if key in structured_output_kwargs["output_keys"]}
            else:
                output = parse_module_response(response, module_type)
            return output

        @self.mcp.tool(name="send-agent-module-response", description="Send a client response for the current agent module and return its parsed output.")
        def send_agent_module_response(response: str, structured_output_kwargs: dict) -> str:
            #logger.info(f"[DEBUG] send_agent_module_response(), module_type: {self.module_type}")

            if "\\n" in response:
                response = response.replace("\\n", "\n")
            if self.module_type == "action_inference":
                output = _parse_module_response(response, "action_inference", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output.get("action", None)
            elif self.module_type == "skill_management":
                if response is not None:
                    output = _parse_module_response(response, "skill_management", structured_output_kwargs)
                    agent_update_memory(self, output)
                    agent_add_new_skill(self, output)
                skills_text = agent_retrieve_skills(self)
                output = {"retrieved_skills": skills_text}
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "subtask_planning":
                output = _parse_module_response(response, "subtask_planning", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "knowledge_retrieval":
                output = _parse_module_response(response, "knowledge_retrieval", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "self_reflection":
                output = _parse_module_response(response, "self_reflection", structured_output_kwargs)
                for key in PREFIXS["self_reflection"]:
                    if key not in output:
                        output[key] = None
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "long_term_management":
                output = _parse_module_response(response, "long_term_management", structured_output_kwargs)
                agent_update_memory(self, output)
                agent_add_new_long_term_memory(self, output)
                retrieved_memory = agent_retrieve_long_term_memory(self)
                output = {"retrieved_memory": retrieved_memory}
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "history_summarization":
                output = _parse_module_response(response, "history_summarization", structured_output_kwargs)

                action_memory = self.memory.get_all("action")
                output['short_term_summary'] += f"\nExecuted Action Sequence: (oldest)[{'->'.join(map(str, action_memory[-self.memory.num_action_buffer:]))}](latest)" if action_memory else None
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "memory_management":
                import re
                goal = self.memory.get_last("subtask_description")
                query = None

                state_dict = self.memory.state_dict
                cur_state = state_dict['state']
                if cur_state == "Title":
                    environment_perception = f"State:{cur_state}"
                elif cur_state == "Field":
                    map_info = state_dict['map_info']
                    environment_perception = f"State:{cur_state}, MapName:{map_info['map_name']}, PlayerPos:({map_info['player_pos_x']},{map_info['player_pos_y']})"
                elif cur_state == 'Dialog':
                    environment_perception = f"State:{cur_state}, ScreenText:{state_dict['filtered_screen_text']}"
                else:
                    environment_perception = f"State:{cur_state}, Enemy:{state_dict['enemy_pokemon']}, Party:{state_dict['your_party']}"

                self.memory.add('environment_perception', environment_perception)

                if self.memory.is_exist('self_reflection'):
                    try:
                        reflection_data_str = self.memory.get_last('self_reflection').strip()
                        json_str = re.sub(r"^```json\s*|\s*```$", "", reflection_data_str, flags=re.DOTALL)
                        reflection_json = json.loads(json_str)

                        if 'Goal' in reflection_json:
                            goal = str(reflection_json['Goal'])
                        else:
                            goal = 'Not Provided from reflection'

                        # self.memory.environment_perception = reflection_json.get("Env", [])
                    except (json.JSONDecodeError, AttributeError, TypeError) as e:
                        print(f"Error processing self_reflection: {e}")
                        print("Use default goal and environment_perception.")
                    
                    if 'self_reflection' == self.last_module:  # LTM Managing
                        try:
                            memory_entries = extract_memory_entries(self.memory.get_last('self_reflection'))
                            if memory_entries:
                                for entry in memory_entries:
                                    self.memory.add_long_term_memory(entry, similarity_threshold=0.2)
                        except Exception as e:
                            print(f"Error adding long term memory: {e}")
                    else:
                        goal = self.memory.get_last('subtask_description')

                query = build_memory_query(goal, self.memory.get_last('environment_perception'))
                try:
                    memory_snippets = self.memory.retrieve_long_term_memory(query, similarity_threshold=0.4)
                    self.memory.add('relevant_memory', memory_snippets or None)
                    parsed_output = self.memory.get_last('relevant_memory')
                except Exception as e:
                    logger.error(f"Error retrieving long term memory: {e}")
                    # Return empty memory if retrieval fails
                    self.memory.add('relevant_memory', None)
                    parsed_output = None
            elif self.module_type == "action_execution":
                # Pop the last action from the action memory
                action_str = self.memory.get_last('action')
                self.memory.memories['action'] = self.memory.memories['action'][:-1]
                parsed_output = action_str
            elif self.module_type == "history_review":
                output = _parse_module_response(response, "history_review", structured_output_kwargs)
                for key in PREFIXS["history_review"]:
                    if key not in output:
                        output[key] = None
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "reasoning":
                output = _parse_module_response(response, "reasoning", structured_output_kwargs)
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "history_review_reasoning":
                output = _parse_module_response(response, "history_review_reasoning", structured_output_kwargs)
                for key in PREFIXS["history_review_reasoning"]:
                    if key not in output:
                        output[key] = None
                agent_update_memory(self, output)
                parsed_output = output
            elif self.module_type == "action_inference_with_memory":
                output = _parse_module_response(response, "action_inference_with_memory", structured_output_kwargs)
                agent_update_memory(self, output)
                
                # 如果should_save为"Yes"，则添加长期记忆
                should_save = output.get("should_save", "No")
                new_memory = output.get("new_memory", None)
                
                if should_save and should_save.lower() in ["yes", "true", "1"] and new_memory and new_memory.lower() != "none":
                    try:
                        self.memory.add_long_term_memory(new_memory, similarity_threshold=0.8)
                        logger.info(f"Added new long-term memory: {new_memory[:100]}...")
                    except Exception as e:
                        logger.error(f"Error adding long-term memory: {e}")
                
                parsed_output = output.get("action", None)
            elif self.module_type == "long_term_memory_retrieval":
                # 构建查询：基于当前观测、历史总结和推理结果
                cur_state = self.memory.get_last('observation')
                history_summary = self.memory.get_last('history_summary')
                reasoning = self.memory.get_last('reasoning')
                
                query_parts = []
                if cur_state:
                    query_parts.append(f"Current state: {cur_state[:200]}")
                if history_summary:
                    query_parts.append(f"History context: {history_summary[:200]}")
                if reasoning:
                    query_parts.append(f"Reasoning: {reasoning[:200]}")
                
                query = " ".join(query_parts) if query_parts else None
                
                try:
                    memory_snippets = self.memory.retrieve_long_term_memory(query, similarity_threshold=0.4)
                    self.memory.add('retrieved_memory', memory_snippets or None)
                    parsed_output = memory_snippets or None
                except Exception as e:
                    logger.error(f"Error retrieving long term memory: {e}")
                    self.memory.add('retrieved_memory', None)
                    parsed_output = None
            elif self.module_type == "update_short_term_history":
                # 获取当前状态和动作
                cur_state = self.memory.get_last('observation')
                action = self.memory.get_last('action')
                
                # 更新step_count
                if not hasattr(self.memory, 'step_count'):
                    self.memory.step_count = 0
                self.memory.step_count += 1
                
                # 构建历史条目
                history_entry = {
                    f"step_{self.memory.step_count}_state": cur_state,
                    f"step_{self.memory.step_count}_action": action,
                }
                
                # 添加推理和记忆信息（如果有）
                reasoning = self.memory.get_last('reasoning')
                if reasoning:
                    history_entry[f"step_{self.memory.step_count}_reasoning"] = reasoning
                
                retrieved_memory = self.memory.get_last('retrieved_memory')
                if retrieved_memory:
                    history_entry[f"step_{self.memory.step_count}_retrieved_memory"] = retrieved_memory[:500]
                
                # 添加到历史列表
                if not hasattr(self.memory, 'histories'):
                    self.memory.histories = []
                
                self.memory.histories.append(history_entry)
                
                # 保持历史列表在合理大小
                if not hasattr(self.memory, 'num_history_buffer'):
                    self.memory.num_history_buffer = 20
                self.memory.histories = self.memory.histories[-self.memory.num_history_buffer:]
                
                # 更新短期历史到memory
                self.memory.add('short_term_history', self.memory.histories)
                parsed_output = self.memory.histories
            elif self.module_type == "add_long_term_memory_optional":
                output = _parse_module_response(response, "add_long_term_memory_optional", structured_output_kwargs)
                agent_update_memory(self, output)
                
                # 如果should_save为"Yes"，则添加长期记忆
                should_save = output.get("should_save", "No")
                new_memory = output.get("new_memory", None)
                
                if should_save and should_save.lower() in ["yes", "true", "1"] and new_memory:
                    try:
                        self.memory.add_long_term_memory(new_memory, similarity_threshold=0.8)
                        logger.info(f"Added new long-term memory: {new_memory[:100]}...")
                    except Exception as e:
                        logger.error(f"Error adding long-term memory: {e}")
                
                parsed_output = output
            else:
                raise ValueError(f"Unknown module: {self.module_type}")
            
            self.last_module = self.module_type

            return json.dumps({
                "parsed_output": str(parsed_output),
            })

    async def run(self):
        await self.mcp.run_stdio_async()
