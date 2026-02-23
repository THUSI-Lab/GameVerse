from typing import List, Dict, Union
import os
import logging
import base64

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def setup_gemini(api_key: str = None) -> genai.Client:
    """
    使用API key设置Gemini客户端
    
    Args:
        api_key: Google API密钥，如果为None则从环境变量或key.env文件读取
    
    Returns:
        genai.Client实例
    """
    if api_key is None:
        # 首先尝试从环境变量读取
        api_key = os.getenv('GOOGLE_API_KEY')
        
        # 如果环境变量没有，尝试从key.env文件读取
        if not api_key:
            key_file_path = os.path.join(
                os.path.dirname(__file__), 
                "..", "..", "agent_servers", "keys", "google-key", "key.env"
            )
            if os.path.exists(key_file_path):
                try:
                    with open(key_file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        # 如果文件内容包含=，则按环境变量格式解析
                        if '=' in content:
                            for line in content.split('\n'):
                                if line.strip().startswith('GOOGLE_API_KEY='):
                                    api_key = line.split('=', 1)[1].strip()
                                    break
                        else:
                            # 否则整个文件内容就是API key
                            api_key = content
                except Exception as e:
                    logger.warning(f"读取key.env文件失败: {e}")
    
    if not api_key:
        raise ValueError(
            "需要提供GOOGLE_API_KEY。请检查:\n"
            "1. 环境变量 GOOGLE_API_KEY\n"
            "2. 或者 src/agent_servers/keys/google-key/key.env 文件"
        )
    
    client = genai.Client(api_key=api_key)
    return client

try:
    client = setup_gemini()
except Exception as e:
    print(f"Exception occurred while setting up Gemini client: {e}")
    client = None


class Message:
    def __init__(self, role: str, content: str):
        self.role = role 
        self.content = content

class Choice:
    def __init__(self, message: Message):
        self.message = message

class GeminiChatCompletionResponse:
    def __init__(self, text: str, role: str):
        self.choices = [Choice(Message(role=role, content=text))] 
        self.usage = None  # unavailable in gemini


# def chat_completion_request(
#     model: str,
#     messages: List[Dict[str, str]],
#     temperature: float = 0.2,
#     top_p: float = 0.8,
#     max_tokens: int = 1024,
#     stream: bool = False,
# ) -> GeminiChatCompletionResponse:

#     system_prompt = None
#     contents = []

#     for m in messages:
#         if m["role"] == "system" and system_prompt is None:
#             system_prompt = m["content"]
#         else:
#             if isinstance(m["content"], str):
#                 contents.append(
#                     types.Content(
#                         role=m["role"],
#                         parts=[types.Part.from_text(text=m["content"])]
#                     )
#                 )
#             elif isinstance(m["content"], list):
#                 for part in m["content"]:
#                     if part["type"] == "text":
#                         contents.append(
#                             types.Content(
#                                 role=m["role"],
#                                 parts=[types.Part.from_text(text=part["text"])]
#                             )
#                         )
#                     elif part["type"] == "image_url":
#                         base64_image = part["image_url"]["url"][len("data:image/png;base64,"):]
#                         image_bytes = base64.b64decode(base64_image)
#                         contents.append(
#                             types.Content(
#                                 role=m["role"],
#                                 parts=[types.Part.from_bytes(data=image_bytes, mime_type="image/png")]
#                             )
#                         )
#                     else:
#                         raise ValueError("Content must be a string or list of strings.")

#     if system_prompt is None:
#         system_prompt = ""

#     generate_content_config = types.GenerateContentConfig(
#         temperature=temperature,
#         top_p=top_p,
#         max_output_tokens=max_tokens,
#         response_modalities=["TEXT"],
#         safety_settings=[],
#         system_instruction=[types.Part(text=system_prompt)],
#     )

#     full_text = ""
#     response_role = ""  # default role

#     if stream:
#         for chunk in client.models.generate_content_stream(
#             model=model,
#             contents=contents,
#             config=generate_content_config,
#         ):
#             if hasattr(chunk, "text") and chunk.text:
#                 full_text += chunk.text
#                 response_role = "assistant" 
#     else:
#         max_retries = 100
#         for attempt in range(max_retries):
#             full_text = ""
#             response_role = ""
#             response = client.models.generate_content(
#                 model=model,
#                 contents=contents,
#                 config=generate_content_config,
#             )
#             if hasattr(response, "candidates") and response.candidates:
#                 for candidate in response.candidates:
#                     if candidate.content.parts:
#                         for part in candidate.content.parts:
#                             if hasattr(part, "text") and part.text:
#                                 full_text += part.text
#                                 response_role = "assistant"

#             if full_text and response_role:
#                 break
#             logger.info(f"[Retry {attempt+1}] Empty response. Retrying...")

#     return GeminiChatCompletionResponse(text=full_text, role=response_role)

def chat_completion_request(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    top_p: float = 0.8,
    max_tokens: int = 1024,
    stream: bool = False,
) -> GeminiChatCompletionResponse:
    """
    使用新的Gemini API进行聊天完成请求
    """
    if client is None:
        raise RuntimeError("Gemini client not initialized. Please check your API key.")

    system_prompt = None
    contents = []

    # 处理消息格式
    for m in messages:
        if m["role"] == "system" and system_prompt is None:
            system_prompt = m["content"]
        else:
            # 转换角色名称：assistant -> model
            role = "model" if m["role"] == "assistant" else m["role"]
            
            if isinstance(m["content"], str):
                contents.append({
                    "role": role,
                    "parts": [{"text": m["content"]}]
                })
            elif isinstance(m["content"], list):
                parts = []
                for part in m["content"]:
                    if part["type"] == "text":
                        parts.append({"text": part["text"]})
                    elif part["type"] == "image_url":
                        # 处理base64图片
                        image_url = part["image_url"]["url"]
                        if image_url.startswith("data:image/"):
                            # 提取base64数据
                            mime_type, base64_data = image_url.split(",", 1)
                            mime_type = mime_type.split(":")[1].split(";")[0]
                            image_bytes = base64.b64decode(base64_data)
                            parts.append({
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": base64_data
                                }
                            })
                        else:
                            raise ValueError(f"Unsupported image URL format: {image_url}")
                    else:
                        raise ValueError(f"Unsupported content type: {part['type']}")
                
                contents.append({
                    "role": role,
                    "parts": parts
                })

    # 构建生成配置
    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
        "max_output_tokens": max_tokens,
    }

    full_text = ""
    response_role = "assistant"

    max_retries = 10
    for attempt in range(max_retries):
        try:
            # 使用新的API调用方式
            if system_prompt:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        **generation_config,
                        "system_instruction": {"parts": [{"text": system_prompt}]}
                    }
                )
            else:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generation_config
                )
            
            # 提取响应文本
            # 首先尝试从 candidates 中提取（处理 candidates 为 None 或空列表的情况）
            if hasattr(response, "candidates"):
                if response.candidates:  # candidates 不为 None 且不为空列表
                    for candidate in response.candidates:
                        # 检查finish_reason，如果被截断或阻止，记录警告
                        if hasattr(candidate, "finish_reason"):
                            finish_reason = candidate.finish_reason
                            if finish_reason and finish_reason != "STOP":
                                print(f"[Warning] Gemini response finish_reason: {finish_reason}. Response may be incomplete.")
                                if finish_reason in ["MAX_TOKENS", "RECITATION"]:
                                    print(f"[Warning] Response was truncated due to: {finish_reason}")
                                elif finish_reason in ["SAFETY", "PROHIBITED_CONTENT"]:
                                    print(f"[Warning] Response was blocked due to safety filter: {finish_reason}")
                        
                        # 尝试多种方式提取文本
                        if hasattr(candidate, "content"):
                            content = candidate.content
                            # 方式1: content.parts
                            if hasattr(content, "parts") and content.parts:
                                for part in content.parts:
                                    # 更严格的检查：确保 text 属性存在且不为 None 且不为空字符串
                                    if hasattr(part, "text"):
                                        part_text = part.text
                                        if part_text is not None and part_text != "":
                                            full_text += part_text
                            # 方式2: content.text (直接属性)
                            elif hasattr(content, "text"):
                                content_text = content.text
                                if content_text is not None and content_text != "":
                                    full_text += content_text
                        # 方式3: candidate.text (直接属性)
                        elif hasattr(candidate, "text"):
                            candidate_text = candidate.text
                            if candidate_text is not None and candidate_text != "":
                                full_text += candidate_text
                # 如果 candidates 为 None 或空列表，尝试直接从 response 获取 text
                elif hasattr(response, "text"):
                    response_text = response.text
                    if response_text is not None and response_text != "":
                        full_text = response_text
            # 如果 response 没有 candidates 属性，直接尝试获取 text
            elif hasattr(response, "text"):
                response_text = response.text
                if response_text is not None and response_text != "":
                    full_text = response_text

            if full_text:
                break
            
            # 如果仍然为空，打印调试信息
            if attempt == 0:  # 只在第一次尝试时打印详细调试信息
                print(f"[Debug] Response structure: {type(response)}")
                print(f"[Debug] Response attributes: {dir(response)}")
                if hasattr(response, "candidates"):
                    print(f"[Debug] Candidates: {response.candidates}")
                    if response.candidates:
                        print(f"[Debug] First candidate attributes: {dir(response.candidates[0])}")
            print(f"[Retry {attempt+1}] Empty response. Retrying...")
            
        except Exception as e:
            import time
            print(f"[Retry {attempt + 1}] Unexpected error: {e}. Retrying...")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return GeminiChatCompletionResponse(text=full_text, role=response_role)