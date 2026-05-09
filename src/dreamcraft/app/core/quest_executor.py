import asyncio
from enum import StrEnum, auto

from dreamcraft.app.core import messages
from dreamcraft.app.core.messages import MessageBus
from dreamcraft.app.models import tasks
from dreamcraft.app.services.knowledge_service import KnowledgeService
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.app.protocols import IMinecraftClient
from dreamcraft.domain import Quest


class ExecutorState(StrEnum):
    INIT = auto()       # 初始化规划
    WAIT = auto()  # 获取执行任务
    GENERATE_CODE = auto()  # 生成代码
    VERIFY = auto()  # 验证结果
    SUCCESS = auto()    # 任务成功


class QuestExecutor:
    def __init__(self, bus: MessageBus, context: Quest, llm: LLMService, knowledge: KnowledgeService, mc: IMinecraftClient):
        self.bus = bus
        self.context = context
        self.inbox = bus.register("executor")
        self.llm = llm
        self.knowledge = knowledge
        self.mc = mc

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

    async def handle_init(self) -> ExecutorState:
        return ExecutorState.WAIT
    
    async def handle_wait(self) -> ExecutorState:
        msg = await self.inbox.wait_for_topic(f"execute")
        if msg and self.context.exec_next:
            return ExecutorState.GENERATE_CODE

    async def handle_generate_code(self) -> ExecutorState:
        if len(self.context.exec_history.get("fail_records", [])) > 3:
            print("连续失败超过3次，自动放弃执行当前任务。")
            self.context.exec_ind += 1
            await self.inbox.emit_to("orchestrator", messages.ExecutionFailureMessage(
                from_wp=self.context.executing.name if self.context.executing else "None",
                to_wp=self.context.exec_next.name if self.context.exec_next else "None",
                reason=self.context.exec_history
            ))
            self.context.exec_history = {}
            return ExecutorState.WAIT
        
        if not self.context.exec_next:
            print("下一个执行节点不存在，执行器进入等待状态。")
            return ExecutorState.WAIT
        
        _task = tasks.GenerateCodeTask(
            target=self.context.exec_next,
            snapshot=self.context.current.actual_snapshot,
            reason=self.context.exec_next.extra_info.get("feasible_reason", ""),
            error=self.context.exec_history
        )
        response = await self.llm.execute(_task)
        raw_code = response["result"]
        final_code = self.knowledge.inject_dependencies(raw_code)
        final_code = f"""
            {final_code}
        """
        print(f"注入依赖函数后代码:\n{final_code}")
        self.context.exec_history["last_code"] = final_code
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        try:
            execute_result = await asyncio.wait_for(self.mc.execute(final_code), timeout=300.0)
            if execute_result["status"] != 200:
                self.context.snapshot = execute_result["observation"].snapshot
                return ExecutorState.VERIFY
            else:
                raise RuntimeError(f"失败, mineflayer服务器返回状态码: {execute_result['status']}")
        except asyncio.TimeoutError:
            self.context.snapshot = (await self.mc.observe()).snapshot
            self.context.exec_history.setdefault("fail_records", []).append({
                "snapshot": self.context.snapshot,
                "reason": "执行超时"
            })
        except Exception as e:
            self.context.snapshot = (await self.mc.observe()).snapshot
            self.context.exec_history.setdefault("fail_records", []).append({
                "snapshot": self.context.snapshot,
                "reason": f"执行异常: {str(e)}"
            })
        return ExecutorState.GENERATE_CODE
        
    async def handle_verify(self) -> ExecutorState:
        _task = tasks.VerifyTask(
            target=self.context.next,
            imagine=self.context.next.imaginated_snapshot,
            actual=self.context.snapshot
        )
        response = await self.llm.execute(_task)
        reason = response.get("reason", "") 
        is_success = response["result"]
        self.context.token_usage += response.get("token_usage", 0)['uncached_tokens']
        print(f"验证结果: {is_success}")
        if is_success:
            self.context.exec_history = {}
            self.context.exec_ind += 1
            return ExecutorState.WAIT
        else:
            self.context.exec_history.setdefault("fail_records", []).append({
                "snapshot": self.context.snapshot,
                "reason": f"任务未达成预期效果: {reason}"
            })
            return ExecutorState.GENERATE_CODE
    
        