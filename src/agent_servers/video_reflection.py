"""
视频反思模块：从失败视频和专家视频中提取经验
支持不同模型的视频输入方式
"""
import os
import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable
import imageio
import numpy as np
from PIL import Image
import base64
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from dashscope import MultiModalConversation
    import dashscope
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    logger.warning("dashscope not available, Qwen video analysis may not work properly")


def encode_image_base64(image: Image.Image) -> str:
    """将PIL Image编码为base64字符串"""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def get_qwen_api_key() -> str:
    """
    获取Qwen API密钥
    
    Returns:
        API密钥字符串
    """
    # 方法1: 尝试从环境变量获取
    api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('QWEN_API_KEY')
    if api_key:
        return api_key
    
    # 方法2: 从文件读取
    cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    key_paths = [
        "src/agent_servers/keys/qwen-key/key.env",
        "./src/agent_servers/keys/qwen-key/key.env", 
        os.path.join(cwd, "src/agent_servers/keys/qwen-key/key.env"),
        os.path.join(script_dir, "../../keys/qwen-key/key.env"),
        "../src/agent_servers/keys/qwen-key/key.env"
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
            logger.warning(f"Failed to read key from {key_path}: {e}")
            continue
    
    raise ValueError("No Qwen API key found. Please set DASHSCOPE_API_KEY environment variable or place key in qwen-key/key.env")


def get_model_type(model_name: str) -> str:
    """
    根据模型名称判断模型类型
    
    Returns:
        "gemini", "qwen", "gpt4o", "seed", 或其他
    """
    model_name_lower = model_name.lower()
    if "gemini" in model_name_lower:
        return "gemini"
    elif "qwen" in model_name_lower:
        return "qwen"
    elif "gpt-4o" in model_name_lower or "gpt4o" in model_name_lower:
        return "gpt4o"
    elif "seed" in model_name_lower or "doubao-seed" in model_name_lower:
        return "seed"
    else:
        return "other"


def load_all_frames_from_obs_images(obs_images_dir: str) -> List[Image.Image]:
    """
    从obs_images目录加载所有帧（用于GPT-4o失败视频分析）
    
    Args:
        obs_images_dir: obs_images目录路径
    
    Returns:
        所有帧的列表（按文件名排序）
    """
    frames = []
    if not os.path.exists(obs_images_dir):
        logger.warning(f"obs_images目录不存在: {obs_images_dir}")
        return frames
    
    # 获取所有step_*.png文件并按文件名排序
    image_files = sorted(Path(obs_images_dir).glob("step_*.png"))
    
    for img_file in image_files:
        try:
            img = Image.open(img_file)
            # 转换为RGB格式
            if img.mode != 'RGB':
                img = img.convert('RGB')
            frames.append(img)
        except Exception as e:
            logger.warning(f"无法读取图片 {img_file}: {e}")
            continue
    
    logger.info(f"从obs_images目录加载了{len(frames)}帧")
    return frames


def extract_frames_from_video(video_path: str, fps: float = 0.5) -> List[Image.Image]:
    """
    从视频中按指定频率提取帧（用于GPT-4o专家视频分析）
    默认2秒1帧（fps=0.5）
    
    Args:
        video_path: 视频文件路径
        fps: 提取帧率（每秒帧数），默认0.5（即2秒1帧）
    
    Returns:
        提取的帧列表
    """
    frames = []
    try:
        reader = imageio.get_reader(video_path)
        total_frames = reader.count_frames()
        video_fps = reader.get_meta_data().get('fps', 30)  # 默认30fps
        
        if total_frames == 0:
            logger.warning(f"视频 {video_path} 没有帧")
            return frames
        
        # 计算帧间隔（每多少帧提取一帧）
        frame_interval = max(1, int(video_fps / fps))
        
        # 提取帧
        for idx in range(0, total_frames, frame_interval):
            try:
                frame = reader.get_data(idx)
                img = Image.fromarray(frame)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                frames.append(img)
            except Exception as e:
                logger.warning(f"无法读取第 {idx} 帧: {e}")
                continue
        
        reader.close()
        logger.info(f"从视频提取了{len(frames)}帧（fps={fps}）")
        return frames
    except Exception as e:
        logger.error(f"提取关键帧失败: {e}")
        return []


def upload_video_to_gemini(video_path: str, max_wait_time: int = 600):
    """
    上传视频文件到Gemini，并等待文件变为ACTIVE状态
    
    Args:
        video_path: 视频文件路径
        max_wait_time: 最大等待时间（秒），默认300秒（5分钟）
    
    Returns:
        上传后的文件对象（处于ACTIVE状态）
    """
    import time
    from agent_client.llms.google_utils import setup_gemini
    client = setup_gemini()
    
    logger.info(f"开始上传视频到Gemini: {video_path}")
    myfile = client.files.upload(file=video_path)
    
    # 等待文件变为ACTIVE状态
    start_time = time.time()
    wait_interval = 15  # 每15秒检查一次
    
    while True:
        # 刷新文件状态
        myfile = client.files.get(name=myfile.name)
        
        # 检查文件状态
        if hasattr(myfile, 'state'):
            state = myfile.state
            logger.info(f"文件状态: {state}")
            
            if state == "ACTIVE":
                logger.info("文件已激活，可以使用")
                break
            elif state == "FAILED":
                raise Exception(f"文件上传失败，状态: {state}")
        else:
            # 如果没有state属性，尝试直接使用（某些版本可能没有state属性）
            logger.warning("文件对象没有state属性，尝试直接使用")
            break
        
        # 检查是否超时
        elapsed_time = time.time() - start_time
        if elapsed_time > max_wait_time:
            raise TimeoutError(f"等待文件激活超时（超过{max_wait_time}秒）")
        
        # 等待一段时间后再次检查
        time.sleep(wait_interval)
    
    return myfile


def analyze_failure_video(
    llm,
    model_type: str,
    game_name: str,
    failure_video_path: Optional[str] = None,
    obs_images_dir: Optional[str] = None
) -> str:
    """
    第一阶段：分析失败视频，总结失败场景和原因
    
    Args:
        llm: LLM实例
        model_type: 模型类型（"gemini", "qwen", "gpt4o"等）
        game_name: 游戏名称
        failure_video_path: 失败视频路径
        obs_images_dir: obs_images目录路径（用于GPT-4o）
    
    Returns:
        失败场景和原因的总结文本
    """
    system_prompt = f"""You are a game strategy analysis expert. Your task is to analyze failure scenarios and reasons from failed game videos.

    Requirements:
    1. Carefully observe the game process in the video
    2. Identify key errors and issues that led to failure
    3. Summarize failure scenarios and reasons, be specific and clear
    4. Output format: Plain text, list failure scenarios and reasons in bullet points
    """

    user_content = [{"type": "text", "text": f"Game name: {game_name}\n\nPlease analyze this failure video and summarize the failure scenarios and reasons.\n"}]
    
    if model_type == "gemini":
        # Gemini：直接上传视频文件
        if failure_video_path and os.path.exists(failure_video_path):
            try:
                video_file = upload_video_to_gemini(failure_video_path)
                # Gemini使用特殊格式：在contents中直接使用文件对象和文本
                text_content = user_content[0]["text"]
                user_content = [video_file, text_content]
            except Exception as e:
                logger.error(f"上传视频到Gemini失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        else:
            raise ValueError(f"失败视频路径不存在: {failure_video_path}")
    elif model_type == "qwen":
        # Qwen：使用dashscope MultiModalConversation API，通过file://协议传入视频文件绝对路径
        # 这样可以避免base64编码的10MB限制
        if failure_video_path and os.path.exists(failure_video_path):
            try:
                # 获取视频文件的绝对路径
                # Windows 路径需要转换为正斜杠，因为 file:// 协议使用正斜杠
                abs_video_path = os.path.abspath(failure_video_path)
                # 将反斜杠转换为正斜杠
                abs_video_path = abs_video_path.replace('\\', '/')
                video_path = f"file://{abs_video_path}"
                
                # 使用dashscope API直接调用
                if not DASHSCOPE_AVAILABLE:
                    raise ImportError("dashscope package is required for Qwen video analysis. Please install it: pip install dashscope")
                
                api_key = get_qwen_api_key()
                model_name = llm.model if hasattr(llm, 'model') else "qwen3-vl-8b-instruct"
                
                # 构建消息格式
                # 根据 dashscope 文档，需要添加 fps 参数控制视频抽帧数量（每隔1/fps秒抽取一帧）
                messages = [
                    {
                        'role': 'user',
                        'content': [
                            {'video': video_path, 'fps': 2},  # fps=2 表示每隔0.5秒抽取一帧
                            {'text': f"{system_prompt}\n\n{user_content[0]['text']}"}
                        ]
                    }
                ]
                
                # 调用dashscope API
                response = MultiModalConversation.call(
                    api_key=api_key,
                    model=model_name,
                    messages=messages
                )
                
                # 检查响应是否有错误
                if hasattr(response, 'status_code') and response.status_code != 200:
                    error_msg = str(response)
                    # 如果视频太短，回退到提取关键帧的方式
                    if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                        logger.warning(f"视频文件太短，无法直接使用dashscope API，回退到提取关键帧的方式: {error_msg}")
                        # 回退到提取关键帧的方式
                        frames = extract_frames_from_video(failure_video_path, fps=2.0)  # 1秒1帧
                        if frames:
                            # 如果帧数太多，均匀采样
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            # 使用提取的关键帧构建消息
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{user_content[0]['text']}\n\nKey frames from the failure video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            # 使用OpenAI兼容接口调用（通过llm.chat）
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            # 解析响应
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    failure_analysis = message.content
                                else:
                                    failure_analysis = str(message)
                            else:
                                failure_analysis = str(response_obj)
                            
                            return failure_analysis.strip()
                        else:
                            raise ValueError("无法从失败视频提取帧")
                    else:
                        # 其他错误，直接抛出
                        raise Exception(f"DashScope API调用失败: {error_msg}")
                
                # 解析正常响应
                if response and response.output and response.output.choices:
                    content = response.output.choices[0].message.content
                    if isinstance(content, list) and len(content) > 0:
                        if 'text' in content[0]:
                            failure_analysis = content[0]['text']
                        else:
                            failure_analysis = str(content[0])
                    else:
                        failure_analysis = str(content)
                else:
                    failure_analysis = str(response)
                
                return failure_analysis.strip()
            except Exception as e:
                error_msg = str(e)
                # 如果视频太短或其他错误，尝试回退到提取关键帧的方式
                if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                    logger.warning(f"视频文件不符合要求，回退到提取关键帧的方式: {error_msg}")
                    try:
                        frames = extract_frames_from_video(failure_video_path, fps=2.0)
                        if frames:
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{user_content[0]['text']}\n\nKey frames from the failure video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    failure_analysis = message.content
                                else:
                                    failure_analysis = str(message)
                            else:
                                failure_analysis = str(response_obj)
                            
                            return failure_analysis.strip()
                    except Exception as fallback_error:
                        logger.error(f"回退到关键帧方式也失败: {fallback_error}")
                
                logger.error(f"处理Qwen视频失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        else:
            raise ValueError(f"失败视频路径不存在: {failure_video_path}")
    
    elif model_type == "gpt4o":
        # GPT-4o：从obs_images目录加载所有帧
        if obs_images_dir:
            frames = load_all_frames_from_obs_images(obs_images_dir)
            if frames:
                user_content.append({"type": "text", "text": "\nAll frames from the failure video:"})
                for i, frame in enumerate(frames):
                    base64_image = encode_image_base64(frame)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    if (i + 1) % 10 == 0:  # Add a text marker every 10 frames
                        user_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
            else:
                raise ValueError("无法从obs_images目录加载帧")
        else:
            raise ValueError("obs_images目录路径未提供（GPT-4o需要obs_images_dir）")
    elif model_type == "seed":
        # Seed：直接上传视频文件到 Seed API
        if failure_video_path and os.path.exists(failure_video_path):
            from agent_client.llms.seed_utils import upload_video_to_seed
            # 上传视频文件，fps=1.0 表示每秒抽取一帧
            logger.info(f"正在上传失败视频到 Seed API: {failure_video_path}")
            video_file_id = upload_video_to_seed(failure_video_path, fps=1.0)
            logger.info(f"视频上传成功，文件 ID: {video_file_id}")
            
            # 添加视频到用户内容
            user_content.append({
                "type": "video",
                "file_id": video_file_id
            })
        else:
            raise ValueError(f"失败视频路径不存在: {failure_video_path}")
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    # 对于Gemini，需要特殊处理消息格式
    if model_type == "gemini" and isinstance(user_content, list) and len(user_content) > 0 and not isinstance(user_content[0], dict):
        # Gemini使用文件对象，需要直接调用API
        try:
            from agent_client.llms.google_utils import setup_gemini
            client = setup_gemini()
            # user_content格式：[file_object, text_string]
            model_name = llm.model if hasattr(llm, 'model') else "gemini-2.0-flash-exp"
            response = client.models.generate_content(
                model=model_name,
                contents=user_content,
                config={
                    "temperature": 0.7,
                    "system_instruction": {"parts": [{"text": system_prompt}]}
                }
            )
            if hasattr(response, "text"):
                failure_analysis = response.text
            else:
                failure_analysis = str(response)
            return failure_analysis.strip()
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    
    try:
        # 调用LLM
        if hasattr(llm, 'chat'):
            response = llm.chat(messages)
            if isinstance(response, dict) and 'response' in response:
                response_obj = response['response']
            else:
                response_obj = response
        elif hasattr(llm, '__call__'):
            response = llm(messages)
            if isinstance(response, dict) and 'response' in response:
                response_obj = response['response']
            else:
                response_obj = response
        else:
            response_obj = llm(messages)
        
        # Extract text
        # Handle ChatCompletion objects (OpenAI/Qwen format)
        if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
            # OpenAI/Qwen ChatCompletion format
            message = response_obj.choices[0].message
            if hasattr(message, 'content') and message.content:
                failure_analysis = message.content
            elif hasattr(message, 'text'):
                failure_analysis = message.text
            else:
                failure_analysis = str(message)
        elif hasattr(response_obj, 'text'):
            failure_analysis = response_obj.text
        elif isinstance(response_obj, dict) and 'text' in response_obj:
            failure_analysis = response_obj['text']
        elif isinstance(response_obj, str):
            failure_analysis = response_obj
        else:
            failure_analysis = str(response_obj)
        
        return failure_analysis.strip()
    except Exception as e:
        logger.error(f"分析失败视频失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ""


def analyze_expert_video_with_failure_context(
    llm,
    model_type: str,
    game_name: str,
    failure_analysis: str,
    expert_video_path: Optional[str] = None,
    max_length: int = 1000
) -> str:
    """
    第二阶段：基于失败分析，从专家视频中学习经验
    
    Args:
        llm: LLM实例
        model_type: 模型类型
        game_name: 游戏名称
        failure_analysis: 第一阶段的失败分析结果
        expert_video_path: 专家视频路径
        max_length: 经验文本最大长度（单词数或token数，不是字符数）
    
    Returns:
        凝练的经验文本
    """
    system_prompt = f"""You are a game strategy analysis expert. You have analyzed the failure video and understood the failure scenarios and reasons. Now please watch the expert video, learn successful strategies, and summarize experiences that can help avoid the previous failures.

Requirements:
1. Combine the previously analyzed failure scenarios and reasons
2. Observe successful strategies in the expert video
3. Summarize experiences that can avoid failures and improve game performance (no more than {max_length} words or tokens)
4. Experiences should be specific and actionable, avoid vague suggestions
5. Sort by importance, put the most important experiences first
6. **IMPORTANT: Keep your response within {max_length} words or tokens. Be concise and focus on the most critical insights.**

Output format: Plain text, one experience per line, described in concise language."""

    user_content = [
        {"type": "text", "text": f"Game name: {game_name}\n\n"},
        {"type": "text", "text": f"### Previously analyzed failure scenarios and reasons:\n{failure_analysis}\n\n"},
        {"type": "text", "text": "### Expert video:\nPlease watch the following expert video, learn successful strategies, and summarize experiences that can help avoid the previous failures.\n"}
    ]
    
    if model_type == "gemini":
        # Gemini：直接上传视频文件
        if expert_video_path and os.path.exists(expert_video_path):
            try:
                video_file = upload_video_to_gemini(expert_video_path)
                # Gemini使用特殊格式：在contents中直接使用文件对象
                user_content = [video_file, user_content[0]["text"], user_content[1]["text"], user_content[2]["text"]]
            except Exception as e:
                logger.error(f"上传视频到Gemini失败: {e}")
                raise
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    elif model_type == "qwen":
        # Qwen：使用dashscope MultiModalConversation API，通过file://协议传入视频文件绝对路径
        # 这样可以避免base64编码的10MB限制
        if expert_video_path and os.path.exists(expert_video_path):
            try:
                # 获取视频文件的绝对路径
                # Windows 路径需要转换为正斜杠，因为 file:// 协议使用正斜杠
                abs_video_path = os.path.abspath(expert_video_path)
                # 将反斜杠转换为正斜杠
                abs_video_path = abs_video_path.replace('\\', '/')
                video_path = f"file://{abs_video_path}"
                
                # 使用dashscope API直接调用
                if not DASHSCOPE_AVAILABLE:
                    raise ImportError("dashscope package is required for Qwen video analysis. Please install it: pip install dashscope")
                
                api_key = get_qwen_api_key()
                model_name = llm.model if hasattr(llm, 'model') else "qwen3-vl-8b-instruct"
                
                # 构建文本内容
                text_content = f"{user_content[0]['text']}{user_content[1]['text']}{user_content[2]['text']}"
                
                # 构建消息格式
                # 根据 dashscope 文档，需要添加 fps 参数控制视频抽帧数量（每隔1/fps秒抽取一帧）
                messages = [
                    {
                        'role': 'user',
                        'content': [
                            {'video': video_path, 'fps': 2},  # fps=2 表示每隔0.5秒抽取一帧
                            {'text': f"{system_prompt}\n\n{text_content}"}
                        ]
                    }
                ]
                
                # 调用dashscope API
                response = MultiModalConversation.call(
                    api_key=api_key,
                    model=model_name,
                    messages=messages
                )
                
                # 检查响应是否有错误
                if hasattr(response, 'status_code') and response.status_code != 200:
                    error_msg = str(response)
                    # 如果视频太短，回退到提取关键帧的方式
                    if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                        logger.warning(f"视频文件太短，无法直接使用dashscope API，回退到提取关键帧的方式: {error_msg}")
                        # 回退到提取关键帧的方式
                        frames = extract_frames_from_video(expert_video_path, fps=2.0)
                        if frames:
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{text_content}\n\nKey frames from the expert video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    reflection_text = message.content
                                else:
                                    reflection_text = str(message)
                            else:
                                reflection_text = str(response_obj)
                            
                            return reflection_text.strip()
                        else:
                            raise ValueError("无法从专家视频提取帧")
                    else:
                        raise Exception(f"DashScope API调用失败: {error_msg}")
                
                # 解析正常响应
                if response and response.output and response.output.choices:
                    content = response.output.choices[0].message.content
                    if isinstance(content, list) and len(content) > 0:
                        if 'text' in content[0]:
                            reflection_text = content[0]['text']
                        else:
                            reflection_text = str(content[0])
                    else:
                        reflection_text = str(content)
                else:
                    reflection_text = str(response)
                
                return reflection_text.strip()
            except Exception as e:
                error_msg = str(e)
                # 如果视频太短或其他错误，尝试回退到提取关键帧的方式
                if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                    logger.warning(f"视频文件不符合要求，回退到提取关键帧的方式: {error_msg}")
                    try:
                        frames = extract_frames_from_video(expert_video_path, fps=2.0)
                        if frames:
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            text_content = f"{user_content[0]['text']}{user_content[1]['text']}{user_content[2]['text']}"
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{text_content}\n\nKey frames from the expert video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    reflection_text = message.content
                                else:
                                    reflection_text = str(message)
                            else:
                                reflection_text = str(response_obj)
                            
                            return reflection_text.strip()
                    except Exception as fallback_error:
                        logger.error(f"回退到关键帧方式也失败: {fallback_error}")
                
                logger.error(f"处理Qwen视频失败: {e}")
                raise
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    
    elif model_type == "gpt4o":
        # GPT-4o：从专家视频中按2秒1帧提取帧
        if expert_video_path and os.path.exists(expert_video_path):
            frames = extract_frames_from_video(expert_video_path, fps=0.5)  # 2秒1帧
            if frames:
                user_content.append({"type": "text", "text": "\nKey frames from the expert video (1 frame per 2 seconds):"})
                for i, frame in enumerate(frames):
                    base64_image = encode_image_base64(frame)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    if (i + 1) % 5 == 0:  # Add a text marker every 5 frames
                        user_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
            else:
                raise ValueError("无法从专家视频提取帧")
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    elif model_type == "seed":
        # Seed：直接上传视频文件到 Seed API
        if expert_video_path and os.path.exists(expert_video_path):
            from agent_client.llms.seed_utils import upload_video_to_seed
            # 上传视频文件，fps=1.0 表示每秒抽取一帧
            logger.info(f"正在上传专家视频到 Seed API: {expert_video_path}")
            video_file_id = upload_video_to_seed(expert_video_path, fps=1.0)
            logger.info(f"视频上传成功，文件 ID: {video_file_id}")
            
            # 构建文本内容
            text_content = f"{user_content[0]['text']}{user_content[1]['text']}{user_content[2]['text']}"
            user_content = [
                {"type": "text", "text": text_content},
                {
                    "type": "video",
                    "file_id": video_file_id
                }
            ]
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    # 对于Gemini，需要特殊处理消息格式
    if model_type == "gemini" and len(user_content) > 0 and not isinstance(user_content[0], dict):
        # Gemini使用文件对象，需要直接调用API
        try:
            from agent_client.llms.google_utils import setup_gemini
            client = setup_gemini()
            # user_content格式：[file_object, text_string, ...]
            model_name = llm.model if hasattr(llm, 'model') else "gemini-2.0-flash-exp"
            response = client.models.generate_content(
                model=model_name,
                contents=user_content,
                config={
                    "temperature": 0.7,
                    "system_instruction": {"parts": [{"text": system_prompt}]}
                }
            )
            if hasattr(response, "text"):
                reflection_text = response.text
            else:
                reflection_text = str(response)
            # Limit length by word count (approximate, since token counting requires tokenizer)
            words = reflection_text.split()
            if len(words) > max_length:
                # Truncate to max_length words
                reflection_text = ' '.join(words[:max_length]) + "..."
            return reflection_text.strip()
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    
    try:
        # 调用LLM
        if hasattr(llm, 'chat'):
            response = llm.chat(messages)
            if isinstance(response, dict) and 'response' in response:
                response_obj = response['response']
            else:
                response_obj = response
        elif hasattr(llm, '__call__'):
            response = llm(messages)
            if isinstance(response, dict) and 'response' in response:
                response_obj = response['response']
            else:
                response_obj = response
        else:
            response_obj = llm(messages)
        
        # 提取文本
        # 处理 ChatCompletion 对象（OpenAI/Qwen 格式）
        if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
            # OpenAI/Qwen ChatCompletion 格式
            message = response_obj.choices[0].message
            if hasattr(message, 'content') and message.content:
                reflection_text = message.content
            elif hasattr(message, 'text'):
                reflection_text = message.text
            else:
                reflection_text = str(message)
        elif hasattr(response_obj, 'text'):
            reflection_text = response_obj.text
        elif isinstance(response_obj, dict) and 'text' in response_obj:
            reflection_text = response_obj['text']
        elif isinstance(response_obj, str):
            reflection_text = response_obj
        else:
            reflection_text = str(response_obj)
        
        # Limit length by word count (approximate, since token counting requires tokenizer)
        words = reflection_text.split()
        if len(words) > max_length:
            # Truncate to max_length words
            reflection_text = ' '.join(words[:max_length]) + "..."
        
        return reflection_text.strip()
    except Exception as e:
        logger.error(f"分析专家视频失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return ""


def reflect_from_videos(
    llm,
    model_name: str,
    game_name: str,
    failure_video_path: Optional[str] = None,
    expert_video_path: Optional[str] = None,
    obs_images_dir: Optional[str] = None,
    max_length: int = 1000
) -> str:
    """
    从视频中反思并生成经验（两阶段分析）
    
    Args:
        llm: LLM实例
        model_name: 模型名称
        game_name: 游戏名称
        failure_video_path: 失败视频路径
        expert_video_path: 专家视频路径
        obs_images_dir: obs_images目录路径（用于GPT-4o失败视频）
        max_length: 经验文本最大长度（单词数或token数，不是字符数）
    
    Returns:
        凝练的经验文本
    """
    model_type = get_model_type(model_name)
    logger.info(f"使用模型类型: {model_type}")
    
    # 第一阶段：分析失败视频
    logger.info("第一阶段：分析失败视频...")
    failure_analysis = analyze_failure_video(
        llm=llm,
        model_type=model_type,
        game_name=game_name,
        failure_video_path=failure_video_path,
        obs_images_dir=obs_images_dir
    )
    
    if not failure_analysis:
        raise ValueError("失败视频分析失败")
    
    logger.info(f"失败分析结果: {failure_analysis[:1000]}...")
    
    # 消融实验：当专家视频为空时，直接返回失败视频反思
    if not expert_video_path:
        return failure_analysis

    # 检查专家视频是否存在
    if not os.path.exists(expert_video_path):
        raise ValueError(f"专家视频不存在: {expert_video_path}")
    
    # 第二阶段：基于失败分析，从专家视频中学习经验
    logger.info("第二阶段：分析专家视频并生成经验...")
    reflection_text = analyze_expert_video_with_failure_context(
        llm=llm,
        model_type=model_type,
        game_name=game_name,
        failure_analysis=failure_analysis,
        expert_video_path=expert_video_path,
        max_length=max_length
    )
    
    return reflection_text


def reflect_from_multiple_failure_videos(
    llm,
    model_name: str,
    game_name: str,
    failure_video_paths: List[str],
    expert_video_path: Optional[str] = None,
    obs_images_dirs: Optional[List[Optional[str]]] = None,
    max_length: int = 1000,
    merge_reflections_fn: Optional[Callable[[List[str], List[str], str], str]] = None
) -> str:
    """
    Multi-video reflection: generate reflection per failure video, then concatenate.

    Args:
        llm: LLM实例
        model_name: 模型名称
        game_name: 游戏名称
        failure_video_paths: 失败视频路径列表
        expert_video_path: 专家视频路径
        obs_images_dirs: 与 failure_video_paths 对应的 obs_images 目录列表（可选）
        max_length: 经验文本最大长度
        merge_reflections_fn: 拼接函数（由 generate_reflection.py 传入）

    Returns:
        拼接后的整体经验文本
    """
    if not failure_video_paths:
        raise ValueError("failure_video_paths is empty for multi-video reflection")

    if obs_images_dirs and len(obs_images_dirs) < len(failure_video_paths):
        obs_images_dirs = obs_images_dirs + [None] * (len(failure_video_paths) - len(obs_images_dirs))

    per_video_reflections: List[str] = []
    for idx, failure_video_path in enumerate(failure_video_paths, start=1):
        obs_images_dir = None
        if obs_images_dirs and idx - 1 < len(obs_images_dirs):
            obs_images_dir = obs_images_dirs[idx - 1]

        logger.info(f"Multi-video reflection: processing failure video {idx}/{len(failure_video_paths)}")
        reflection_text = reflect_from_videos(
            llm=llm,
            model_name=model_name,
            game_name=game_name,
            failure_video_path=failure_video_path,
            expert_video_path=expert_video_path,
            obs_images_dir=obs_images_dir,
            max_length=max_length
        )

        if reflection_text and reflection_text.strip():
            per_video_reflections.append(reflection_text.strip())

    if not per_video_reflections:
        raise ValueError("Failed to generate any valid reflection from multi-video inputs")

    if merge_reflections_fn:
        return merge_reflections_fn(per_video_reflections, failure_video_paths, game_name)

    # Fallback simple concatenation
    header = [
        f"Multi-video reflection summary for {game_name}.",
        "The following experience is concatenated from multiple failure videos.",
        f"Total failure videos: {len(failure_video_paths)}"
    ]
    body = []
    for i, text in enumerate(per_video_reflections, start=1):
        body.append(f"\n[Reflection from failure video {i}]\n{text}")
    return "\n".join(header) + "\n" + "\n".join(body)


def find_expert_video(game_name: str, log_path: str) -> Optional[str]:
    """
    查找专家视频（skill_video或playthrough_video）
    
    Args:
        game_name: 游戏名称
        log_path: 当前日志路径
    
    Returns:
        专家视频路径，如果不存在则返回None
    """
    # 可能的专家视频位置
    possible_paths = [
        os.path.join("data", "expert_videos", game_name, "skill_video.mp4"),
        os.path.join("data", "expert_videos", game_name, "playthrough_video.mp4"),
        os.path.join("data", "expert_videos", game_name, "expert.mp4"),
        os.path.join("data", "expertvideo", game_name, "skill_video.mp4"),
        os.path.join("data", "expertvideo", game_name, "playthrough_video.mp4"),
        os.path.join("data", "expertvideo", game_name, "expert.mp4"),
    ]
    
    # 从项目根目录查找
    project_root = Path(log_path).resolve()
    # 向上查找项目根目录（包含src目录的目录）
    while project_root.parent != project_root:
        if (project_root / "src").exists():
            break
        project_root = project_root.parent
    
    for rel_path in possible_paths:
        full_path = project_root / rel_path
        if full_path.exists():
            return str(full_path)
    
    # 也尝试查找expertvideo目录下的所有mp4文件（包括子目录）
    expertvideo_dir = project_root / "data" / "expertvideo" / game_name
    if expertvideo_dir.exists():
        # 先查找直接在该目录下的mp4文件
        video_files = list(expertvideo_dir.glob("*.mp4"))
        if video_files:
            return str(video_files[0])
        
        # 如果没找到，递归查找子目录中的mp4文件
        video_files = list(expertvideo_dir.glob("**/*.mp4"))
        if video_files:
            # 优先返回 playthrough_video.mp4，如果没有则返回第一个找到的
            playthrough_videos = [f for f in video_files if f.name == "playthrough_video.mp4"]
            if playthrough_videos:
                return str(playthrough_videos[0])
            return str(video_files[0])
    
    return None


def extract_milestones_from_expert_video(
    llm,
    model_type: str,
    game_name: str,
    expert_video_path: Optional[str] = None
) -> Dict:
    """
    从专家视频中提取游戏里程碑
    
    Args:
        llm: LLM实例
        model_type: 模型类型（"gemini", "qwen", "gpt4o"等）
        game_name: 游戏名称
        expert_video_path: 专家视频路径
    
    Returns:
        包含里程碑的字典，格式为 {"milestones": [...]}
    """
    system_prompt = f"""You are a game milestone identifier. Please carefully watch this {game_name} playthrough video (including frame sequences and possibly game audio and commentary audio), identify and list in chronological order all milestone events where player actions are crucial to game progress. Please base your analysis on the video content itself.

Requirements:

1. Milestones should be meaningful game progress nodes, including: first time completing an operation, making important decisions, completing levels, reaching save points, obtaining important items, unlocking important abilities, meeting new characters, defeating important enemies, entering new major areas, completing key steps.

2. Each milestone should include: timestamp range (min.sec - min.sec), milestone name, detailed description, category, importance

3. Arrange in chronological order

4. Descriptions should be specific and detailed, including content summary and specific context

5. Ensure each milestone represents a single, distinct event.

Please return in JSON format as follows:

{{
    "milestones": [
        {{
            "timestamp": "123.45 - 127.46",
            "title": "Complete Level 1",
            "description": "Complete Level 1: After defeating the boss, the player obtains a new weapon, character health is full, and unlocks new skills",
            "category": "Level Completion",
            "importance": "High"
        }},
        {{
            "timestamp": "234.56 - 241.57",
            "title": "Defeat First Boss",
            "description": "Defeat Boss: Defeat the first Boss, gain experience points and gold rewards",
            "category": "Boss Defeat",
            "importance": "High"
        }},
        {{
            "timestamp": "345.67 - 412.57",
            "title": "Obtain Rare Item X",
            "description": "Obtain Rare Item: Discover hidden treasure chest and obtain rare item",
            "category": "Item Acquisition",
            "importance": "Medium"
        }}
    ]
}}

Please ensure the JSON format is correct and timestamps are accurate to seconds."""

    user_content = [{"type": "text", "text": f"Game name: {game_name}\n\nPlease carefully watch this playthrough video and identify and list all milestone events in chronological order.\n"}]
    
    if model_type == "gemini":
        # Gemini：直接上传视频文件
        if expert_video_path and os.path.exists(expert_video_path):
            try:
                video_file = upload_video_to_gemini(expert_video_path)
                # Gemini使用特殊格式：在contents中直接使用文件对象和文本
                text_content = user_content[0]["text"]
                user_content = [video_file, text_content]
            except Exception as e:
                logger.error(f"上传视频到Gemini失败: {e}")
                raise
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    elif model_type == "qwen":
        # Qwen：使用dashscope MultiModalConversation API，通过file://协议传入视频文件绝对路径
        # 这样可以避免base64编码的10MB限制
        if expert_video_path and os.path.exists(expert_video_path):
            try:
                # 获取视频文件的绝对路径
                # Windows 路径需要转换为正斜杠，因为 file:// 协议使用正斜杠
                abs_video_path = os.path.abspath(expert_video_path)
                # 将反斜杠转换为正斜杠
                abs_video_path = abs_video_path.replace('\\', '/')
                video_path = f"file://{abs_video_path}"
                
                # 使用dashscope API直接调用
                if not DASHSCOPE_AVAILABLE:
                    raise ImportError("dashscope package is required for Qwen video analysis. Please install it: pip install dashscope")
                
                api_key = get_qwen_api_key()
                model_name = llm.model if hasattr(llm, 'model') else "qwen3-vl-8b-instruct"
                
                # 构建消息格式
                # 根据 dashscope 文档，需要添加 fps 参数控制视频抽帧数量（每隔1/fps秒抽取一帧）
                messages = [
                    {
                        'role': 'user',
                        'content': [
                            {'video': video_path, 'fps': 2},  # fps=2 表示每隔0.5秒抽取一帧
                            {'text': f"{system_prompt}\n\n{user_content[0]['text']}"}
                        ]
                    }
                ]
                
                # 调用dashscope API
                response = MultiModalConversation.call(
                    api_key=api_key,
                    model=model_name,
                    messages=messages
                )
                
                # 检查响应是否有错误
                if hasattr(response, 'status_code') and response.status_code != 200:
                    error_msg = str(response)
                    # 如果视频太短，回退到提取关键帧的方式
                    if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                        logger.warning(f"视频文件太短，无法直接使用dashscope API，回退到提取关键帧的方式: {error_msg}")
                        # 回退到提取关键帧的方式
                        frames = extract_frames_from_video(expert_video_path, fps=2.0)
                        if frames:
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{user_content[0]['text']}\n\nKey frames from the expert video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    result_text = message.content
                                else:
                                    result_text = str(message)
                            else:
                                result_text = str(response_obj)
                            
                            # 尝试解析JSON格式的里程碑
                            try:
                                milestones = json.loads(result_text)
                                return milestones
                            except json.JSONDecodeError:
                                logger.warning("Qwen返回的不是JSON格式，返回原始文本")
                                return {"milestones": [{"timestamp": 0, "description": result_text}]}
                        else:
                            raise ValueError("无法从专家视频提取帧")
                    else:
                        raise Exception(f"DashScope API调用失败: {error_msg}")
                
                # 解析正常响应
                if response and response.output and response.output.choices:
                    content = response.output.choices[0].message.content
                    if isinstance(content, list) and len(content) > 0:
                        if 'text' in content[0]:
                            result_text = content[0]['text']
                        else:
                            result_text = str(content[0])
                    else:
                        result_text = str(content)
                else:
                    result_text = str(response)
                
                # 尝试解析JSON格式的里程碑
                try:
                    milestones = json.loads(result_text)
                    return milestones
                except json.JSONDecodeError:
                    # 如果不是JSON格式，返回原始文本
                    logger.warning("Qwen返回的不是JSON格式，返回原始文本")
                    return {"milestones": [{"timestamp": 0, "description": result_text}]}
            except Exception as e:
                error_msg = str(e)
                # 如果视频太短或其他错误，尝试回退到提取关键帧的方式
                if 'too short' in error_msg.lower() or 'does not meet the requirements' in error_msg.lower():
                    logger.warning(f"视频文件不符合要求，回退到提取关键帧的方式: {error_msg}")
                    try:
                        frames = extract_frames_from_video(expert_video_path, fps=2.0)
                        if frames:
                            if len(frames) > 60:
                                indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                                frames = [frames[i] for i in indices]
                            
                            frame_content = [{"type": "text", "text": f"{system_prompt}\n\n{user_content[0]['text']}\n\nKey frames from the expert video:"}]
                            for i, frame in enumerate(frames):
                                base64_image = encode_image_base64(frame)
                                frame_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                                })
                                if (i + 1) % 10 == 0:
                                    frame_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
                            
                            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": frame_content}]
                            response_obj = llm.chat(messages)
                            
                            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                                message = response_obj.choices[0].message
                                if hasattr(message, 'content') and message.content:
                                    result_text = message.content
                                else:
                                    result_text = str(message)
                            else:
                                result_text = str(response_obj)
                            
                            # 尝试解析JSON格式的里程碑
                            try:
                                milestones = json.loads(result_text)
                                return milestones
                            except json.JSONDecodeError:
                                logger.warning("Qwen返回的不是JSON格式，返回原始文本")
                                return {"milestones": [{"timestamp": 0, "description": result_text}]}
                    except Exception as fallback_error:
                        logger.error(f"回退到关键帧方式也失败: {fallback_error}")
                
                logger.error(f"处理Qwen视频失败: {e}")
                raise
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    elif model_type == "gpt4o":
        # GPT-4o：从专家视频中提取关键帧
        if expert_video_path and os.path.exists(expert_video_path):
            frames = extract_frames_from_video(expert_video_path, fps=2.0)  # 1秒1帧
            if frames:
                # 如果帧数太多，均匀采样
                if len(frames) > 60:
                    indices = np.linspace(0, len(frames) - 1, 60, dtype=int)
                    frames = [frames[i] for i in indices]
                
                user_content.append({"type": "text", "text": "\nKey frames from the expert video:"})
                for i, frame in enumerate(frames):
                    base64_image = encode_image_base64(frame)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    if (i + 1) % 10 == 0:
                        user_content.append({"type": "text", "text": f"(Displayed {i+1} frames)"})
            else:
                raise ValueError("无法从专家视频提取帧")
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    elif model_type == "seed":
        # Seed：直接上传视频文件到 Seed API
        if expert_video_path and os.path.exists(expert_video_path):
            from agent_client.llms.seed_utils import upload_video_to_seed
            # 上传视频文件，fps=1.0 表示每秒抽取一帧
            logger.info(f"正在上传专家视频到 Seed API（里程碑提取）: {expert_video_path}")
            video_file_id = upload_video_to_seed(expert_video_path, fps=1.0)
            logger.info(f"视频上传成功，文件 ID: {video_file_id}")
            
            # 添加视频到用户内容
            user_content.append({
                "type": "video",
                "file_id": video_file_id
            })
        else:
            raise ValueError(f"专家视频路径不存在: {expert_video_path}")
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    # 对于Gemini，需要特殊处理消息格式
    if model_type == "gemini" and len(user_content) > 0 and not isinstance(user_content[0], dict):
        # Gemini使用文件对象，需要直接调用API
        try:
            from agent_client.llms.google_utils import setup_gemini
            client = setup_gemini()
            # user_content格式：[file_object, text_string]
            model_name = llm.model if hasattr(llm, 'model') else "gemini-2.0-flash-exp"
            response = client.models.generate_content(
                model=model_name,
                contents=user_content,
                config={
                    "temperature": 0.7,
                    "system_instruction": {"parts": [{"text": system_prompt}]}
                }
            )
            if hasattr(response, "text"):
                response_text = response.text
            else:
                response_text = str(response)
        except Exception as e:
            logger.error(f"Gemini API调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"milestones": []}
    else:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
        
        try:
            # 调用LLM
            if hasattr(llm, 'chat'):
                response = llm.chat(messages)
                if isinstance(response, dict) and 'response' in response:
                    response_obj = response['response']
                else:
                    response_obj = response
            elif hasattr(llm, '__call__'):
                response = llm(messages)
                if isinstance(response, dict) and 'response' in response:
                    response_obj = response['response']
                else:
                    response_obj = response
            else:
                response_obj = llm(messages)
            
            # 提取文本
            # 处理 ChatCompletion 对象（OpenAI/Qwen 格式）
            if hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                # OpenAI/Qwen ChatCompletion 格式
                message = response_obj.choices[0].message
                if hasattr(message, 'content') and message.content:
                    response_text = message.content
                elif hasattr(message, 'text'):
                    response_text = message.text
                else:
                    response_text = str(message)
            elif hasattr(response_obj, 'text'):
                response_text = response_obj.text
            elif isinstance(response_obj, dict) and 'text' in response_obj:
                response_text = response_obj['text']
            elif isinstance(response_obj, str):
                response_text = response_obj
            else:
                response_text = str(response_obj)
        except Exception as e:
            logger.error(f"提取里程碑失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"milestones": []}
    
    # 尝试解析JSON
    try:
        import re
        # 1. 尝试提取markdown代码块中的JSON（如果存在）
        json_code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response_text, re.IGNORECASE)
        if json_code_block_match:
            response_text = json_code_block_match.group(1)
        else:
            # 2. 尝试提取第一个完整的JSON对象
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group(0)
        
        # 3. 修复常见的JSON格式问题
        # JSON中单引号不需要转义，但LLM可能返回 \'，需要修复为 '
        # 注意：JSON字符串内的单引号不需要转义，所以 \' 应该被替换为 '
        # 直接替换 \' 为 '（在JSON中这是安全的，因为单引号在字符串内不需要转义）
        # 但要避免替换 \\'（双反斜杠加单引号，虽然这种情况很少见）
        # 使用负向后顾断言确保前面不是反斜杠
        response_text = re.sub(r'(?<!\\)\\\'', "'", response_text)
        
        # 4. 尝试解析JSON
        milestones_data = json.loads(response_text)
        if "milestones" not in milestones_data:
            milestones_data = {"milestones": milestones_data}
        return milestones_data
    except json.JSONDecodeError as e:
        logger.error(f"解析JSON失败: {e}")
        logger.error(f"响应文本（前1000字符）: {response_text[:1000]}")
        # 尝试使用更宽松的方式：使用ast.literal_eval或直接正则提取
        try:
            # 尝试使用正则表达式直接提取milestones数组
            milestones_match = re.search(r'"milestones"\s*:\s*\[([\s\S]*?)\]', response_text)
            if milestones_match:
                logger.warning("使用正则表达式提取milestones，可能不完整")
                # 这里可以尝试更复杂的解析，但为了简单起见，返回空列表
                return {"milestones": []}
        except Exception as e2:
            logger.error(f"备用解析方法也失败: {e2}")
        return {"milestones": []}
