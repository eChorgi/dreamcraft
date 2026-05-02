import json
import faiss
import numpy as np
class SkillDoc:
    def __init__(self, name: str, desc: str, impact: dict):
        self.name = name
        self.desc = desc
        self.impact = impact

class SkillRepo:
    def __init__(self, settings):
        self.documents = self.load_documents_from_json(settings.skill_documents_path)
        self.embeddings = self.load_embeddings_from_npy(settings.skill_embeddings_npy_path)
        self.faiss_index = self.load_faiss_index(settings.skill_faiss_index_path)

    def load_documents_from_json(self, json_path):

        if not json_path.exists():
            return []  # 如果文件不存在，返回空列表
        with open(json_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        return documents

    def load_embeddings_from_npy(self, npy_path):
        if not npy_path.exists():
            return np.empty((0, 1536), dtype='float32')  # 如果文件不存在，返回空数组
        embeddings = np.load(str(npy_path))
        return embeddings

    def load_faiss_index(self, index_path):
        if not index_path.exists():
            # 如果索引文件不存在，创建一个新的空索引
            faiss_index = faiss.IndexFlatL2(1536)  # 假设使用 L2 距离，维度为 1536
            return faiss_index
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def save_documents_to_json(self, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=4)
    
    def save_embeddings_to_npy(self, npy_path):
        np.save(str(npy_path), self.embeddings)
    
    def save_faiss_index(self, index_path):
        faiss.write_index(self.faiss_index, str(index_path))
    
    def search(self, query_embedding, top_k=5) -> list[dict]:
        distances, indices = self.faiss_index.search(query_embedding, top_k)
        return [self.documents[i] for i in indices[0]]

    def add_skill(self, skill_doc: SkillDoc):
        """添加新技能到知识库，并更新 FAISS 索引和文档列表"""
        # 1. 将 skill_map 转换为文本描述
        skill_text = json.dumps({
            "name": skill_doc.name,
            "desc": skill_doc.desc,
            "impact": skill_doc.impact
        })  # 简单示例，实际可设计更丰富的文本格式
        
        # 2. 生成技能的向量表示
        skill_embedding = self.llm.embed(skill_text).reshape(1, -1).astype('float32')
        
        # 3. 添加到文档列表和 FAISS 索引,并更新 embeddings 数组
        self.documents.append(skill_doc)
        self.faiss_index.add(skill_embedding)
        self.embeddings = np.vstack([self.embeddings, skill_embedding])  # 更新 embeddings 数组