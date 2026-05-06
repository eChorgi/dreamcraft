from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from enum import StrEnum, auto
from dreamcraft.app.core.messaging import Mailbox
from dreamcraft.app.core.quest_context import QuestContext
from dreamcraft.app.core.quest_runner import QuestRunner
from dreamcraft.app.protocols import ILLMClient, IPromptRepo
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.domain.quest import Quest
from dreamcraft.domain.snapshot import Snapshot
from dreamcraft.domain.waypoint import Waypoint

class OrchestratorState(StrEnum):
    INIT = auto()       # 初始化规划
    CHECK_FEASIBILITY = auto()  # 检查技能可用性
    IMAGINATE = auto()  # 想象下一个状态
    CHECK_GRANULARITY = auto()  # 检查任务粒度
    WAIT_FOR_EXCUTING = auto()  # 等待执行
    NAVIGATE = auto()   # 导航
    EXPAND = auto()     # 任务分解
    SUCCESS = auto()    # 任务成功

class QuestOrchestrator:
    def __init__(
            self,
            quest: QuestService, 
            llm: LLMService, 
            prompt: IPromptRepo,
            inbox: Mailbox,
            outbox: Mailbox
        ):
        self.quest = quest
        self.llm = llm
        self.prompt = prompt
        self.inbox = inbox
        self.outbox = outbox
        self.context = None

        self.runner = QuestRunner(self.outbox, self.inbox, self.context)


    def run(self, target: str):
        """状态机的主循环"""
        self.context = QuestContext(target)
        current_state = OrchestratorState.INIT
        max_steps = 10000

        while current_state != OrchestratorState.SUCCESS and self.context.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            print(f"状态 {self.context.step_count}: {current_state}")
            current_state = handler(self.context)
            self.context.step_count += 1
        if self.context.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    def handle_init(self, ctx: QuestContext) -> OrchestratorState:
        ctx.quest = self.quest.add_quest(ctx.target)
        ctx.current_waypoint = ctx.quest.origin
        ctx.target_waypoint = ctx.quest.target
        ctx.actual_snapshot = Snapshot.default()
        return OrchestratorState.CHECK_FEASIBILITY
    
    def handle_check_feasibility(self, ctx: QuestContext) -> OrchestratorState:
        is_feasible = self.llm.check_feasibility(
            completed = ctx.completed,
            target = ctx.target_waypoint,
            snapshot = ctx.current_waypoint.imaginated_snapshot
        )
        print(f"检查可行性结果: {is_feasible}")
        if is_feasible:
            return OrchestratorState.IMAGINATE
        else:
            return OrchestratorState.CHECK_GRANULARITY

    def handle_imaginate(self, ctx: QuestContext) -> OrchestratorState:
        imagined_snapshot = self.llm.imaginate(
            completed = ctx.completed,
            target = ctx.current_waypoint,
            snapshot = ctx.current_waypoint.imaginated_snapshot
        )
        ctx.target_waypoint.imaginated_snapshot = imagined_snapshot
        print(f"想象下一个状态结果: {imagined_snapshot}")
        if ctx.target_waypoint == ctx.quest.target:
            return OrchestratorState.WAIT_FOR_EXCUTING
        ctx.current_waypoint = ctx.target_waypoint
        ctx.target_waypoint = next(iter(ctx.target_waypoint.next), None)
        return OrchestratorState.CHECK_FEASIBILITY
    
    def handle_wait_for_excuting(self, ctx: QuestContext) -> OrchestratorState:
        return OrchestratorState.SUCCESS

    def handle_check_granularity(self, ctx: QuestContext) -> OrchestratorState:
        is_granular = self.llm.check_granularity(
            target = ctx.target_waypoint,
            snapshot = ctx.current_waypoint.imaginated_snapshot
        )
        print(f"检查任务粒度结果: {is_granular}")
        if is_granular:
            return OrchestratorState.EXPAND
        else:
            return OrchestratorState.NAVIGATE
        
    def handle_navigate(self, ctx: QuestContext) -> OrchestratorState:
        next_waypoint = self.llm.navigate(
            target = ctx.target_waypoint,
            snapshot = ctx.current_waypoint.imaginated_snapshot
        )
        print(f"导航结果: {next_waypoint.line if next_waypoint else '无'}")
        if next_waypoint is None:
            raise ValueError("任务执行失败, 无法完成")
            # return OrchestratorState.FIX
        else:
            ctx.target_waypoint = next_waypoint
            return OrchestratorState.EXPAND

    def handle_expand(self, ctx: QuestContext) -> OrchestratorState:
        path_wps = self.llm.expand_path(
            completed = ctx.completed,
            target = ctx.target_waypoint,
            snapshot = ctx.current_waypoint.imaginated_snapshot
        )
        print(f"分解结果: {[wp.line for wp in path_wps]}")
        self.quest.expand_between(ctx.current_waypoint, ctx.target_waypoint, path_wps)
        ctx.target_waypoint = path_wps[0]
        return OrchestratorState.CHECK_FEASIBILITY

    def handle_unknown(self, ctx: QuestContext) -> OrchestratorState:
        raise ValueError("进入了未知的系统状态！")
    
    