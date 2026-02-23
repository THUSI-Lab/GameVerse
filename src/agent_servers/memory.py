from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import uuid
import logging
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from agent_servers.setup_openai import setup_openai

logger = logging.getLogger(__name__)

setup_openai()


def get_embedding_function(embedding_model: Optional[str] = None, embedding_config: Optional[Dict] = None):
    """
    根据配置创建embedding函数
    
    Args:
        embedding_model: embedding模型类型，可选值: "openai", "qwen", None(默认使用openai)
        embedding_config: embedding配置字典，可包含model, dimensions, api_key等参数
    
    Returns:
        embedding函数实例
    """
    if embedding_config is None:
        embedding_config = {}
    
    # 默认使用openai
    if embedding_model is None or embedding_model.lower() == "openai":
        logger.info("Using OpenAI embeddings")
        return OpenAIEmbeddings(**embedding_config)
    elif embedding_model.lower() == "qwen":
        logger.info("Using Qwen embeddings")
        from agent_servers.qwen_embeddings import QwenEmbeddings
        return QwenEmbeddings(**embedding_config)
    else:
        logger.warning(f"Unknown embedding model: {embedding_model}, falling back to OpenAI")
        return OpenAIEmbeddings(**embedding_config)


class GenericMemory:
    def __init__(self, path: str, embedding_model: Optional[str] = None, embedding_config: Optional[Dict] = None):
        """
        初始化GenericMemory
        
        Args:
            path: 日志路径
            embedding_model: embedding模型类型，可选值: "openai", "qwen", None(默认使用openai)
            embedding_config: embedding配置字典，可包含model, dimensions, api_key等参数
        """
        self.memories: Dict[str, List[Any]] = {}
        self.histories = []

        # long-term memory
        self.save_path = f"data/long_term_memory/{path.replace('logs/', '', 1)}/"
        
        # 根据配置创建embedding函数
        embedding_function = get_embedding_function(embedding_model, embedding_config)
        
        self.vectordb = Chroma(
            collection_name="long_term_memory",
            embedding_function=embedding_function,
            persist_directory=self.save_path,
        )
        self.retrieval_top_k = 3
        
        # Pokemon specific
        self.map_memory_dict = {}
        self.state_dict = {}
        self.dialog_buffer = []
        self.step_count = 0
        self.environment_perception = ''
        self.num_action_buffer = 5
        self.num_history_buffer = 20
        
    def add(self, key: str, value: Any) -> None:
        if key not in self.memories:
            self.memories[key] = []
        self.memories[key].append(value)
    
    def get_all(self, key: str) -> List[Any]:
        return self.memories.get(key, [])
    
    def get_last(self, key: str) -> Any:
        values = self.memories.get(key, [])
        return values[-1] if values else None

    def is_exist(self, key: str) -> bool:
        return key in self.memories
    
    def clear(self) -> None:
        self.memories = {}
    
    def save_to_file(self, filepath: str) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str) -> None:
        with open(filepath, 'r', encoding='utf-8') as f:
            self.memories = json.load(f)

    def add_long_term_memory(self, content: str, similarity_threshold: float = 0.8) -> None:
        if not content:
            return

        results = self.vectordb.similarity_search_with_score(content, k=1)

        if results:
            _, score = results[0]
            if score <= similarity_threshold:
                logger.info(f"The new memory is too similar ({score}<={similarity_threshold}) to an existing memory and will not be saved.")
                return

        mem_id = str(uuid.uuid4())
        self.vectordb.add_texts(
            texts=[content],
            ids=[mem_id],
            metadatas=[{"id": mem_id}],
        )
        self.add("long_term_memory", content)

    def retrieve_long_term_memory(self, query: str, save_to_file: bool = False, similarity_threshold: float = 0.8) -> str:
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0 or not query:
            return None
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        # Filter documents with similarity score <= 0.8
        filtered_docs = [(doc, score) for doc, score in docs_and_scores if score <= similarity_threshold]
        retrieved_contents = "\n".join([f"{i+1}: {doc.page_content}" for i, (doc, _) in enumerate(filtered_docs)])
        if retrieved_contents == "":
            return None
        
        if save_to_file:
            with open(f'{self.save_path}retrieved_memory.txt', 'w+', encoding='utf-8') as file:
                file.write(retrieved_contents)
        
        return retrieved_contents
