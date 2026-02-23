import os
import base64
import asyncio
from typing import List, Dict, Union, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion
import time
from volcenginesdkarkruntime import AsyncArk

# 尝试导入 ResponsesReasoning 枚举类型
REASONING_ENUM_AVAILABLE = False
ResponsesReasoning = None

try:
    from openai.types.responses import ResponsesReasoning
    REASONING_ENUM_AVAILABLE = True
except ImportError:
    # 如果导入失败，尝试其他可能的路径
    try:
        from openai.resources.responses.types import ResponsesReasoning
        REASONING_ENUM_AVAILABLE = True
    except ImportError:
        # 如果都失败，枚举不可用，将不传递 reasoning 参数
        pass

def get_seed_api_key() -> str:
    """
    获取 Seed API 密钥
    
    Returns:
        API密钥字符串
    """
    # 方法1: 尝试从环境变量获取
    api_key = os.getenv('ARK_API_KEY')
    if api_key:
        return api_key
    
    # 方法2: 从文件读取
    cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    key_paths = [
        "src/agent_servers/keys/seed-key/key.env",
        "./src/agent_servers/keys/seed-key/key.env", 
        os.path.join(cwd, "src/agent_servers/keys/seed-key/key.env"),
        os.path.join(script_dir, "../../../agent_servers/keys/seed-key/key.env"),
        "../src/agent_servers/keys/seed-key/key.env"
    ]
    
    for key_path in key_paths:
        try:
            abs_path = os.path.abspath(key_path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding='utf-8') as f:
                    api_key = f.read().strip()
                if api_key:
                    return api_key
        except Exception as e:
            print(f"Failed to read key from {key_path}: {e}")
            continue
    
    raise ValueError("No Seed API key found. Please set ARK_API_KEY environment variable or place key in seed-key/key.env")

def get_seed_client():
    """
    获取 Seed 客户端
    
    Returns:
        OpenAI客户端实例（配置了 Seed API 的 base_url）
    """
    api_key = get_seed_api_key()
    
    # 设置环境变量供其他地方使用
    os.environ["ARK_API_KEY"] = api_key
    
    return OpenAI(
        api_key=api_key,
        base_url="https://ark.cn-beijing.volces.com/api/v3"
    )

# 延迟初始化客户端
client = None

def get_client():
    """获取或创建客户端"""
    global client
    if client is None:
        try:
            client = get_seed_client()
        except Exception as e:
            print(f"Exception occurred while setting up Seed client: {e}")
            client = None
    return client

