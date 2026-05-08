from enum import StrEnum, auto
from dreamcraft.app.core.message import MessageBus
from dreamcraft.app.protocols import IPromptRepo
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.domain.quest import Executable

class OrchestratorState(StrEnum):
    INIT = auto()       # 初始化规划
    CHECK_FEASIBILITY = auto()  # 检查技能可用性
    IMAGINATE = auto()  # 想象下一个状态
    CHECK_GRANULARITY = auto()  # 检查任务粒度
    WAIT_FOR_EXECUTOR = auto()  # 等待执行
    NAVIGATE = auto()   # 导航
    EXPAND = auto()     # 任务分解
    SUCCESS = auto()    # 任务成功

class QuestOrchestrator:
    def __init__(
            self,
            s_quest: QuestService, 
            llm: LLMService, 
            prompt: IPromptRepo,
            bus: MessageBus
        ):
        self.quest_service = s_quest
        self.llm = llm
        self.prompt = prompt
        self.quest = None
        self.bus = bus
        self.inbox = bus.register("orchestrator")

    async def run(self, target: str):
        """状态机的主循环"""
        self.quest = self.quest_service.add_quest(target)
        current_state = OrchestratorState.INIT
        max_steps = 10000

        while current_state != OrchestratorState.SUCCESS and self.quest.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            print(f"状态 {self.quest.step_count}: {current_state}")
            current_state = await handler(self.quest)
            self.quest.step_count += 1
        if self.quest.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    async def handle_init(self) -> OrchestratorState:
        return OrchestratorState.CHECK_FEASIBILITY
    
    async def handle_check_feasibility(self) -> OrchestratorState:
        response = await self.llm.check_feasibility(
            completed = self.quest.completed,
            target = self.quest.next,
            snapshot = self.quest.current.actual_snapshot if self.quest.current.actual_snapshot else self.quest.current.imaginated_snapshot
        )
        is_feasible = response["result"]
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"检查可行性结果: {is_feasible}")
        print(f"当前已使用 tokens: {self.quest.token_usage}")
        if is_feasible:
            self.quest.exec_path.append(Executable(
                waypoint=self.quest.next,
                reason=response.get("reason", "")
            ))
            self.bus.send_to("executor", "execute")
            return OrchestratorState.IMAGINATE
        else:
            return OrchestratorState.CHECK_GRANULARITY

    async def handle_imaginate(self) -> OrchestratorState:
        response = await self.llm.imaginate(
            completed = self.quest.completed,
            target = self.quest.next,
            snapshot = self.quest.current.actual_snapshot if self.quest.current.actual_snapshot else self.quest.current.imaginated_snapshot
        )
        imagined_snapshot = response["result"]
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        self.quest.next.imaginated_snapshot = imagined_snapshot
        print(f"想象下一个状态结果: {imagined_snapshot}")
        print(f"当前已使用 tokens: {self.quest.token_usage}")
        if self.quest.next == self.quest.target:
            return OrchestratorState.WAIT_FOR_EXECUTOR
        self.quest.current = self.quest.next
        self.quest.next = next(iter(self.quest.next.next), None)
        return OrchestratorState.CHECK_FEASIBILITY
    
    async def handle_wait_for_executor(self) -> OrchestratorState:
        return OrchestratorState.SUCCESS

    async def handle_check_granularity(self) -> OrchestratorState:
        response = await self.llm.check_granularity(
            target = self.quest.next,
            snapshot = self.quest.current.actual_snapshot if self.quest.current.actual_snapshot else self.quest.current.imaginated_snapshot
        )
        is_granular = response["result"]
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"检查任务粒度结果: {is_granular}")
        print(f"当前已使用 tokens: {self.quest.token_usage}")

        if is_granular:
            return OrchestratorState.EXPAND
        else:
            return OrchestratorState.NAVIGATE
        
    async def handle_navigate(self) -> OrchestratorState:
        response = await self.llm.navigate(
            target = self.quest.next,
            snapshot = self.quest.current.actual_snapshot if self.quest.current.actual_snapshot else self.quest.current.imaginated_snapshot
        )
        next_waypoint = response["result"]
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"导航结果: {next_waypoint.line if next_waypoint else '无'}")
        print(f"当前已使用 tokens: {self.quest.token_usage}")

        if next_waypoint is None:
            raise ValueError("任务执行失败, 无法完成")
            # return OrchestratorState.FIX
        else:
            self.quest.next = next_waypoint
            return OrchestratorState.EXPAND

    async def handle_expand(self) -> OrchestratorState:
        response = await self.llm.expand_path(
            completed = self.quest.completed,
            target = self.quest.next,
            snapshot = self.quest.current.actual_snapshot if self.quest.current.actual_snapshot else self.quest.current.imaginated_snapshot
        )
        path_wps = response["result"]
        self.quest.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"分解结果: {[wp.line for wp in path_wps]}")
        print(f"当前已使用 tokens: {self.quest.token_usage}")
        
        self.quest_service.expand_between(self.quest.current, self.quest.next, path_wps)
        self.quest.next = path_wps[0]
        return OrchestratorState.CHECK_FEASIBILITY

    async def handle_unknown(self) -> OrchestratorState:
        raise ValueError("进入了未知的系统状态！")
    
    