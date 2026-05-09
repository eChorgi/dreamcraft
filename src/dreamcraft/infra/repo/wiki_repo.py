import json
import faiss
import asyncio

from dreamcraft.domain import WikiDocument
from dreamcraft.utils import grep


class WikiRepo:
    def __init__(self, settings):
        self.md_path = settings.wiki_md_path
        self.documents_path = settings.wiki_documents_path
        self.faiss_index_path = settings.wiki_faiss_index_path
        self.documents: list[WikiDocument] = []
        self.faiss_index: faiss.Index = None
        
    async def load(self):
        doc_task = asyncio.to_thread(self.load_documents_from_json, self.documents_path)
        faiss_task = asyncio.to_thread(self.load_faiss_index, self.faiss_index_path)
        self.documents, self.faiss_index = await asyncio.gather(doc_task, faiss_task)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.documents[key]
        else:
            raise KeyError("Key must be an integer index")

    def load_documents_from_json(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        return [WikiDocument(**doc) for doc in documents]   

    def load_faiss_index(self, index_path):
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def query(self, query_embedding, top_k=3) -> list[dict]:
        actual_k = min(top_k, len(self.documents))
        distances, indices = self.faiss_index.search(query_embedding, actual_k)
        return [
            {
                "document": self.documents[i],
                # 如果你想让 LLM 更容易理解，可以把距离转化成相似度得分
                "l2_distance": distances[0][j]
            }
            for j, i in enumerate(indices[0])
            if i != -1  # FAISS 在搜索结果不足时会返回 -1，建议过滤掉
        ]

    def grep_files(self, pattern: str, max_results: int = 5) -> list[dict]:
        return grep.grep_files(pattern, self.md_path, "*.md", max_results)

    def read_section(self, file_name: str, section_title: str) -> str:
        """根据章节标题读取对应的内容，适用于章节标题唯一的情况"""
        if not file_name.endswith(".md"):
            file_name += ".md"
        if " " in file_name:
            file_name = file_name.replace(" ", "_")
        section_title = section_title.replace("#", "").strip()  # 去掉可能的 Markdown 标题符号和多余空格
        return grep.read_md_section(self.md_path / file_name, section_title)