def encode_image_base64(image: Union[str, bytes]) -> str:
    """
    将图片编码为base64字符串
    
    Args:
        image: 图片路径（str）或图片数据（bytes）或 PIL Image 对象
        
    Returns:
        base64编码的字符串
    """
    if isinstance(image, str):
        # 如果是文件路径
        with open(image, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    elif isinstance(image, bytes):
        # 如果已经是字节数据
        return base64.b64encode(image).decode('utf-8')
    else:
        # 假设是 PIL Image 对象
        from io import BytesIO
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

def convert_messages_to_seed_format(messages: List[Dict]) -> List[Dict]:
    """
    将标准消息格式转换为 Seed 模型需要的格式
    
    Seed 格式：
    input = [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": "..."},
                {"type": "input_text", "text": "..."}
            ]
        }
    ]
    
    Args:
        messages: 标准消息列表，格式为 [{"role": "...", "content": ...}]
        
    Returns:
        Seed 格式的 input 列表
    """
    seed_input = []
    system_content = None
    
    # 首先提取 system 消息内容
    for message in messages:
        if message.get("role") == "system":
            content = message.get("content", "")
            if isinstance(content, str) and content.strip():
                system_content = content
            break
    
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        
        # 跳过 system 消息
        if role == "system":
            continue
        
        seed_content = []
        
        # 如果是第一个非 system 消息且有 system 内容，先添加 system 内容
        if system_content and len(seed_input) == 0:
            seed_content.append({
                "type": "input_text",
                "text": system_content
            })
        
        # 处理 content
        if isinstance(content, str):
            # 纯文本
            if content.strip():
                seed_content.append({
                    "type": "input_text",
                    "text": content
                })
        elif isinstance(content, list):
            # 多模态内容（文本、图像和视频）
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        # 文本类型
                        text = item.get("text", "")
                        if text.strip():
                            seed_content.append({
                                "type": "input_text",
                                "text": text
                            })
                    elif item.get("type") == "image_url":
                        # 图像类型
                        image_url = item.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:image/"):
                            # 提取 base64 数据
                            header, base64_data = image_url.split(",", 1)
                            seed_content.append({
                                "type": "input_image",
                                "image_url": f"data:image/png;base64,{base64_data}"
                            })
                        elif image_url.startswith("http://") or image_url.startswith("https://"):
                            # HTTP URL
                            seed_content.append({
                                "type": "input_image",
                                "image_url": image_url
                            })
                        else:
                            # 文件路径，需要转换为 base64
                            try:
                                base64_image = encode_image_base64(image_url)
                                seed_content.append({
                                    "type": "input_image",
                                    "image_url": f"data:image/png;base64,{base64_image}"
                                })
                            except Exception as e:
                                print(f"Warning: Failed to encode image {image_url}: {e}")
                                continue
                    elif item.get("type") == "video" or item.get("type") == "input_video":
                        # 视频类型（支持两种格式：video 和 input_video）
                        file_id = item.get("file_id") or item.get("video_file_id")
                        if file_id:
                            seed_content.append({
                                "type": "input_video",
                                "file_id": file_id
                            })
        
        # 如果有内容，添加到 input
        if seed_content:
            seed_input.append({
                "role": role,
                "content": seed_content
            })
    
    return seed_input

def chat_completion_request(
    messages: Union[List[Dict], List],
    model: str = "doubao-seed-1-8-251228",
    temperature: float = 1.0,
    max_output_tokens: int = 16384,
    stop=None,
    stream: bool = False,
    reasoning: str = "low",
    **kwargs
):
    """
    Seed 模型聊天完成请求
    
    Args:
        messages: 消息列表，支持文本和图像
        model: 模型名称
        temperature: 温度参数
        max_output_tokens: 最大输出token数，默认为 16384
        stop: 停止词
        stream: 是否流式输出
        reasoning: 思考能力级别，可选值 "low"、"medium"、"high"，默认为 "low"
        **kwargs: 其他参数
        
    Returns:
        响应对象（需要转换为 ChatCompletion 格式）
    """
    max_retries = 10
    current_client = get_client()
    
    if current_client is None:
        raise Exception("Failed to initialize Seed client")
    
    # 转换消息格式
    seed_input = convert_messages_to_seed_format(messages)
    
    # 转换 reasoning 字符串为枚举类型（如果可用）
    reasoning_param = None
    reasoning_available = REASONING_ENUM_AVAILABLE and ResponsesReasoning is not None
    
    if reasoning_available:
        try:
            # 将字符串映射到枚举值
            reasoning_map = {
                "low": ResponsesReasoning.LOW,
                "medium": ResponsesReasoning.MEDIUM,
                "high": ResponsesReasoning.HIGH
            }
            if reasoning.lower() in reasoning_map:
                reasoning_param = reasoning_map[reasoning.lower()]
        except (AttributeError, NameError, TypeError):
            # 如果枚举类型不存在或无法访问，标记为不可用
            reasoning_available = False
    
    for attempt in range(max_retries):
        try:
            # 使用 responses.create() 方法
            # 构建参数字典
            create_params = {
                "model": model,
                "input": seed_input,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
            
            # 只在枚举可用且已转换时添加 reasoning
            # 根据错误信息，API 不接受字符串，必须使用枚举类型
            if reasoning_available and reasoning_param is not None:
                create_params["reasoning"] = reasoning_param
            # 如果枚举不可用，不传递 reasoning 参数，让 API 使用默认值
            
            # 添加其他 kwargs（但排除可能冲突的参数）
            for key, value in kwargs.items():
                if key not in create_params:
                    create_params[key] = value
            
            response = current_client.responses.create(**create_params)
            
            # 将 Seed 响应转换为 ChatCompletion 格式
            return _convert_seed_response_to_chat_completion(response, model)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[Warning] chat_completion_request failed (attempt {attempt+1}), retrying...")
                time.sleep(0.5)
                continue
            else:
                print(f"[Error] chat_completion_request failed after {max_retries} attempts.")
                raise e

def _convert_seed_response_to_chat_completion(seed_response, model: str):
    """
    将 Seed API 响应转换为 ChatCompletion 格式
    
    Args:
        seed_response: Seed API 的响应对象
        model: 模型名称
        
    Returns:
        ChatCompletion 格式的响应对象
    """
    # 创建一个类似 ChatCompletion 的对象
    class SeedChatCompletion:
        def __init__(self, seed_response, model):
            self.model = model
            self.choices = [SeedChoice(seed_response)]
            self.usage = None  # Seed API 可能不提供 usage 信息
            self.created = getattr(seed_response, 'created', None)
            self.id = getattr(seed_response, 'id', None)
            self.object = 'chat.completion'
    
    class SeedChoice:
        def __init__(self, seed_response):
            self.index = 0
            self.message = SeedMessage(seed_response)
            self.finish_reason = getattr(seed_response, 'finish_reason', 'stop')
            self.logprobs = None
    
    class SeedMessage:
        def __init__(self, seed_response):
            self.role = 'assistant'
            
            # 从 output 数组中查找 type='message' 的元素，提取 content[0].text
            content_text = ""
            output = getattr(seed_response, 'output', None)
            if isinstance(output, list):
                for item in output:
                    # 获取 item 的类型（支持对象和字典）
                    item_type = getattr(item, 'type', None) if hasattr(item, 'type') else (item.get('type') if isinstance(item, dict) else None)
                    
                    # 只处理 message 类型，跳过 reasoning
                    if item_type == 'message':
                        # 获取 content 数组（支持对象和字典）
                        content_list = getattr(item, 'content', None) if hasattr(item, 'content') else (item.get('content') if isinstance(item, dict) else None)
                        
                        # 从 content[0].text 提取文本
                        if isinstance(content_list, list) and len(content_list) > 0:
                            first_content = content_list[0]
                            content_text = getattr(first_content, 'text', None) if hasattr(first_content, 'text') else (first_content.get('text') if isinstance(first_content, dict) else None)
                            if content_text:
                                break
            
            self.content = content_text or ""
            self.function_call = None
            self.tool_calls = None
    
    return SeedChatCompletion(seed_response, model)

def create_vision_message(text: str, image_path: Optional[str] = None) -> Dict:
    """
    创建支持视觉的消息格式
    
    Args:
        text: 文本内容
        image_path: 图片路径（可选）
        
    Returns:
        格式化的消息字典
    """
    content = []
    
    # 添加文本内容
    if text:
        content.append({
            "type": "text",
            "text": text
        })
    
    # 添加图像内容
    if image_path:
        base64_image = encode_image_base64(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}"
            }
        })
    
    return {
        "role": "user",
        "content": content
    }

async def upload_video_to_seed_async(video_path: str, fps: float = 1.0) -> str:
    """
    异步上传视频文件到 Seed API
    
    Args:
        video_path: 视频文件路径
        fps: 视频采样帧率，默认 1.0（每秒一帧）
    
    Returns:
        上传后的文件 ID
    """
    api_key = get_seed_api_key()
    client = AsyncArk(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key=api_key
    )
    
    # 上传视频文件
    with open(video_path, "rb") as video_file:
        file = await client.files.create(
            file=video_file,
            purpose="user_data",
            preprocess_configs={
                "video": {
                    "fps": fps,
                }
            }
        )
    
    file_id = file.id
    
    # 等待文件处理完成
    await client.files.wait_for_processing(file_id)
    
    return file_id

def upload_video_to_seed(video_path: str, fps: float = 1.0) -> str:
    """
    同步上传视频文件到 Seed API（异步函数的同步包装器）
    
    Args:
        video_path: 视频文件路径
        fps: 视频采样帧率，默认 1.0（每秒一帧）
    
    Returns:
        上传后的文件 ID
    """
    return asyncio.run(upload_video_to_seed_async(video_path, fps))

