import json
import os

import faiss
import numpy as np

from dreamcraft.domain.quest import Quest
import pickle

from dreamcraft.domain.snapshot import Snapshot


class snapshotRepo:
    def __init__(self, settings):
        self.dim = settings.embedding_dimension
        self.json_path = settings.snapshot_documents_path
        self.faiss_index_path = settings.snapshot_faiss_index_path

        self.snapshots: list[Snapshot] = self.load_snapshots_from_json(self.json_path)
        self.faiss_index = self.load_faiss_index(self.faiss_index_path)
        

    def load_snapshots_from_json(self, json_path):
        if not json_path.exists():
            return []
        
        if os.path.getsize(json_path) == 0:
            print(f"警告: {json_path} 是空的，返回空列表")
            return []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                snapshots = json.load(f)
            return [Snapshot(**ss) for ss in snapshots]
        except json.JSONDecodeError:
            print(f"错误: {json_path} 格式非法")
            return []
        
    def save_snapshots_to_json(self, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([ss.dict for ss in self.snapshots], f, ensure_ascii=False, indent=4)
    
    def load_faiss_index(self, index_path):
        if not index_path.exists():
            faiss_index = faiss.IndexFlatL2(self.dim)
            return faiss_index
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def save_faiss_index(self, index_path):
        faiss.write_index(self.faiss_index, str(index_path))

    def add(self, snapshot: Snapshot, embeddings: np.ndarray) -> int:
        """添加新的快照数据。"""
        self.snapshots.append(snapshot)
        self.faiss_index.add(embeddings)
        self.save_snapshots_to_json(self.json_path)
        self.save_faiss_index(self.faiss_index_path)
        return len(self.snapshots) - 1
    
    def remove(self, snapshot_refs: list[int | Snapshot]):
        snapshot_ids = []
        for ref in snapshot_refs:
            if isinstance(ref, int):
                snapshot_ids.append(ref)
            elif isinstance(ref, Snapshot):
                try:
                    snapshot_id = self.snapshots.index(ref)
                    snapshot_ids.append(snapshot_id)
                except ValueError:
                    print(f"警告: 快照 {ref} 不在仓库中，无法删除")
            else:
                raise ValueError("Snapshot reference must be either int (ID) or Snapshot instance")
        """根据快照 ID 删除快照数据。"""
        for snapshot_id in snapshot_ids:
            if snapshot_id < 0 or snapshot_id >= len(self.snapshots):
                raise IndexError("Snapshot ID out of range")
        
        for snapshot_id in sorted(snapshot_ids, reverse=True):
            del self.snapshots[snapshot_id]
        self.faiss_index.remove_ids(np.array(snapshot_ids))
        self.save_snapshots_to_json(self.json_path)
        self.save_faiss_index(self.faiss_index_path)

    def get(self, snapshot_id: int) -> Snapshot:
        """根据快照 ID 获取快照数据。"""
        if snapshot_id < 0 or snapshot_id >= len(self.snapshots):
            raise IndexError("Snapshot ID out of range")
        return self.snapshots[snapshot_id]
    
    def get_id(self, snapshot: Snapshot) -> int:
        """根据快照数据获取快照 ID。"""
        try:
            snapshot_id = self.snapshots.index(snapshot)
            return snapshot_id
        except ValueError:
            raise ValueError("Snapshot not found in repository")
        
    def query(self, query_embedding, top_k=3) -> list[Snapshot]:
        """根据查询向量获取最相关的快照数据。"""
        actual_k = min(top_k, len(self.snapshots))
        distances, indices = self.faiss_index.search(query_embedding, actual_k)
        return [self.snapshots[i] for i in indices[0]]