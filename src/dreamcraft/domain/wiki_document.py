import json
from typing import Literal

class WikiDocument:
    def __init__(self, heading_hierarchy: list[str] = None, file: str = None, content: str = None, type: Literal["text", "table", None] = None, chunk_index: int = None):
        self.heading_hierarchy = heading_hierarchy
        self.file = file
        self.content = content
        self.type = type
        self.chunk_index = chunk_index

    def __repr__(self):
        return json.dumps(self.dict, ensure_ascii=False)
    
    def __str__(self):
        return json.dumps(self.dict, ensure_ascii=False)
    

    @property
    def dict(self):
        try:
            json_dict = {
                "heading_hierarchy": self.heading_hierarchy,
                "file": self.file,
                "content": json.loads(self.content.replace("'", '"')) if isinstance(self.content, str) else self.content,
                "type": self.type
            }
        except:
            json_dict = {
                "heading_hierarchy": self.heading_hierarchy,
                "file": self.file,
                "content": self.content,
                "type": self.type
            }
        return json_dict
        
    