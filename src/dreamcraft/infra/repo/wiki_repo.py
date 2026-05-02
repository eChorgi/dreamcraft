import json
import faiss
import numpy as np


class WikiRepo:
    def __init__(self, settings):
        self.documents = self.load_documents_from_json(settings.wiki_documents_path)
        self.embeddings = self.load_embeddings_from_npy(settings.wiki_embeddings_npy_path)
        self.faiss_index = self.load_faiss_index(settings.wiki_faiss_index_path)

    def load_documents_from_json(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            documents = json.load(f)
        return documents

    def load_embeddings_from_npy(self, npy_path):
        embeddings = np.load(str(npy_path))
        return embeddings

    def load_faiss_index(self, index_path):
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def search(self, query_embedding, top_k=5) -> list[dict]:
        distances, indices = self.faiss_index.search(query_embedding, top_k)
        return [self.documents[i] for i in indices[0]]