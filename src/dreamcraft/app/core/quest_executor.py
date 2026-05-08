from enum import StrEnum, auto

from dreamcraft.app.core.messaging import MessageBus
from dreamcraft.app.services.knowledge_service import KnowledgeService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.domain.quest import Quest

class ExecutorState(StrEnum):
    INIT = auto()       # 初始化规划
    FETCH_EXECUTING = auto()  # 获取执行任务
    GENERATE_CODE = auto()  # 生成代码
    SUCCESS = auto()    # 任务成功


class QuestExecutor:
    def __init__(self, bus: MessageBus, quest: Quest, llm: LLMService, knowledge: KnowledgeService):
        self.bus = bus
        self.quest = quest
        self.inbox = bus.register("executor")
        self.llm = llm
        self.knowledge = knowledge

    async def run(self):
        current_state = ExecutorState.INIT
        max_steps = 10000

        while current_state != ExecutorState.SUCCESS and self.quest.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            print(f"执行器状态 {self.quest.step_count}: {current_state}")
            current_state = await handler(self.quest)
            self.quest.step_count += 1
        if self.quest.step_count >= max_steps:
            print("执行器因超时或死循环被系统强制终止。")

    async def handle_init(self) -> ExecutorState:
        return ExecutorState.FETCH_EXECUTING
    
    async def handle_fetch_executing(self) -> ExecutorState:
        msg = self.inbox.fetch_topic(f"execute")
        if msg:
            if len(self.quest.exec_path) > self.quest.exec_ind + 1:
                return ExecutorState.GENERATE_CODE

    async def handle_generate_code(self) -> ExecutorState:
        response = self.llm.generate_code(
            target=self.quest.next,
            snapshot=self.quest.current.actual_snapshot,
            reason=self.quest.exec_path[self.quest.exec_ind + 1].reason
        )
        raw_code = response["result"]
        final_code = self.knowledge.inject_dependencies(raw_code)
        final_code = f"""
            {final_code}
        """
        print(f"注入依赖函数后代码:\n{final_code}")
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        
    
        