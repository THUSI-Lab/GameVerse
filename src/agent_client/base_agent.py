import importlib
import os
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Union, Any
# 添加logger
import logging
from omegaconf import DictConfig

logger = logging.getLogger(__name__)

from agent_client.llms.llm import load_model, LocalBase
from agent_client.llms.openai_utils import (
    Logger,
    MoneyManager,
    pretty_print_conversation,
)
from agent_client.json_schemas import SCHEMA_REGISTRY

from game_servers.utils.types.misc import Configurable

from agent_servers.base_server import (
    PREFIXS,
    AGENT_MODULES,
    GUI_AGENT_MODULES,
    GenericMemory,
    SkillManager,
    agent_get_local_memory,
    get_module_prompts,
    parse_module_response,
    agent_update_memory,
    agent_add_new_long_term_memory,
    agent_retrieve_long_term_memory,
    agent_add_new_skill,
    agent_retrieve_skills
)

from PIL import Image
from io import BytesIO
import re
import base64

# Function to encode PIL.Image.Image to base64
def encode_image(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

class BaseAgent(Configurable):
    @dataclass
    class Config:
        llm_name: str
        temperature: float = 0.0
        repetition_penalty: float = 0.0
        api_key: str = ""
        api_base_url: str = ""

        agent_type: str = "zeroshot_agent"
        prompt_path: str = ""

        log_path: str = "./logs"
        debug_mode: bool = False
        structured_output: Optional[Dict[str, str]] = field(default_factory=dict)
        long_term_memory_len: int = 10
        
        # Embedding model configuration
        embedding_model: Optional[str] = None  # "openai" or "qwen", None defaults to "openai"
        embedding_config: Optional[Dict[str, Any]] = field(default_factory=dict)  # Additional embedding config (model, dimensions, api_key, etc.)
        
        # Video reflection related configuration
        use_reflection: bool = False  # Whether to use video reflection experience
        reflection_format: str = "json"  # Reflection file format: json or txt
        reflection_file_path: Optional[str] = None  # Directly specify reflection file path (takes priority)
        reflection_generation: Optional[Dict[str, Any]] = field(default_factory=dict)  # Video reflection generation configuration

    cfg: Config  # add this to every subclass to enable static type checking

    def configure(self):
        pass

    def __init__(
        self, cfg: Optional[Union[dict, DictConfig]] = None, *args, **kwargs
    ) -> None:
        super().__init__(cfg, *args, **kwargs)

        # default arguments
        self.orig_model = self.cfg.llm_name
        self.temperature = self.cfg.temperature
        self.repetition_penalty = self.cfg.repetition_penalty
        self.api_key = self.cfg.api_key
        self.api_base_url = self.cfg.api_base_url

        self.log_path = self.cfg.log_path
        self.debug_mode = self.cfg.debug_mode

        self.agent_type = self.cfg.agent_type
        self.agent_modules = AGENT_MODULES[self.agent_type]
        self.structured_output = self.cfg.structured_output

        self._setup_model()
        self._setup_logger()

    def _setup_model(self):
        loaded_model = load_model(
            self.orig_model,
            temperature=self.temperature,
            repetition_penalty=self.repetition_penalty,
            api_key=self.api_key,
            api_base_url=self.api_base_url
        )

        self.model_name = loaded_model["model_name"]
        self.ctx_manager: MoneyManager = loaded_model["ctx_manager"]
        self.llm = loaded_model["llm"]
        self.tokenizer = loaded_model["tokenizer"]

    def _setup_logger(self):
        self.logger = Logger(log_path=self.log_path)

    def chat_completion(self, system_prompt, user_prompt, images={}, **kwargs):
        messages = []

        messages.append({"role": "system", "content": system_prompt})

        if images:
            # 支持多种图像标记：cur_state_image, prev_state_image, recent_image_0到recent_image_4
            pattern = r"(<\|cur_state_image\|>|<\|prev_state_image\|>|<\|recent_image_\d+\|>)"
            parts = re.split(pattern, user_prompt)

            user_prompt = []
            for part in parts:
                if part == "<|cur_state_image|>":
                    if "cur_image" not in images:
                        user_prompt.append(
                            {
                                "type": "text",
                                "text": "None",
                            }
                        )
                        continue
                    base64_image = encode_image(images["cur_image"])
                    user_prompt.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                            }
                        }
                    )
                elif part == "<|prev_state_image|>":
                    if "prev_image" not in images:
                        user_prompt.append(
                            {
                                "type": "text",
                                "text": "None",
                            }
                        )
                        continue
                    base64_image = encode_image(images["prev_image"])
                    user_prompt.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                            }
                        }
                    )
                elif part.startswith("<|recent_image_") and part.endswith("|>"):
                    # 提取图像索引，例如 <|recent_image_0|> -> 0
                    match = re.search(r"recent_image_(\d+)", part)
                    if match:
                        idx = int(match.group(1))
                        image_key = f"recent_image_{idx}"
                        if image_key in images and images[image_key] is not None:
                            base64_image = encode_image(images[image_key])
                            user_prompt.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}",
                                    }
                                }
                            )
                        else:
                            user_prompt.append(
                                {
                                    "type": "text",
                                    "text": "None",
                                }
                            )
                else:
                    if part.strip():  # 只添加非空部分
                        user_prompt.append(
                            {
                                "type": "text",
                                "text": part,
                            }
                        )

        messages.append({"role": "user", "content": user_prompt})

        output = self.llm(messages, **kwargs)

        messages.append(
            {
                "content": output["response"].choices[0].message.content,
                "role": output["response"].choices[0].message.role,
            }
        )
        messages.append({"total_cost": self.ctx_manager.total_cost})

        if self.debug_mode:
            pretty_print_conversation(messages)
        self.logger(messages)

        completion = output["response"].choices[0].message.content
        return completion

    def update_parameters(
        self,
        temperature: float | None = None,
        repetition_penalty: float | None = None,
    ) -> None:
        if temperature is not None:
            self.temperature = temperature
        if repetition_penalty is not None:
            self.repetition_penalty = repetition_penalty
        self._setup_model()

    # Return the total cost for calling this agent
    def total_cost(self) -> float:
        return self.ctx_manager.total_cost

    def refresh(self) -> None:
        return self.ctx_manager.refresh()

