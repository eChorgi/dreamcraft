from dreamcraft.config import PROMPT_DIR
from pathlib import Path

from dreamcraft.domain.quest import Waypoint
from dreamcraft.domain.snapshot import Snapshot

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
        prompt_path = self.dir / f"{name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found in {self.dir}")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def react(self, role: str, query: str, extra: str = "", enable_context_compression: bool = True) -> str:
        """ react 基础模板，供后续进一步定制"""
        prompt = self.load("react")
        if enable_context_compression:
            extra = f"{self.load('context_compression')}\n" + extra
        if extra:
            extra = "\n\n# 额外信息\n" + extra
        #首先判断 prompt 中是否存在 {query} 占位符，如果没有就默认在末尾添加
        if "{query}" in prompt:
            formatted_prompt = prompt.format(role=role, query=query, extra=extra)
        else:
            formatted_prompt = prompt + f"\n\n# 本次任务查询\n{query}"
        return formatted_prompt

    def imaginate(self, completed: list[Waypoint | str], target: Waypoint | str, snapshot: Snapshot, enable_context_compression: bool = True) -> str:
        """专门用于生成想象状态的 prompt 模板"""
        prompt = self.react(
            role = self.load("imaginate_role"),
            query = self.load("imaginate_query").format(
                completed = "- " + "\n- ".join([wp.description if isinstance(wp, Waypoint) else wp for wp in completed]),
                target=target.description if isinstance(target, Waypoint) else target,
                snapshot = snapshot.json
            ),
            enable_context_compression=enable_context_compression
        )
        return prompt

    def feasibility_check(self, completed: list[Waypoint | str], target: Waypoint | str, snapshot: Snapshot, enable_context_compression: bool = True) -> str:
        """专门用于生成可行性检查的 prompt 模板"""
        prompt = self.react(
            role = self.load("feasibility_check_role"),
            query = self.load("feasibility_check_query").format(
                completed = "- " + "\n- ".join([wp.description if isinstance(wp, Waypoint) else wp for wp in completed]),
                target=target.description if isinstance(target, Waypoint) else target,
                snapshot = snapshot.json
            ),
            enable_context_compression=enable_context_compression
        )
        return prompt