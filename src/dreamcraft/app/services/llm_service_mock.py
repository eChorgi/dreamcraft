from dreamcraft.domain import Waypoint, Snapshot
from dreamcraft.app.protocols import ILLMClient, IPromptRepo, IQuestRepo, IToolRepo

class LLMServiceMock:
    """负责与 LLM 进行交互的服务类，提供一个统一的接口供 Orchestrator 调用"""
    
    def __init__(self, llm: ILLMClient, prompt: IPromptRepo, tool: IToolRepo, quest: IQuestRepo):
        self.llm = llm
        self.prompt = prompt
        self.tool = tool
        self.quest = quest

        self.fc_list = [False, False, True, True, True]
        self.fc_counter = 0
        self.fg_list = [False, True]
        self.fg_counter = 0
    
    def check_feasibility(
        self, 
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
        ) -> bool:
        
        if self.fc_counter < len(self.fc_list):
            result = self.fc_list[self.fc_counter]
            self.fc_counter += 1
            return result
        return True
        # 随机返回 True 或 False 来模拟可行性检查的结果
        # import random
        # 随机种子 = hash(str(target)+str(time.time()))  # 使用目标的哈希值作为随机种子，确保同一目标的结果一致
        # random.seed(随机种子)
        # return random.choice([True, False])

    def imaginate(
        self, 
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> Snapshot:
        return Snapshot.default()
    
    def expand_path(
        self,
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> list[Waypoint] | None:
        
        return [Waypoint(name="Mocked Waypoint 1", description="这是一个由LLMServiceMock生成的模拟节点"), Waypoint(name="Mocked Target 2", description="这是一个由LLMServiceMock生成的模拟目标节点")]
    
    def navigate(
        self,
        target: Waypoint, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> Waypoint | None:
        return next(iter(target.next), None)  # 简单地返回第一个后继节点作为导航结果
    
    def check_granularity(
        self, 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
        ) -> bool:
        if self.fg_counter < len(self.fg_list):
            self.fg_counter += 1
            return self.fg_list[self.fg_counter-1]
        else:
            return True
        # 随机返回 True 或 False 来模拟粒度检查的结果
        # import random
        # 随机种子 = hash(str(target)+str(time.time()))  # 使用目标的哈希值作为随机种子，确保同一目标的结果一致
        # random.seed(随机种子)
        # return random.choice([True, False])