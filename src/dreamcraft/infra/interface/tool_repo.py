import json
import inspect
from pydantic import Field
from functools import wraps
from langchain_core.tools import tool
from pydantic import BaseModel, Field, create_model

from dreamcraft.app import QuestService, KnowledgeService
from dreamcraft.infra.env.agent import Agent
 

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

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs): # 👈 升级为 async def
            if 'thought' in kwargs: kwargs.pop('thought')
            elif len(args) > 0: args = args[1:]
            
            # 🌟 必须在这里真正 await 它，否则协程就会原样漏出去！
            return await func(*args, **kwargs) 
    else:
        # 如果是同步工具 (如 summary, query_wiki)
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'thought' in kwargs: kwargs.pop('thought')
            elif len(args) > 0: args = args[1:]
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

    @staticmethod
    def extend(model_name: str, **kwargs) -> type["ThoughtToolArgs"]:
        """动态创建一个新的 Pydantic 模型类，包含 thought 参数和额外的字段"""
        # fields 格式: { 'field_name': (type, description) }
        return create_model(
            model_name,
            __base__=ThoughtToolArgs,
            **{k: (v[0], Field(description=v[1])) for k, v in kwargs.items()}
        )

class ToolRepo:
    def __init__(self, knowledges: KnowledgeService, quest: QuestService, agent: Agent):
        self.knowledges = knowledges
        self.quest = quest
        self.agent = agent
        self._all_tools = None  # 用于缓存工具实例的字典

    def __getitem__(self, key: str) -> tool:
        return self.get_tools([key])[0]

    def get_tools(self, tools: list[str]) -> list[tool]:
        """根据工具名称列表返回工具实例列表"""
        all_tools = self.all_tools
        return [all_tools[t] for t in tools if t in all_tools]

    @property
    def all_tools(self) -> dict[str, tool]:
        """
        动态返回绑定了当前 Service 实例的工具列表
        在内部定义工具可以闭包引用 self
        """
        
        if self._all_tools is not None:
            return self._all_tools  # 返回缓存的工具实例

        @tool("query_wiki",
            description=
"""
# 功能
    - 这是一个Minecraft wiki语义查询工具，输入英文关键词和返回条数，输出相关的wiki内容. 这个工具会查询抽象的语义信息，而不是具体的文本匹配，因此适合在你对某个机制有模糊印象但不确定细节时使用。
# 输出格式
```
{
    "document": WikiDocument对象,
    "l2_distance": LLM生成的查询向量与文档向量之间的L2距离 范围在 0-2 之间 (数值越小表示越相关, 如果大于0.6说明相关度较低)
}
```
# 注意
    - 你应该尽可能具体地描述你想查询的内容，避免过于宽泛的关键词（如“enchanting”），而应该针对流程中的具体环节进行针对性查询（如“enchanting table”）。
    - 如果你发现查询结果的L2距离过高（如都大于0.6），则说明你可能没有查询到相关内容
""", 
            args_schema=ThoughtToolArgs.extend(
                "WikiQueryArgs", 
                keyword=(str, "查询关键词(英文)"), 
                items=(int, "返回条数，你需要尽可能少的填写此参数，只查询最重要的内容")
            )
        )
        @need_thought
        def query_wiki(keyword: str, items: int = 3) -> str:
            
            # 这里的调用会走 Service 层，完美符合 DDD
            result = self.knowledges.query_wiki(keyword, items)
            str_list = []
            for r in result:
                l2_dist = r['l2_distance']
                str_list.append(f"{{\n'document': {r['document'].dict},\n'l2_distance': {l2_dist:.2f}\n}}")
            return "[\n"+",\n".join(str_list)+"\n]"

        @tool("query_skill",
            description=
"""
# 功能
- 这是一个你的skill查询工具,你可以通过它查询你已经掌握的技能。输入技能相关的关键词和返回条数，输出相关的技能内容.
# 输出格式
- {
    "skill": Skill对象,
    "l2_distance": LLM生成的查询向量与文档向量之间的L2距离 范围在 0-2 之间 (数值越小表示越相关, 如果大于0.6说明相关度较低)
}
# 注意
- 你应该尽可能具体地描述你想查询的技能，避免过于宽泛的关键词（如“mining”），而应该针对流程中的具体环节进行针对性查询（如“iron ore mining”）。
- 如果你发现查询结果的L2距离过高（如都大于0.6），则说明你可能没有查询到相关技能
""",
            args_schema=ThoughtToolArgs.extend(
                "SkillQueryArgs",
                keyword=(str, "查询关键词"),
                items=(int, "返回条数，你需要尽可能少的填写此参数，只查询最重要的内容")
            )
        )
        @need_thought
        def query_skill(keyword: str, items: int = 3) -> str:
            result = self.knowledges.query_skill(keyword, items)
            str_list = []
            for r in result:
                l2_dist = r['l2_distance']
                str_list.append(f'{{\n"skill": {json.dumps(r["skill"].brief_dict)},\n"l2_distance": {l2_dist:.2f}\n}}')
            return "[\n"+",\n".join(str_list)+"\n]"

        # @tool("expand_path") # 简单参数也可以不写 Schema 类
        # @need_thought
        # def expand_path(waypoints: list[str]):
        #     """当需要扩展路径时使用。输入节点描述列表。"""
        #     # 这里你应该注入 QuestService 来处理
        #     return "路径已扩展"
        
        @tool("summary")
        @need_thought
        def summary(s: str):
            """当需要更新总结时使用。输入前面所有对话记录的总结文本。"""
            return s
        
        @tool("grep_wiki_files",description=
"""
# 简短摘要 (Summary)
在 Wiki 知识库中进行全局关键词检索。支持正则表达式，返回带标题层级路径（Breadcrumbs）的结构化代码片段。

# 详细功能描述 (Detailed Description)
**功能描述：**
该工具用于在大量 Markdown 文档中快速定位信息。它不仅返回匹配的文本行，还会自动向上溯源，提供该行所属的完整标题路径（heading_hierarchy）。
**使用提示：**
	- 初步探索：当不确定某个机制（如“fireball”）在哪个文件时，用于快速扫射全局。
	- 语境判断：通过返回的 heading_hierarchy 判断匹配项是属于“生成逻辑”、“掉落属性”还是“死亡消息”。
	- 精确定位：获取行号和章节名，为后续调用 read_md_section 提供入口。
**输出规范：**
    - 返回结果很可能经过截断处理（is_truncated），仅展示一部分文件预览。
    - 匹配项已使用 ==keyword== 进行语法高亮。
""",
            args_schema=ThoughtToolArgs.extend(
                "GrepWikiArgs",
                pattern=(str, "搜索关键词，支持正则表达式"),
                max_results=(int, "返回预览的最大匹配行数，默认为5, 你应该尽可能少的填写此参数, 只查询你最关心的具体内容，如果结果过多说明你的关键词不够具体")
            )
        )
        @need_thought
        def grep_wiki_files(pattern: str, max_results: int = 5):
            return self.knowledges.grep_wiki_files(pattern, max_results)
        

        @tool("read_wiki_section",
            description=
"""
# 功能：根据给定的文件名和章节标题，提取该章节下完整的 Markdown 内容（含子章节）。
# 使用逻辑：
	1. 深挖细节：当 grep_wiki_files 发现了关键线索（如某个行号或片段），但该片段信息不足以支撑决策时，调用此工具读取该行所属的完整 Section。
	2. 获取机制：当需要了解某个具体机制（如“如何合成石镐”或“僵尸的掉落逻辑”）时，直接读取对应的标题块。
""",
            args_schema=ThoughtToolArgs.extend(
                "ReadWikiSectionArgs",
                file_name=(str, "Markdown文件名，必须包含扩展名"),
                section_title=(str, "章节标题，必须与 grep_wiki_files 返回的 heading_hierarchy 中的标题完全匹配"))
            )
        @need_thought
        def read_wiki_section(file_name: str, section_title: str):
            return self.knowledges.read_wiki_section(file_name, section_title)


        @tool("get_next_waypoints",description=
"""
# 简短摘要 (Summary)
获取某个节点的后续任务的详细信息
**注意**
- 返回的节点是查询节点后续要进行的下游节点列表
""",
            args_schema=ThoughtToolArgs.extend(
                "GetNextWaypointsArgs",
                ind=(int, "节点索引"),
                depth=(int, "查询递归深度, 尽可能小的值（如1或2），以避免信息过载")
            )
        )
        @need_thought
        def get_next_waypoints(ind: int, depth: int = 2):
            st = set([ind])
            def _get_next(waypoint, current_depth = 0):
                st.add(waypoint.ind)
                if current_depth >= depth:
                    return 
                for next_wp in waypoint.next:
                    _get_next(next_wp, current_depth + 1)
            _get_next(self.quest.get_waypoint(ind))
            result = [self.quest.get_waypoint(i).dict for i in st]
            for r in result:
                r["next"] = [n.ind for n in self.quest.get_waypoint(r["ind"]).next]
            return result
        
        @tool("observe",
            description=
"""
# 功能：获取当前Minecraft世界的完整状态观察，包含玩家状态、周围环境、背包物品等信息。   
""",
        )
        @need_thought
        def observe():
            return self.agent.observe()
        

        @tool("grep_recipe", description=
"""
# 简短摘要 (Summary)
利用正则表达式检索配方信息，返回相关物品的合成配方详情。当你缺少某个物品的中间合成信息, 你应该调用这个工具进行查找, 例如你已知"木栅栏"需要"木板"和"木棍", 但不清楚"木板"的合成方法, 你就可以调用这个工具查询"木板"的配方, 从而获取如何制作"木板"的详细步骤。
# 返回格式
torch x4 <==无需工作台== charcoal x1, stick x1
# 注意
- 你应该先尽可能宽泛的查询(如查询木栅栏时应该查询"fence"而不是"wood_fence"), 除非你很确定物品的名称是什么
- 你必须注意产物和原料的数量关系，例如上面这个配方表示制作4个torch需要1个charcoal和1个stick。你应该把这些信息纳入计算范围
""",
            args_schema=ThoughtToolArgs.extend(
                "GrepRecipeArgs",
                pattern=(str, "搜索关键词，支持正则表达式"),
                max_results=(int, "返回结果的最大数量，默认为10")
            )
        )
        @need_thought
        async def grep_recipe(pattern: str, max_results: int = 10):
            def handle_json(s):
                rs = json.loads(s)
                return [f"{r['name']} x{r['resultCount']} <=={'工作台' if r.get('needCraftingTable') else '无需工作台'}== " + ', '.join([f"{x['name']} x{x['count']}" for x in r['ingredients']]) for r in rs]
            response = await self.agent.execute(f"log(await grepRecipe(bot, new RegExp('{pattern}')));")
            recipes = response.get("outputs", [])[0]
            recipes = handle_json(recipes)
            return_str = ""
            if len(recipes) > 0:
                if len(recipes) > max_results:
                    return_str = f"查询范围过于宽泛, 找到 {len(recipes)} 个匹配的配方:{', '.join([r.split(' x')[0] for r in recipes])}，只显示前 {max_results} 个\n"
                    recipes = recipes[:max_results]
                else:
                    return_str = f"找到 {len(recipes)} 个匹配的配方:\n"
            else:
                return "没有找到匹配的配方！请调整查询正则表达式后重试。\n"
            
            for r in recipes:
                return_str += f"{r}\n"
            return return_str

        
        
    
        self._all_tools = {
            "query_wiki": query_wiki,
            "query_skill": query_skill,
            # "expand_path": expand_path,
            "summary": summary,
            "grep_wiki_files": grep_wiki_files,
            "read_wiki_section": read_wiki_section,
            "get_next_waypoints": get_next_waypoints,
            "observe": observe,
            "grep_recipe": grep_recipe,
        }
        return self._all_tools
