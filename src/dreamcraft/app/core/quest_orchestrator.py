import json
from enum import StrEnum, auto


from dreamcraft.app.core import messages
from dreamcraft.app.core.messages import MessageBus
from dreamcraft.app.models import tasks
from dreamcraft.app.protocols import IPromptRepo
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.app.services.quest_service import QuestService

from dreamcraft.domain import Edge

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
            quest: QuestService, 
            llm: LLMService, 
            prompt: IPromptRepo,
            bus: MessageBus
        ):
        self.quest = quest
        self.llm = llm
        self.prompt = prompt
        self.context = None
        self.bus = bus
        self.inbox = bus.register("orchestrator")

    async def run(self, target: str):
        """状态机的主循环"""
        self.context = self.quest.add_quest(target)
        current_state = OrchestratorState.INIT
        max_steps = 10000

        while current_state != OrchestratorState.SUCCESS and self.context.step_count < max_steps:
            msg = self.inbox.fetch()
            match msg:
                case messages.ExecutionFailureMessage(from_wp=from_wp, to_wp=to_wp, reason=reason):
                    print(f"收到执行失败消息: 从 {from_wp} 到 {to_wp} 失败，原因: {reason}")
                    self.context.blocked_edges[Edge(from_wp, to_wp)] = "执行无法成功" + json.dumps(reason)
                    try:
                        split_ind = self.context.exec_path.index(to_wp)  # 回退到失败的节点，准备重新规划
                        self.context.exec_path = self.context.exec_path[:split_ind]
                    except ValueError:
                        print(f"警告: 执行失败的节点 {to_wp} 不在当前执行路径上，无法回退。")
                    self.context.current = from_wp
                    self.context.next = to_wp
                    current_state = OrchestratorState.NAVIGATE

            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            print(f"状态 {self.context.step_count}: {current_state}")
            current_state = await handler(self.context)
            self.context.step_count += 1
        if self.context.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    async def handle_init(self) -> OrchestratorState:
        return OrchestratorState.CHECK_FEASIBILITY
    
    async def handle_check_feasibility(self) -> OrchestratorState:
        _task = tasks.FeasibilityCheckTask(
            completed = self.context.completed,
            target = self.context.next,
            snapshot = self.context.current.actual_snapshot if self.context.current.actual_snapshot else self.context.current.imaginated_snapshot
        )
        response = await self.llm.execute(_task)
        reason = response.get("reason", "")
        is_feasible = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"检查可行性结果: {is_feasible}")
        print(f"当前已使用 tokens: {self.context.token_usage}")
        if is_feasible:
            self.context.next.extra_info["feasible_reason"] = response.get("reason", "")
            self.context.exec_path.append(self.context.next())
            self.bus.send_to("executor", "execute")
            return OrchestratorState.IMAGINATE
        else:
            self.context.blocked_edges[Edge(self.context.current, self.context.next)] = "判断不可行 : " + reason
            return OrchestratorState.CHECK_GRANULARITY

    async def handle_imaginate(self) -> OrchestratorState:
        _task = tasks.ImaginateTask(
            completed = self.context.completed,
            target = self.context.next,
            snapshot = self.context.current.actual_snapshot if self.context.current.actual_snapshot else self.context.current.imaginated_snapshot
        )
        response = await self.llm.execute(_task)
        imagined_snapshot = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        self.context.next.imaginated_snapshot = imagined_snapshot
        print(f"想象下一个状态结果: {imagined_snapshot}")
        print(f"当前已使用 tokens: {self.context.token_usage}")
        if self.context.next == self.context.target:
            return OrchestratorState.WAIT_FOR_EXECUTOR
        self.context.current = self.context.next
        self.context.next = next(iter(self.context.next.next), None)
        return OrchestratorState.CHECK_FEASIBILITY
    
    async def handle_wait_for_executor(self) -> OrchestratorState:
        return OrchestratorState.SUCCESS

    async def handle_check_granularity(self) -> OrchestratorState:
        _task = tasks.GranularityCheckTask(
            target = self.context.next,
            snapshot = self.context.current.actual_snapshot if self.context.current.actual_snapshot else self.context.current.imaginated_snapshot
        )
        response = await self.llm.execute(_task)
        is_granular = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"检查任务粒度结果: {is_granular}")
        print(f"当前已使用 tokens: {self.context.token_usage}")

        if is_granular:
            return OrchestratorState.EXPAND
        else:
            return OrchestratorState.NAVIGATE
        
    async def handle_navigate(self) -> OrchestratorState:
        _task = tasks.NavigateTask(
            reason = self.context.blocked_edges.get(Edge(self.context.current, self.context.next), ""),
            target = self.context.next,
            snapshot = self.context.current.actual_snapshot if self.context.current.actual_snapshot else self.context.current.imaginated_snapshot
        )
        response = await self.llm.execute(_task)
        next_waypoint = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"导航结果: {next_waypoint.line if next_waypoint else '无'}")
        print(f"当前已使用 tokens: {self.context.token_usage}")

        if next_waypoint is None:
            raise ValueError("任务执行失败, 无法完成")
            # return OrchestratorState.FIX
        else:
            self.context.next = next_waypoint
            return OrchestratorState.EXPAND

    async def handle_expand(self) -> OrchestratorState:
        _task = tasks.ExpandPathTask(
            completed = self.context.completed,
            target = self.context.next,
            snapshot = self.context.current.actual_snapshot if self.context.current.actual_snapshot else self.context.current.imaginated_snapshot
        )
        response = await self.llm.execute(_task)
        path_wps = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"分解结果: {[wp.line for wp in path_wps]}")
        print(f"当前已使用 tokens: {self.context.token_usage}")
        
        self.quest.expand_between(self.context.current, self.context.next, path_wps)
        self.context.next = path_wps[0]
        return OrchestratorState.CHECK_FEASIBILITY

    async def handle_unknown(self) -> OrchestratorState:
        raise ValueError("进入了未知的系统状态！")
    
    