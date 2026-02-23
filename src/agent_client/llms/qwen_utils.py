import os
import base64
from typing import List, Dict, Union, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion
import time

def setup_qwen(key_path: str = "src/agent_servers/keys/qwen-key/key.env") -> str:
    """
    设置Qwen API密钥（保留向后兼容性）
    
    Args:
        key_path: 密钥文件路径
        
    Returns:
        API密钥字符串
    """

    api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('QWEN_API_KEY')
    if api_key:
        return api_key
    raise FileNotFoundError(f"API key file not found: {key_path} and no environment variable set")

def get_qwen_client():
    """
    获取Qwen客户端，支持多种密钥获取方式
    
    Returns:
        OpenAI客户端实例
    """
    api_key = None
    
    # 方法1: 尝试从环境变量获取
    api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('QWEN_API_KEY')
    
    # 方法2: 如果环境变量没有，尝试从文件读取
    if not api_key:
        # 获取当前工作目录和脚本目录
        cwd = os.getcwd()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        key_paths = [
            "src/agent_servers/keys/qwen-key/key.env",
            "./src/agent_servers/keys/qwen-key/key.env", 
            os.path.join(cwd, "src/agent_servers/keys/qwen-key/key.env"),
            os.path.join(script_dir, "../../../agent_servers/keys/qwen-key/key.env"),
            "../src/agent_servers/keys/qwen-key/key.env"
        ]
        
        print(f"Current working directory: {cwd}")
        print(f"Script directory: {script_dir}")
        
        for key_path in key_paths:
            try:
                abs_path = os.path.abspath(key_path)
                print(f"Trying to read key from: {abs_path}")
                if os.path.exists(abs_path):
                    with open(abs_path, "r", encoding='utf-8') as f:
                        api_key = f.read().strip()
                    if api_key:  # 确保读取到了非空内容
                        print(f"Successfully loaded API key from {abs_path}")
                        print(f"Key length: {len(api_key)}, starts with: {api_key[:10]}...")
                        break
                    else:
                        print(f"File exists but is empty: {abs_path}")
                else:
                    print(f"File does not exist: {abs_path}")
            except Exception as e:
                print(f"Failed to read key from {key_path}: {e}")
                continue
    
    if not api_key:
        raise ValueError("No Qwen API key found. Please set DASHSCOPE_API_KEY environment variable or place key in qwen-key/key.env")
    
    # 设置环境变量供其他地方使用
    os.environ["DASHSCOPE_API_KEY"] = api_key
    os.environ["QWEN_API_KEY"] = api_key
    
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

# 延迟初始化客户端
client = None

def get_client():
    """获取或创建客户端"""
    global client
    if client is None:
        try:
            client = get_qwen_client()
        except Exception as e:
            print(f"Exception occurred while setting up Qwen client: {e}")
            client = None
    return client

def encode_image_base64(image_path: str) -> str:
    """
    将图片编码为base64字符串
    
    Args:
        image_path: 图片路径
        
    Returns:
        base64编码的字符串
    """
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def chat_completion_request(
    messages: Union[List[Dict], List],
    model: str = "qwen-vl-plus",
    temperature: float = 1.0,
    max_tokens: int = 8192,
    stop=None,
    stream: bool = False,
    **kwargs
) -> ChatCompletion:
    
    """
    Qwen模型聊天完成请求
    
    Args:
        messages: 消息列表，支持文本和图像
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        stop: 停止词
        stream: 是否流式输出
        **kwargs: 其他参数
        
    Returns:
        ChatCompletion响应
    """
    max_retries = 10
    current_client = get_client()
    
    if current_client is None:
        raise Exception("Failed to initialize Qwen client")
    
    for attempt in range(max_retries):
        try:
            response = current_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                stop=stop,
                **kwargs
            )
            return response
        except Exception as e:
            if attempt < max_retries-1:
                print(f"[Warning] chat_completion_request failed (attempt {attempt+1}), retrying...")
                time.sleep(0.5)
                continue
            else:
                print(f"[Error] chat_completion_request failed after {max_retries} attempts.")
                raise e

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
