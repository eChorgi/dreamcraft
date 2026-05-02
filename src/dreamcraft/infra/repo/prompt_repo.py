from dreamcraft.config import PROMPT_DIR
from pathlib import Path

class PromptRepo:
    def __init__(self, settings):
        self.dir = settings.prompt_dir

    def load(self, name: str)-> str:
        """从 prompts 目录加载指定名称的 prompt 模板。

        参数:
        - name: prompt 模板文件名（不含扩展名），如 "build_house"。

        返回:
        - 模板内容字符串，供 LLM 调用时格式化使用。
        """
        prompt_path = self.dir / f"{name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found in {self.dir}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()