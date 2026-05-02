from langchain_core.tools import tool
from pydantic import BaseModel, Field
from dreamcraft.app.services.knowledge_service import KnowledgeService

import inspect
from functools import wraps
from pydantic import Field

def need_thought(func):
    # 1. 获取原有的签名和注解
    sig = inspect.signature(func)
    # 获取函数现有的类型注解，如果没有则初始化为空字典
    annotations = getattr(func, '__annotations__', {})

    # 2. 创建新的 thought 参数对象
    thought_param = inspect.Parameter(
        'thought',
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=str,  # 这里指定了类型为 str
        default=inspect.Parameter.empty
    )

    # 3. 更新签名
    new_params = [thought_param] + list(sig.parameters.values())
    new_sig = sig.replace(parameters=new_params)

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 逻辑保持不变：剥离 thought 参数
        if 'thought' in kwargs:
            thought = kwargs.pop('thought')
        elif len(args) > 0:
            thought = args[0]
            args = args[1:]
        else:
            raise ValueError("Missing required 'thought' parameter")
        
        # 可以在这里对 thought 做处理，比如 logging
        return func(*args, **kwargs)

    # 4. 同步更新包装器的签名和类型注解
    wrapper.__signature__ = new_sig
    
    # 手动注入 thought 的类型到注解字典中
    new_annotations = annotations.copy()
    new_annotations['thought'] = str
    wrapper.__annotations__ = new_annotations

    return wrapper

class ThoughtToolArgs(BaseModel):
    thought: str = Field(description="【必填】在执行此动作前，说明你的分析过程和为什么选择这个操作。")

# 1. Schema 定义建议放在外层，保持整洁
class WikiQueryArgs(ThoughtToolArgs):
    keyword: str = Field(description="查询关键词(英文)")
    items: int = Field(default=3, description="返回条数，你需要尽可能少的填写此参数，只查询最重要的内容")

class SkillQueryArgs(ThoughtToolArgs):
    keyword: str = Field(description="查询关键词")
    items: int = Field(default=3, description="返回条数，你需要尽可能少的填写此参数，只查询最重要的内容")

class ToolManager:
    def __init__(self, knowledges: KnowledgeService):
        self.knowledges = knowledges

    def get_tools(self) -> dict[str, tool]:
        """
        动态返回绑定了当前 Service 实例的工具列表
        在内部定义工具可以闭包引用 self
        """
        
        @tool("query_wiki", args_schema=WikiQueryArgs)
        @need_thought
        def query_wiki(keyword: str, items: int = 3) -> str:
            """
            这是一个Minecraft wiki查询工具，输入英文关键词和返回条数，输出相关的wiki内容. 
            查询特定的 单一知识点。严禁输入过于宽泛的问题（如“how to win”），请针对流程中的具体环节进行针对性查询（如“Blaze Spawning Mechanics”）
            """
            # 这里的调用会走 Service 层，完美符合 DDD
            return self.knowledges.query_wiki(keyword, items)

        @tool("query_skill", args_schema=SkillQueryArgs)
        @need_thought
        def query_skill(keyword: str, items: int = 3) -> str:
            """
            这是一个你的skill查询工具,你可以通过它查询你已经掌握的技能。输入技能相关的关键词和返回条数，输出相关的技能内容.
            查询特定的 单一技能。
            """
            # 这里的调用会走 Service 层，完美符合 DDD
            return self.knowledges.query_skill(keyword, items)

        @tool("expand_path") # 简单参数也可以不写 Schema 类
        @need_thought
        def expand_path(new_nodes: list[str]):
            """当需要扩展路径时使用。输入节点描述列表。"""
            # 这里你应该注入 GoalService 来处理
            return "路径已扩展"

        return {
            "query_wiki": query_wiki, 
            "query_skill": query_skill,
            "expand_path": expand_path
        }