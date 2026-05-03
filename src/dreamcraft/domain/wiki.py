import json
from typing import Literal


class WikiDocument:
    def __init__(self, path: list[str] = None, content: str = None, type: Literal["text", "table", None] = None, chunk_index: int = None):
        self.path = path
        self.content = content
        self.type = type
        self.chunk_index = chunk_index

    def __repr__(self):
        return json.dumps(self.json, ensure_ascii=False)
    
    def __str__(self):
        return json.dumps(self.json, ensure_ascii=False)
    

    @property
    def json(self):
        return {
            "path": self.path,
            "content": self.content,
            "type": self.type
        }
        
    