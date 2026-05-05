from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from enum import StrEnum, auto
from dreamcraft.app.common.messaging import Mailbox
from dreamcraft.app.protocols import ILLMClient, IPromptRepo
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.domain.quest import Quest
from dreamcraft.domain.snapshot import Snapshot
from dreamcraft.domain.waypoint import Waypoint

class OrchestratorState(StrEnum):
    INIT = auto()       # 初始化规划
    CHECK_FEASIBILITY = auto()  # 检查技能可用性
    CHECK_GRANULARITY = auto()  # 检查任务粒度
    WAIT_FOR_EXCUTING = auto()  # 等待执行
    NAVIGATE = auto()   # 导航
    EXPAND = auto()     # 任务分解
    FIX = auto()        # 失败修正
    SUCCESS = auto()    # 任务成功

class QuestContext:
    """上下文总线：在整个状态机流转中传递的唯一数据包"""
    def __init__(self, target):
        self.target: str = target
        self.quest: Quest | None = None  # 当前任务地图
        self.current_waypoint: Waypoint | None = None
        self.target_waypoint: Waypoint | None = None 

        self.latest_snapshot = None

        self.excuting_waypoint: Waypoint | None = None # 当前正在执行的节点

        self.completed: list[Waypoint] = []  # 已完成的节点列表

        self.is_imaginated: set[Waypoint] = set()  # 记录哪些节点已经经过想象状态检查
        self.error_history = []
        self.step_count = 0

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


    def run(self, target: str):
        """状态机的主循环"""
        ctx = QuestContext(target)
        current_state = OrchestratorState.INIT
        max_steps = 10000

        while current_state != OrchestratorState.END and ctx.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            current_state = handler(ctx)
            ctx.step_count += 1
            
        if ctx.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    def handle_init(self, ctx: QuestContext) -> OrchestratorState:
        ctx.quest = self.quest.add_quest(ctx.target)
        ctx.current_waypoint = ctx.quest.origin
        ctx.target_waypoint = ctx.quest.target
        ctx.latest_snapshot = Snapshot.default()
        return OrchestratorState.CHECK_FEASIBILITY
    
    def handle_check_feasibility(self, ctx: QuestContext) -> OrchestratorState:
        is_feasible = self.llm.check_feasibility(
            completed = ctx.completed,
            target = ctx.target_waypoint,
            snapshot = self.get_current_snapshot()
        )
        if is_feasible:
            if ctx.target_waypoint == ctx.quest.target:
                return OrchestratorState.WAIT_FOR_EXCUTING
            ctx.current_waypoint = ctx.target_waypoint
            ctx.target_waypoint = ctx.target_waypoint.next[0]
            return OrchestratorState.CHECK_FEASIBILITY
        else:
            return OrchestratorState.CHECK_GRANULARITY
    def handle_check_granularity(self, ctx: QuestContext) -> OrchestratorState:
        is_granular = self.llm.check_granularity(
            completed = ctx.completed,
            target = ctx.current_waypoint,
            snapshot = self.get_current_snapshot()
        )
        if is_granular:
            return OrchestratorState.EXPAND
        else:
            return OrchestratorState.NAVIGATE
        
    def handle_navigate(self, ctx: QuestContext) -> OrchestratorState:
        next_waypoint = self.llm.navigate(
            completed = ctx.completed,
            target = ctx.current_waypoint,
            snapshot = self.get_current_snapshot()
        )
        if next_waypoint is None:
            raise ValueError("导航模块未返回下一个节点，无法继续执行！")
            # return OrchestratorState.FIX
        else:
            ctx.target_waypoint = next_waypoint
            return OrchestratorState.EXPAND

    def handle_expand(self, ctx: QuestContext) -> OrchestratorState:
        
        path_wps = self.llm.expand_path(
            completed = ctx.completed,
            target = ctx.current_waypoint,
            snapshot = self.get_current_snapshot()
        )
        self.quest.expand_between(ctx.current_waypoint, ctx.target_waypoint, path_wps)
        return OrchestratorState.CHECK_FEASIBILITY

    def handle_execute(self, ctx: QuestContext) -> OrchestratorState:
        result = self.action_agent.execute(ctx.paths)
        
        if result.success:
            return OrchestratorState.REVIEW
        else:
            ctx.error_history.append(result.error_msg)
            return "REVISE_PLAN"

    def handle_unknown(self, ctx: QuestContext) -> OrchestratorState:
        raise ValueError("进入了未知的系统状态！")
    
    