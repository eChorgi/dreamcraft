from dreamcraft.app.models.tasks import BaseTask

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

    def get_task_prompt(self, task: BaseTask) -> str:
        """接收一个 Task 对象，自动完成模板加载和数据注入"""
        # 1. 加载角色设定
        role_text = self.load(task.role_template)
        # 2. 加载查询模板，并用 Task 里的数据填充它
        query_template = self.load(task.query_template)
        query_text = query_template.format(**task.get_prompt_kwargs())
        
        # 3. 组装最终的 React 模板
        return self.react(
            role=role_text,
            query=query_text,
            enable_context_compression=task.enable_context_compression
        )