class BaselineAgent(BaseAgent):
    @dataclass
    class Config:
        llm_name: str
        temperature: float = 0.0
        repetition_penalty: float = 0.0
        api_key: str = ""
        api_base_url: str = ""

        agent_type: str = "zeroshot_agent"
        prompt_path: str = ""

        log_path: str = "./logs"
        debug_mode: bool = False
        structured_output: Optional[Dict[str, str]] = field(default_factory=dict)
        long_term_memory_len: int = 10
        
        # Embedding model configuration
        embedding_model: Optional[str] = None  # "openai" or "qwen", None defaults to "openai"
        embedding_config: Optional[Dict[str, Any]] = field(default_factory=dict)  # Additional embedding config (model, dimensions, api_key, etc.)
        
        # Video reflection related configuration
        use_reflection: bool = False  # Whether to use video reflection experience
        reflection_format: str = "json"  # Reflection file format: json or txt
        reflection_file_path: Optional[str] = None  # Directly specify reflection file path (takes priority)
        reflection_generation: Optional[Dict[str, Any]] = field(default_factory=dict)  # Video reflection generation configuration

    cfg: Config

    def configure(self):
        self.prompt_path = self.cfg.prompt_path
        self.long_term_memory_len = self.cfg.long_term_memory_len

        # 获取embedding配置
        embedding_model = getattr(self.cfg, 'embedding_model', None)
        embedding_config = getattr(self.cfg, 'embedding_config', {}) or {}

        self.memory = GenericMemory(
            path=self.cfg.log_path,
            embedding_model=embedding_model,
            embedding_config=embedding_config
        )
        self.skill_manager = SkillManager(
            path=self.cfg.log_path,
            embedding_model=embedding_model,
            embedding_config=embedding_config
        )
        
        # Initialize reflection manager (if enabled)
        self.use_reflection = self.cfg.use_reflection
        self.reflection_format = self.cfg.reflection_format
        self.reflection_file_path = getattr(self.cfg, 'reflection_file_path', None)
        if self.use_reflection:
            from agent_servers.reflection_manager import ReflectionManager
            self.reflection_manager = ReflectionManager()
        else:
            self.reflection_manager = None
        
        self.modality = self.cfg.prompt_path.split('.')[-1]
        self.agent_type = self.cfg.agent_type
        self.toolset = None
        self.last_module = ""
        
        # Default to action_inference modules
        self.agent_modules = AGENT_MODULES[self.agent_type]

    def set_env_interface(self, env):
        self.env = env
        # Update agent_modules based on env's action_mode
        if hasattr(env, 'action_mode') and env.action_mode == "gui":
            if self.agent_type in GUI_AGENT_MODULES:
                self.agent_modules = GUI_AGENT_MODULES[self.agent_type]
                logger.info(f"Using GUI mode modules: {self.agent_modules}")
        
        # Set game name (for reflection management)
        if hasattr(env, 'cfg') and hasattr(env.cfg, 'env_name'):
            self.game_name = env.cfg.env_name
        elif hasattr(env, 'env_name'):
            self.game_name = env.env_name
        else:
            self.game_name = None

    def module2func(self, module):
        if module == "action_inference":
            return self.action_inference
        elif module == "skill_management":
            return self.skill_management
        elif module == "subtask_planning":
            return self.subtask_planning
        elif module == "knowledge_retrieval":
            return self.knowledge_retrieval
        elif module == "self_reflection":
            return self.self_reflection
        elif module == "long_term_management":
            return self.long_term_management
        elif module == "history_summarization":
            return self.history_summarization
        elif module == "memory_management":
            return self.memory_management
        elif module == "action_execution":
            return self.action_execution
        elif module == "history_review":
            return self.history_review
        elif module == "reasoning":
            return self.reasoning
        elif module == "history_review_reasoning":
            return self.history_review_reasoning
        elif module == "long_term_memory_retrieval":
            return self.long_term_memory_retrieval
        elif module == "update_short_term_history":
            return self.update_short_term_history
        elif module == "add_long_term_memory_optional":
            return self.add_long_term_memory_optional
        elif module == "action_inference_with_memory":
            return self.action_inference_with_memory
        raise ValueError(f"Unknown module: {module}")

    def __call__(self, obs, game_info: Optional[dict] = None) -> str:
        text_obs, image_obs = obs.to_text(), getattr(obs, 'image', None)

        # Update observation to memory
        self.memory.add("observation", text_obs)
        if image_obs is not None:
            self.memory.add("image", image_obs)

        action_result = None  # 保存action_inference的返回值
        for module in self.agent_modules:
            self.local_memory = agent_get_local_memory(self, game_info)

            structured_output_kwargs = {}
            if module in self.structured_output:
                assert isinstance(self.llm, LocalBase), "Structured output is currently tested for local models."

                if "guided_regex" in self.structured_output[module]:
                    structured_output_kwargs.update(self.structured_output[module])
                elif "guided_json" in self.structured_output[module]:
                    json_schema = SCHEMA_REGISTRY[self.structured_output[module]["guided_json"]]
                    structured_output_kwargs.update({"guided_json": json_schema})
                    structured_output_kwargs.update({"output_keys": self.structured_output[module]["output_keys"]})

            result = self.module2func(module)(**structured_output_kwargs)
            self.last_module = module
            
            # 如果是action_inference或action_inference_with_memory模块，保存其返回值
            if module == "action_inference" or module == "action_inference_with_memory":
                action_result = result

        # 如果有action_inference的返回值，返回它；否则返回最后一个模块的返回值
        if action_result is not None:
            return str(action_result)
        else:
            # 如果没有action_inference模块（理论上不应该发生），返回最后一个模块的返回值
            return str(result) if 'result' in locals() else ""

    def self_reflection(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
            self, True, "self_reflection_system", "self_reflection_user")
        if system_prompt is None and user_prompt is None:
            return

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "self_reflection")
        
        for key in PREFIXS["self_reflection"]:
            if key not in output:
                output[key] = None

        agent_update_memory(self, output)

        return output

    def subtask_planning(self, **kwargs):
        
        system_prompt, user_prompt = get_module_prompts(
            self, False, "subtask_planning_system", "subtask_planning_user")

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "subtask_planning")

        agent_update_memory(self, output)

        return output
    
    def knowledge_retrieval(self, **kwargs):
        
        system_prompt, user_prompt = get_module_prompts(
            self, False, "knowledge_retrieval_system", "knowledge_retrieval_user")

        response = self.chat_completion(system_prompt, user_prompt)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "knowledge_retrieval")

        agent_update_memory(self, output)

        return output

    def skill_management(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "skill_management_system", "skill_management_user")
        if system_prompt is None and user_prompt is None:
            return

        # add new skills if the "previous" subtask succeeds
        # TODO: to handle general prefixs
        if "true" in str(self.local_memory.get("success", "")).lower(): # FIXME: "success" prefix should be from self_reflection
            response = self.chat_completion(system_prompt, user_prompt)
            output = parse_module_response(response, "skill_management")
            agent_update_memory(self, output)

            agent_add_new_skill(self, output)

        # retrieve skills based on the "current" subtask
        skills_text = agent_retrieve_skills(self) # FIXME: "knowledge" prefix should be from knowledge_retrieval
        output = {"retrieved_skills": skills_text}

        agent_update_memory(self, output)

        return output

    def long_term_management(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "long_term_system", "long_term_user")
        if system_prompt is None and user_prompt is None:
            return

        response = self.chat_completion(system_prompt, user_prompt)
        output = parse_module_response(response, "long_term_management")
        agent_update_memory(self, output)

        agent_add_new_long_term_memory(self, output)

        retrieved_memory = agent_retrieve_long_term_memory(self)
        output = {"retrieved_memory": retrieved_memory}
        agent_update_memory(self, output)

        return output

    def action_inference(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, False, "action_inference_system", "action_inference_user")
        
        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "action_inference")

        agent_update_memory(self, output)

        return output.get("action", None)
    
    def action_inference_with_memory(self, **kwargs):
        """
        合并的动作推理和长期记忆保存模块
        在一个VLM调用中完成动作推理，并在输出动作后决定是否保存长期记忆
        """
        system_prompt, user_prompt = get_module_prompts(
                self, False, "action_inference_with_memory_system", "action_inference_with_memory_user")
        
        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "action_inference_with_memory")

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

        return output.get("action", None)
    
    def history_summarization(self, **kwargs):
        system_prompt, user_prompt = get_module_prompts(
                self, True, "history_summarization_system", "history_summarization_user")
        if system_prompt is None and user_prompt is None:
            return

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "history_summarization")
        
        for key in PREFIXS["history_summarization"]:
            if key not in output:
                output[key] = None

        action_memory = self.memory.get_all('action')
        output['short_term_summary'] += f"\nExecuted Action Sequence: (oldest)[{'->'.join(map(str, action_memory[-self.memory.num_action_buffer:]))}](latest)" if action_memory else None

        agent_update_memory(self, output)

        return output
    
    def memory_management(self, **kwargs):
        print('Memory Managing...')
        goal = self.memory.get_last('subtask_decription')
        query = None
        
        # default environment_perception
        state_dict = self.memory.state_dict
        cur_state = state_dict['state']
        if cur_state == 'Title':
            self.memory.environment_perception = f"State:{cur_state}"
        elif cur_state == 'Field':
            map_info = state_dict['map_info']
            self.memory.environment_perception = f"State:{cur_state}, MapName:{map_info['map_name']}, PlayerPos:({map_info['player_pos_x']},{map_info['player_pos_y']})"
        elif cur_state == 'Dialog':
            self.memory.environment_perception = f"State:{cur_state}, ScreenText:{state_dict['filtered_screen_text']}"
        else:
            self.memory.environment_perception = f"State:{cur_state}, Enemy:{state_dict['enemy_pokemon']}, Party:{state_dict['your_party']}"

        if self.memory.is_exist('self_reflection'):
            try:
                reflection_data_str = self.memory.get_last('self_reflection').strip()
                json_str = re.sub(r"^```json\s*|\s*```$", "", reflection_data_str, flags=re.DOTALL)
                reflection_json = json.loads(json_str)

                if 'Goal' in reflection_json:
                    goal = str(reflection_json['Goal'])
                else:
                    goal = 'Not Provided from reflection'

            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                print(f"Error processing self_reflection: {e}")
                print("Use default goal and environment_perception.")
            
            goal = self.memory.get_last('subtask_decription')

        query = None

        memory_snippets = self.memory.retrieve_long_term_memory(query, similarity_threshold=0.4)

        self.memory.add('relevant_memory', memory_snippets or None)

        return self.memory.get_last('relevant_memory')
    
    def action_execution(self, **kwargs):
        action_response = self.memory.get_last('action')
        action_response = action_response.split('\n')[0]
        actions = [part.strip() for part in re.split(r'\s*(\||\n)\s*', action_response) if part.strip() and part.strip() not in ('|', '\n')]
        actions = actions[:5]
        messages = []
        flag = ''
            
        for action_idx, action in enumerate(actions):
            if action_idx==0:
                if 'use_tool' in action:
                    break
                else:
                    messages.append(action)
                    flag = 'low'
            else:
                if 'use_tool' in action:
                    break
                else:
                    messages.append(action)
        final_action = "|".join(messages)
        self.memory.add('action', final_action)

        # Managing History
        data = {
            f"{self.memory.step_count}th_state": self.memory.environment_perception,
            f"{self.memory.step_count}th_action": self.memory.get_last('action'),
        }
        self.memory.histories.append(data)
        self.memory.histories = self.memory.histories[-self.memory.num_history_buffer:]
        self.memory.add('short_term_history', self.memory.histories)

        # update long-term memory
        lessons = self.memory.get_last('lessons_learned')
        if lessons and lessons != "Not Provided":
            lessons_list = lessons.split('\n')
            for lesson in lessons_list:
                lesson = lesson.strip()
                lesson_match = re.match(r"^\s*[-*]\s*(.*)", lesson)
                if lesson_match:
                    lesson_text = lesson_match.group(1).strip()
                    if lesson_text:
                        self.memory.add_long_term_memory(lesson_text, similarity_threshold=0.2)
                elif lesson:
                    self.memory.add_long_term_memory(lesson, similarity_threshold=0.2)

        return final_action
    
    def history_review(self, **kwargs):
        """
        短期历史总结回顾模块
        对短期历史进行总结回顾，提取关键信息
        要求：处理最近5个image+action对，基于上一段短期记忆总结生成新的总结
        """
        # 先获取最近5个image+action对和上一段总结，设置到local_memory中
        # 这样在调用get_module_prompts时，这些字段就已经可用了
        
        # 获取历史image+action对（排除当前的image，因为当前image还没有对应的action）
        all_images = self.memory.get_all('image')
        all_actions = self.memory.get_all('action')
        all_observations = self.memory.get_all('observation')
        
        # 排除当前的image（最后一个），因为当前image还没有对应的action
        # history_review应该只处理已经完成的image+action对
        historical_images = all_images[:-1] if len(all_images) > 0 else []
        historical_actions = all_actions  # actions都是历史的，因为当前还没有执行action
        historical_observations = all_observations[:-1] if len(all_observations) > 0 else []
        
        # 获取上一段短期记忆总结
        prev_history_summary = self.memory.get_last('history_summary')
        
        # 构建最近5个历史image+action对（不包含当前的image）
        recent_pairs = []
        num_pairs = min(5, len(historical_images), len(historical_actions))
        
        for i in range(num_pairs):
            idx = -(num_pairs - i)  # 从最远到最近
            pair = {
                'image': historical_images[idx] if idx < 0 else None,
                'action': historical_actions[idx] if idx < 0 else None,
                'observation': historical_observations[idx] if idx < 0 and idx < len(historical_observations) else None,
                'step': len(historical_images) + idx + 1
            }
            if pair['image'] is not None or pair['action'] is not None:
                recent_pairs.append(pair)
        
        # 先获取基础的local_memory（包含cur_state_str等基础字段）
        # 然后在此基础上添加history_review特有的字段
        from agent_servers.base_server import agent_get_local_memory
        self.local_memory = agent_get_local_memory(self, None)
        
        # 将最近5个图像添加到local_memory中，供prompt使用
        # 注意：recent_pairs是从最远到最近排序的，我们需要取最后5个（即最近的5个）
        recent_pairs_for_prompt = recent_pairs[-5:] if len(recent_pairs) >= 5 else recent_pairs
        for i in range(5):
            if i < len(recent_pairs_for_prompt):
                pair = recent_pairs_for_prompt[i]
                if pair and pair.get('image') is not None:
                    self.local_memory[f"recent_image_{i}"] = pair['image']
                    # 转义action中的大括号，避免.format()时出错
                    action_str = str(pair.get('action', 'None'))
                    action_str = action_str.replace('{', '{{').replace('}', '}}')
                    self.local_memory[f"recent_action_{i}"] = action_str
                    # 转义observation中的大括号
                    obs_str = (pair.get('observation') or 'None')[:200] if pair.get('observation') else 'None'
                    obs_str = str(obs_str).replace('{', '{{').replace('}', '}}')
                    self.local_memory[f"recent_observation_{i}"] = obs_str
                else:
                    self.local_memory[f"recent_image_{i}"] = None
                    self.local_memory[f"recent_action_{i}"] = 'None'
                    self.local_memory[f"recent_observation_{i}"] = 'None'
            else:
                self.local_memory[f"recent_image_{i}"] = None
                self.local_memory[f"recent_action_{i}"] = 'None'
                self.local_memory[f"recent_observation_{i}"] = 'None'

        # 更新local_memory以包含最近5对和上一段总结
        self.local_memory['recent_pairs_count'] = len(recent_pairs)
        # 转义prev_history_summary中的大括号，避免.format()时出错
        prev_summary_str = str(prev_history_summary or "No previous summary.")
        prev_summary_str = prev_summary_str.replace('{', '{{').replace('}', '}}')
        self.local_memory['prev_history_summary'] = prev_summary_str
        
        # 现在调用get_module_prompts，此时所有字段都已设置
        system_prompt, user_prompt = get_module_prompts(
            self, True, "history_review_system", "history_review_user")
        
        # 准备传递给prompt的图像（最近5个）
        images = {}
        for i, pair in enumerate(recent_pairs[-5:]):
            if pair['image'] is not None:
                images[f"recent_image_{i}"] = pair['image']
        
        # 如果没有prompt文件，使用默认逻辑
        if system_prompt is None and user_prompt is None:
            if not recent_pairs:
                output = {
                    "history_summary": "No history available yet."
                }
                agent_update_memory(self, output)
                return output
            
            # 简单的历史总结（如果没有prompt文件）
            history_summary = f"Recent {len(recent_pairs)} image+action pairs. "
            if prev_history_summary:
                history_summary += f"Previous summary: {prev_history_summary[:200]}... "
            history_summary += f"Latest action: {recent_pairs[-1]['action'] if recent_pairs else 'None'}"
            
            output = {
                "history_summary": history_summary
            }
            agent_update_memory(self, output)
            return output

        # 重新格式化prompt（如果需要）
        if system_prompt:
            system_prompt = system_prompt.format(**self.local_memory)
        if user_prompt:
            user_prompt = user_prompt.format(**self.local_memory)

        # 准备图像字典（包含所有最近5个图像）
        images_for_llm = {}
        for i in range(min(5, len(recent_pairs))):
            if f"recent_image_{i}" in self.local_memory:
                images_for_llm[f"recent_image_{i}"] = self.local_memory[f"recent_image_{i}"]

        response = self.chat_completion(system_prompt, user_prompt, images=images_for_llm, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "history_review")
        
        for key in PREFIXS["history_review"]:
            if key not in output:
                output[key] = None

        agent_update_memory(self, output)

        return output
    
    def history_review_reasoning(self, **kwargs):
        """
        合并的短期历史总结回顾和推理模块
        在一个VLM调用中完成历史回顾和推理
        """
        # 先执行history_review的逻辑，准备数据
        all_images = self.memory.get_all('image')
        all_actions = self.memory.get_all('action')
        all_observations = self.memory.get_all('observation')
        
        historical_images = all_images[:-1] if len(all_images) > 0 else []
        historical_actions = all_actions
        historical_observations = all_observations[:-1] if len(all_observations) > 0 else []
        
        prev_history_summary = self.memory.get_last('history_summary')
        
        recent_pairs = []
        num_pairs = min(5, len(historical_images), len(historical_actions))
        
        for i in range(num_pairs):
            idx = -(num_pairs - i)
            pair = {
                'image': historical_images[idx] if idx < 0 else None,
                'action': historical_actions[idx] if idx < 0 else None,
                'observation': historical_observations[idx] if idx < 0 and idx < len(historical_observations) else None,
            }
            if pair['image'] is not None or pair['action'] is not None:
                recent_pairs.append(pair)
        
        from agent_servers.base_server import agent_get_local_memory
        self.local_memory = agent_get_local_memory(self, None)
        
        recent_pairs_for_prompt = recent_pairs[-5:] if len(recent_pairs) >= 5 else recent_pairs
        for i in range(5):
            if i < len(recent_pairs_for_prompt):
                pair = recent_pairs_for_prompt[i]
                if pair and pair.get('image') is not None:
                    self.local_memory[f"recent_image_{i}"] = pair['image']
                    action_str = str(pair.get('action', 'None'))
                    action_str = action_str.replace('{', '{{').replace('}', '}}')
                    self.local_memory[f"recent_action_{i}"] = action_str
                    obs_str = (pair.get('observation') or 'None')[:200] if pair.get('observation') else 'None'
                    obs_str = str(obs_str).replace('{', '{{').replace('}', '}}')
                    self.local_memory[f"recent_observation_{i}"] = obs_str
                else:
                    self.local_memory[f"recent_image_{i}"] = None
                    self.local_memory[f"recent_action_{i}"] = 'None'
                    self.local_memory[f"recent_observation_{i}"] = 'None'
            else:
                self.local_memory[f"recent_image_{i}"] = None
                self.local_memory[f"recent_action_{i}"] = 'None'
                self.local_memory[f"recent_observation_{i}"] = 'None'
        
        self.local_memory['recent_pairs_count'] = len(recent_pairs)
        prev_summary_str = str(prev_history_summary or "No previous summary.")
        prev_summary_str = prev_summary_str.replace('{', '{{').replace('}', '}}')
        self.local_memory['prev_history_summary'] = prev_summary_str
        
        system_prompt, user_prompt = get_module_prompts(
            self, True, "history_review_reasoning_system", "history_review_reasoning_user")
        
        if system_prompt is None and user_prompt is None:
            if not recent_pairs:
                output = {
                    "history_summary": "No history available yet.",
                    "reasoning": "No reasoning available yet.",
                    "plan": "No plan available yet."
                }
                agent_update_memory(self, output)
                return output
            
            history_summary = f"Recent {len(recent_pairs)} image+action pairs. "
            if prev_history_summary:
                history_summary += f"Previous summary: {prev_history_summary[:200]}... "
            history_summary += f"Latest action: {recent_pairs[-1]['action'] if recent_pairs else 'None'}"
            
            output = {
                "history_summary": history_summary,
                "reasoning": "Reasoning based on current state and history.",
                "plan": "Continue with current strategy."
            }
            agent_update_memory(self, output)
            return output
        
        images_for_llm = {}
        for i, pair in enumerate(recent_pairs[-5:]):
            if pair['image'] is not None:
                images_for_llm[f"recent_image_{i}"] = pair['image']
        # 添加当前图像
        if "cur_image" in self.local_memory and self.local_memory["cur_image"] is not None:
            images_for_llm["cur_image"] = self.local_memory["cur_image"]
        
        response = self.chat_completion(system_prompt, user_prompt, images=images_for_llm, **kwargs)
        
        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "history_review_reasoning")
        
        for key in PREFIXS["history_review_reasoning"]:
            if key not in output:
                output[key] = None
        
        agent_update_memory(self, output)
        return output
    
    def reasoning(self, **kwargs):
        """
        推理模块
        基于当前观测和历史信息进行推理
        """
        system_prompt, user_prompt = get_module_prompts(
            self, False, "reasoning_system", "reasoning_user")
        if system_prompt is None and user_prompt is None:
            # 如果没有prompt文件，使用默认逻辑
            cur_state = self.memory.get_last('observation')
            history_summary = self.memory.get_last('history_summary')
            output = {
                "reasoning": f"Reasoning based on current state and history summary.",
                "plan": "Continue with current strategy."
            }
            agent_update_memory(self, output)
            return output

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "reasoning")

        agent_update_memory(self, output)

        return output
    
    def long_term_memory_retrieval(self, **kwargs):
        """
        查看重要长期记忆模块
        从长期记忆中检索相关信息
        """
        # 构建查询：基于当前观测、历史总结和推理结果
        cur_state = self.memory.get_last('observation')
        history_summary = self.memory.get_last('history_summary')
        reasoning = self.memory.get_last('reasoning')
        
        # 构建查询字符串
        query_parts = []
        if cur_state:
            query_parts.append(f"Current state: {cur_state[:200]}")  # 限制长度
        if history_summary:
            query_parts.append(f"History context: {history_summary[:200]}")
        if reasoning:
            query_parts.append(f"Reasoning: {reasoning[:200]}")
        
        query = " ".join(query_parts) if query_parts else None
        
        # 检索长期记忆
        try:
            memory_snippets = self.memory.retrieve_long_term_memory(
                query, 
                similarity_threshold=0.4
            )
            self.memory.add('retrieved_memory', memory_snippets or None)
            return memory_snippets or None
        except Exception as e:
            logger.error(f"Error retrieving long term memory: {e}")
            self.memory.add('retrieved_memory', None)
            return None
    
    def update_short_term_history(self, **kwargs):
        """
        更新短期历史模块（必须执行）
        将当前步骤的状态、图像和动作添加到短期历史中
        确保存储image+action对，用于后续的history_review
        """
        # 获取当前状态、图像和动作
        cur_state = self.memory.get_last('observation')
        cur_image = self.memory.get_last('image')
        action = self.memory.get_last('action')
        
        # 更新step_count
        if not hasattr(self.memory, 'step_count'):
            self.memory.step_count = 0
        self.memory.step_count += 1
        
        # 构建历史条目（包含image+action对）
        history_entry = {
            f"step_{self.memory.step_count}_state": cur_state,
            f"step_{self.memory.step_count}_action": action,
            f"step_{self.memory.step_count}_has_image": cur_image is not None,
        }
        
        # 注意：图像对象不直接存储在history_entry中（因为可能很大）
        # 而是通过memory.get_all('image')来获取，确保image和action的索引对应
        
        # 添加推理和记忆信息（如果有）
        reasoning = self.memory.get_last('reasoning')
        if reasoning:
            history_entry[f"step_{self.memory.step_count}_reasoning"] = reasoning
        
        retrieved_memory = self.memory.get_last('retrieved_memory')
        if retrieved_memory:
            history_entry[f"step_{self.memory.step_count}_retrieved_memory"] = retrieved_memory[:500]  # 限制长度
        
        # 添加到历史列表
        if not hasattr(self.memory, 'histories'):
            self.memory.histories = []
        
        self.memory.histories.append(history_entry)
        
        # 保持历史列表在合理大小（但保留更多以支持5个image+action对）
        if not hasattr(self.memory, 'num_history_buffer'):
            self.memory.num_history_buffer = 20
        self.memory.histories = self.memory.histories[-self.memory.num_history_buffer:]
        
        # 同时保持image和action列表在合理大小（确保至少有5个）
        all_images = self.memory.get_all('image')
        all_actions = self.memory.get_all('action')
        if len(all_images) > 10:  # 保留更多以支持history_review的需求
            # 保留最近10个图像和动作
            self.memory.memories['image'] = all_images[-10:]
            self.memory.memories['action'] = all_actions[-10:]
        
        # 更新短期历史到memory
        self.memory.add('short_term_history', self.memory.histories)
        
        return self.memory.histories
    
    def add_long_term_memory_optional(self, **kwargs):
        """
        添加新的长期记忆模块（可选）
        根据推理结果和当前状态，决定是否添加新的长期记忆
        """
        system_prompt, user_prompt = get_module_prompts(
            self, False, "add_long_term_memory_system", "add_long_term_memory_user")
        
        if system_prompt is None and user_prompt is None:
            # 如果没有prompt文件，使用默认逻辑：不添加记忆
            output = {
                "new_memory": None,
                "should_save": "No"
            }
            agent_update_memory(self, output)
            return output

        images = {k: self.local_memory[k] for k in ("cur_image", "prev_image") if k in self.local_memory}

        response = self.chat_completion(system_prompt, user_prompt, images=images, **kwargs)

        if "guided_json" in kwargs:
            output = json.loads(response)
            output = {key: value for key, value in output.items() if key in kwargs["output_keys"]}
        else:
            output = parse_module_response(response, "add_long_term_memory_optional")

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

        return output
