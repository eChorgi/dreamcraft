import json
import faiss
import numpy as np

from dreamcraft.domain.wiki_models import WikiDocument


class WikiRepo:
    def __init__(self, settings):
        self.documents:list[WikiDocument] = self.load_documents_from_json(settings.wiki_documents_path)
        self.faiss_index = self.load_faiss_index(settings.wiki_faiss_index_path)

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
    
    def query(self, query_embedding, top_k=3) -> list[WikiDocument]:
        actual_k = min(top_k, len(self.documents))
        distances, indices = self.faiss_index.search(query_embedding, actual_k)
        return [self.documents[i] for i in indices[0]]