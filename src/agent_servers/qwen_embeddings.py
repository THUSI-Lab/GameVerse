"""
Qwen Embeddings implementation for langchain compatibility
支持通义千问的text-embedding模型
"""
import os
from typing import List, Optional
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


def _get_qwen_api_key(api_key: Optional[str] = None) -> str:
    """
    获取Qwen API密钥，支持多种方式：
    1. 直接传入的api_key参数
    2. 环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY
    3. 从文件 src/agent_servers/keys/qwen-key/key.env 读取
    
    Args:
        api_key: 直接指定的API密钥
        
    Returns:
        API密钥字符串
    """
    # 如果直接传入了api_key，优先使用
    if api_key:
        return api_key
    
    # 尝试从环境变量获取
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    if api_key:
        return api_key
    
    # 尝试从文件读取
    script_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(script_dir, "keys/qwen-key/key.env")
    
    if os.path.exists(key_path):
        try:
            with open(key_path, "r", encoding='utf-8') as f:
                api_key = f.read().strip()
            if api_key:
                logger.info(f"Loaded Qwen API key from {key_path}")
                return api_key
        except Exception as e:
            logger.debug(f"Failed to read key from {key_path}: {e}")
    
    raise ValueError(
        "Qwen API key not found. Please set DASHSCOPE_API_KEY environment variable, "
        "place key in src/agent_servers/keys/qwen-key/key.env, or pass api_key parameter."
    )


class QwenEmbeddings:
    """
    Qwen Embeddings类，兼容langchain的embedding接口
    使用通义千问的text-embedding-v4模型
    """
    
    def __init__(
        self,
        model: str = "text-embedding-v4",
        dimensions: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ):
        """
        初始化Qwen Embeddings
        
        Args:
            model: embedding模型名称，默认为text-embedding-v4
            dimensions: 向量维度，如果为None则默认使用1536（与OpenAI text-embedding-ada-002保持一致）
            api_key: DashScope API密钥，如果为None则从环境变量获取
            base_url: API基础URL
        """
        self.model = model
        # 如果未指定维度，默认使用1024维
        self.dimensions = dimensions if dimensions is not None else 1024
        
        # 获取API密钥
        api_key = _get_qwen_api_key(api_key)
        
        # 创建OpenAI兼容客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        logger.info(f"Initialized QwenEmbeddings with model: {model}, dimensions: {self.dimensions}")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        对文档列表进行embedding
        
        Args:
            texts: 文本列表
            
        Returns:
            embedding向量列表
        """
        if not texts:
            return []
        
        try:
            # 准备请求参数
            request_params = {
                "model": self.model,
                "input": texts
            }
            
            # 如果指定了维度，添加到参数中（text-embedding-v4支持自定义维度）
            if self.dimensions is not None:
                request_params["dimensions"] = self.dimensions
            
            # 调用API
            response = self.client.embeddings.create(**request_params)
            
            # 提取embedding向量
            embeddings = [item.embedding for item in response.data]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        对单个查询文本进行embedding
        
        Args:
            text: 查询文本
            
        Returns:
            embedding向量
        """
        embeddings = self.embed_documents([text])
        return embeddings[0] if embeddings else []
    
    def __call__(self, texts: List[str]) -> List[List[float]]:
        """
        支持直接调用，兼容langchain接口
        """
        return self.embed_documents(texts)

