from typing import Literal


class WikiDocument:
    def __init__(self, path: list[str] = None, content: str = None, type: Literal["text", "table", None] = None, chunk_index: int = None):
        self.path = path
        self.content = content
        self.type = type
        self.chunk_index = chunk_index