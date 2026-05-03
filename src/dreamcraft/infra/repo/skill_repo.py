import json
import os
import faiss
import numpy as np
from dreamcraft.domain.skill import Skill

class SkillRepo:
    def __init__(self, settings):
        self.dim = settings.embedding_dimension
        self.json_path = settings.skill_documents_path
        self.faiss_index_path = settings.skill_faiss_index_path

        self.skills: list[Skill] = self.load_skills_from_json(self.json_path)
        self.skills_dict = {skill.name: skill for skill in self.skills}
        self.faiss_index = self.load_faiss_index(self.faiss_index_path)
        
    def __getitem__(self, key: str | int) -> Skill:
        if isinstance(key, int):
            return self.skills[key]
        elif isinstance(key, str):
            return self.skills_dict[key]
        else:
            raise KeyError("Key must be either int (index) or str (skill name)")


    def load_skills_from_json(self, json_path):
        if not json_path.exists():
            return []
        
        if os.path.getsize(json_path) == 0:
            print(f"警告: {json_path} 是空的，返回空列表")
            return []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            return [Skill(**doc) for doc in skills]
        except json.JSONDecodeError:
            print(f"错误: {json_path} 格式非法")
            return []
    
    def load_faiss_index(self, index_path):
        if not index_path.exists():
            faiss_index = faiss.IndexFlatL2(self.dim)
            return faiss_index
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def save_skills_to_json(self, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([doc.dict for doc in self.skills], f, ensure_ascii=False, indent=4)

    def save_faiss_index(self, index_path):
        faiss.write_index(self.faiss_index, str(index_path))
    
    def query(self, query_embedding, top_k=3) -> list[dict]:
        actual_k = min(top_k, len(self.skills))
        distances, indices = self.faiss_index.search(query_embedding, actual_k)
        return [
            {
                "document": self.skills[i],
                "l2_distance": distances[0][j]
            }
            for j, i in enumerate(indices[0])
            if i != -1  # FAISS 在搜索结果不足时会返回 -1，建议过滤掉
        ]

    def add(self, skill: Skill, skill_embedding: np.ndarray):
        """添加新技能到知识库，并更新 FAISS 索引和文档列表"""
        self.skills.append(skill)
        self.skills_dict[skill.name] = skill
        self.faiss_index.add(skill_embedding)
        self.save_skills_to_json(self.json_path)
        self.save_faiss_index(self.faiss_index_path)
    
    def get(self, ref: int | str) -> Skill:
        """根据索引或技能名称获取技能信息"""
        if isinstance(ref, int):
            return self.skills[ref]
        elif isinstance(ref, str):
            return self.skills_dict.get(ref)
        else:
            raise KeyError("Reference must be either int (index) or str (skill name)")