from enum import StrEnum, auto

from dreamcraft.app.core.messaging import MessageBus
from dreamcraft.domain.quest import Quest

class ExecutorState(StrEnum):
    INIT = auto()       # 初始化规划
    WAIT_FOR_ORCHESTRATOR = auto()  # 等待执行
    SUCCESS = auto()    # 任务成功


class QuestExecutor:
    def __init__(self, bus: MessageBus, quest: Quest):
        self.bus = bus
        self.quest = quest
        self.inbox = bus.register("executor")
    
    async def run(self):
        current_state = ExecutorState.INIT
        max_steps = 10000

        while current_state != ExecutorState.SUCCESS and self.context.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            print(f"执行器状态 {self.context.step_count}: {current_state}")
            current_state = await handler(self.context)
            self.context.step_count += 1
        if self.context.step_count >= max_steps:
            print("执行器因超时或死循环被系统强制终止。")

    
        