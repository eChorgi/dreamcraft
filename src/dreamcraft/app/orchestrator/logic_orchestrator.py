from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from enum import StrEnum, auto
from dreamcraft.app.common.messaging import Mailbox
from dreamcraft.app.protocols import ILLMClient, IPromptRepo
from dreamcraft.app.services.goal_service import GoalService
from dreamcraft.domain.goal_model import GoalNode, GoalMap

class LogicState(StrEnum):
    INIT = auto()       # 初始化规划
    CHECK_FEASIBILITY = auto()  # 检查技能可用性
    EXPAND = auto()     # 任务分解
    FIX = auto()        # 失败修正
    SUCCESS = auto()    # 任务成功

class LogicSession:
    """上下文总线：在整个状态机流转中传递的唯一数据包"""
    def __init__(self, target_goal):
        self.goal: str = target_goal
        self.imagination_stack: list[GoalMap] = []
        self.current_node: GoalNode | None = None
        self.error_history = []
        self.step_count = 0

class LogicOrchestrator:
    def __init__(
            self,
            goals: GoalService, 
            llm: ILLMClient, 
            prompt: IPromptRepo,
            inbox: Mailbox,
            outbox: Mailbox
        ):
        self.goals = goals
        self.llm = llm
        self.prompt = prompt
        self.inbox = inbox
        self.outbox = outbox


    def run(self, target_goal: str):
        """状态机的主循环"""
        session = LogicSession(target_goal)
        current_state = LogicState.INIT
        max_steps = 10000

        while current_state != LogicState.END and session.step_count < max_steps:
            handler_method_name = f"handle_{current_state.lower()}"
            handler = getattr(self, handler_method_name, self.handle_unknown)

            current_state = handler(session)
            session.step_count += 1
            
        if session.step_count >= max_steps:
            print("任务因超时或死循环被系统强制终止。")

    # ================= 状态处理方法 =================

    def handle_init(self, session: LogicSession) -> str:
        """对应图中：给予目标 -> 生成初始目标路径"""
        self.goals.new_goal(session.goal)
        return LogicState.CHECK_FEASIBILITY

    def handle_check_feasibility(self, session: LogicSession) -> str:
        """对应图中：利用想象状态，提前进行下一步可行性检查"""
        # 调用裁判进行判断
        is_feasible = self.llm_judge.check_feasibility(session.paths)
        
        if is_feasible:
            return LogicState.EXECUTE
        else:
            return LogicState.REVISE_PLAN

    def handle_execute(self, session: LogicSession) -> str:
        """对应图中：生成动作函数并触发"""
        result = self.action_agent.execute(session.paths)
        
        if result.success:
            return LogicState.REVIEW
        else:
            session.error_history.append(result.error_msg)
            return "REVISE_PLAN"

    def handle_unknown(self, session: LogicSession) -> str:
        """兜底机制"""
        raise ValueError("进入了未知的系统状态！")
    
    def react(self, prompt: str, query: str, tools: list[tool], max_iterations: int = 5) -> str:
        """核心功能：根据输入的 query 进行思考、工具调用、观察结果、再思考的循环"""
        llm_with_tools = self.llm.with_tools(tools)

        tool_dict = {t.name: t for t in tools}
        
        #首先判断 prompt 中是否存在 {query} 占位符，如果没有就默认在末尾添加
        if "{query}" in prompt:
            formatted_prompt = prompt.format(query=query)
        else:
            formatted_prompt = prompt + f"\n\n查询: {query}"

        messages = []
        messages.append(SystemMessage(content=formatted_prompt))  # 首先把 prompt 作为上下文输入

        current_iteration = 0

        print(f"开始执行大模型循环...提示词: {prompt.replace('\n', ' ')}，查询: {query}")

        while current_iteration < max_iterations:
            print(f"\n--- 第 {current_iteration + 1} 轮思考 ---")

            # messages.append(AIMessage(content=f"当前思考轮次: {current_iteration + 1}"))
            # 1. 把全套历史记录喂给 LLM
            ai_msg = llm_with_tools.invoke(messages)
            messages.append(ai_msg) # 把 LLM 的回复（不管是不是工具调用）记录到历史中

            # 2. 判断是否还需要调用工具
            if not ai_msg.tool_calls:
                # 没有 tool_calls 说明 LLM 认为信息已经充足，输出了最终答案
                if "【Final Answer】" in ai_msg.content:
                    result = ai_msg.content.split("【Final Answer】")[-1].strip()
                    print(f"提取到的最终答案是: {result}")
                    break
                else :
                    print("AI 的回复中没有包含【Final Answer】标记，要求重新思考。")
                    warning_msg = (
                        "⚠️ 系统拦截：你的回答格式严重违规！你既没有触发真正的 Tool Call，也没有给出包含 '【Final Answer】' 的最终计划。\n"
                        "请重新阅读上一轮的工具返回结果，更新你的【信息消化】，然后立即发起一次【全新的 Tool Call】查缺补漏，"
                        "或者输出详尽的 Final Answer 结束任务。不要在文本里汇报 '已调用'！"
                    )
                    messages.append(HumanMessage(content=warning_msg))
                    max_iterations += 1  # 给 LLM 多一次机会重新思考
                    continue

            # 3. 如果走到了这里，说明有 tool_calls，准备执行
            print(f"🔍 AI 觉得线索不够，决定调用工具: {[t['name'] for t in ai_msg.tool_calls]}")
            
            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                tool_func = tool_dict.get(tool_name)
                print(f"  -> 正在执行工具 '{tool_name}'，参数: {tool_args}")
                observation = tool_func.invoke(tool_args)
                    
                print(f"  -> 工具执行结果已返回，准备进入下一轮。")
                
                new_tool_msg = ToolMessage(
                    content=str(observation),
                    tool_call_id=tool_call["id"]
                )
                messages.append(new_tool_msg)

            current_iteration += 1

        if current_iteration >= max_iterations:
            print("⚠️ 达到最大思考轮数，强行终止循环，可能是任务太复杂或遇到了死循环。")
    #输出最终token数
        total_tokens = sum(len(m.content) for m in messages)
        print(f"本次交互总共使用了 {total_tokens} tokens。")
        print(f"完整的交互历史: {messages}")
        return result
        