from typing import Dict, List, Any, Optional
import json
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from agent_servers.setup_openai import setup_openai
from agent_servers.memory import get_embedding_function

setup_openai()

class SkillManager:
    def __init__(self, path, embedding_model: Optional[str] = None, embedding_config: Optional[Dict] = None):
        """
        初始化SkillManager
        
        Args:
            path: 日志路径
            embedding_model: embedding模型类型，可选值: "openai", "qwen", None(默认使用openai)
            embedding_config: embedding配置字典，可包含model, dimensions, api_key等参数
        """
        self.save_path = f"data/skills/{path.replace('logs/', '', 1)}/"
        self.skills: Dict[str, List[Any]] = {}
        
        # 根据配置创建embedding函数
        embedding_function = get_embedding_function(embedding_model, embedding_config)
        
        self.vectordb = Chroma(
            collection_name="skill_vectordb",
            embedding_function=embedding_function,
            persist_directory=self.save_path,
        )
        self.retrieval_top_k = 5
    
    def add_new_skill(self, skill_name: str, skill: str, description: str) -> None:
        if all((skill_name, skill, description)): # if all not None
            self.skills[skill_name] = {
                "skill": skill,
                "description": description,
            }
            self.vectordb.add_texts(
                texts=[description],
                ids=[skill_name],
                metadatas=[{"name": skill_name}],
            )
            assert self.vectordb._collection.count() == len(
                self.skills
            ), "vectordb is not synced with skills dictionary"
    
    def retrieve_skills(self, query: str) -> str:
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0 or query is None:
            return ""
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        
        retrieved_skill_names = [doc.metadata['name'] for doc, _ in docs_and_scores]
        retrieved_skills = '\n\n'.join([self.skills[name]["skill"] for name in retrieved_skill_names])

        # save retrieved_skills.txt
        with open(f'{self.save_path}retrieved_skills.txt', 'w+') as file:
            file.write(retrieved_skills)

        return retrieved_skills