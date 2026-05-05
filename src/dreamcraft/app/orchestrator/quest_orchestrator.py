from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from enum import StrEnum, auto
from dreamcraft.app.common.messaging import Mailbox
from dreamcraft.app.protocols import ILLMClient, IPromptRepo
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.domain.quest import Quest
from dreamcraft.domain.waypoint import Waypoint

class QuestState(StrEnum):
    INIT = auto()       # 初始化规划
    CHECK_FEASIBILITY = auto()  # 检查技能可用性
    EXPAND = auto()     # 任务分解
    FIX = auto()        # 失败修正
    SUCCESS = auto()    # 任务成功

class QuestContext:
    """上下文总线：在整个状态机流转中传递的唯一数据包"""
    def __init__(self, target):
        self.target: str = target
        self.quest: Quest | None = None  # 当前任务地图
        self.imaginating_waypoint: Waypoint | None = None  # 当前正在进行想象状态检查的节点
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
        current_state = QuestState.INIT
        max_steps = 10000

        while current_state != QuestState.END and ctx.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            current_state = handler(ctx)
            ctx.step_count += 1
            
        if ctx.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    def handle_init(self, ctx: QuestContext) -> QuestState:
        ctx.quest = self.quest.add_quest(ctx.target)
        ctx.imaginating_waypoint = ctx.quest.origin
        return QuestState.CHECK_FEASIBILITY

    def handle_expand(self, ctx: QuestContext) -> QuestState:
        
        is_feasible = self.llm.try_expand(
            completed = ctx.completed,
            target = ctx.imaginating_waypoint,
            snapshot = self.get_current_snapshot()
        )
        if is_feasible:
            return QuestState.EXPAND
        else:
            return QuestState.EXPAND

    def handle_execute(self, ctx: QuestContext) -> QuestState:
        result = self.action_agent.execute(ctx.paths)
        
        if result.success:
            return QuestState.REVIEW
        else:
            ctx.error_history.append(result.error_msg)
            return "REVISE_PLAN"

    def handle_unknown(self, ctx: QuestContext) -> QuestState:
        raise ValueError("进入了未知的系统状态！")
    
    