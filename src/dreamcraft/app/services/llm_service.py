import asyncio
import json
import re
from string import Template
import esprima
from typing import List, Union
from dreamcraft.utils.print_helper import ipynb_print

import concurrent

from dreamcraft.app.protocols import ILLMClient, IPromptRepo, IQuestRepo, IToolRepo
from langchain.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

from dreamcraft.domain.waypoint import Waypoint
from dreamcraft.domain.snapshot import Snapshot

class LLMService:
    """负责与 LLM 进行交互的服务类，提供一个统一的接口供 Orchestrator 调用"""
    
    def __init__(self, llm: ILLMClient, prompt: IPromptRepo, tool: IToolRepo, quest: IQuestRepo):
        self.llm = llm
        self.prompt = prompt
        self.tool = tool
        self.quest = quest

    async def react(
        self, 
        prompt: str, 
        tools: List[Union[tool, str]],
        parser: callable = lambda x: {"result": None, "reason": None},  # 默认 parser 是一个简单的身份函数，直接返回原始字符串 
        max_iterations: int = 10, 
        max_retries: int = 5,
        history_messages: list = None,
    ) -> dict:
        """核心功能：根据输入的 query 进行思考、工具调用、观察结果、再思考的循环"""
        
        tools = [self.tool.all_tools[t] if isinstance(t, str) else t for t in tools]
        llm_with_tools = self.llm.with_tools(tools)
        tool_dict = {t.name: t for t in tools}
        total_tokens = 0
        cached_tokens = 0
        reason = ""
        full_messages = history_messages if history_messages is not None else []
        messages = history_messages if history_messages is not None else []
        if messages and not isinstance(messages[0], SystemMessage):
            # 如果历史消息存在但第一个不是 SystemMessage，则把 prompt 插入到第一条
            messages.insert(0, SystemMessage(content=prompt))
        elif messages and isinstance(messages[0], SystemMessage):
            # 如果第一条已经是 SystemMessage，更新它的内容为新的 prompt
            messages[0] = SystemMessage(content=prompt)
        elif not messages:
            # 如果没有历史消息，直接添加 SystemMessage
            messages.append(SystemMessage(content=prompt))  # 首先把 prompt 作为上下文输入
            full_messages.append(SystemMessage(content=prompt))

        error_count = 0
        current_iteration = 0

        print(f"开始执行大模型循环...提示词: {prompt.replace('\n', ' ')}")

        while current_iteration < max_iterations and error_count < max_retries:
            print(f"\n--- 第 {current_iteration + 1} 轮思考 ---")

            # messages.append(AIMessage(content=f"当前思考轮次: {current_iteration + 1}"))
            # 1. 把全套历史记录喂给 LLM
            ai_msg = await llm_with_tools.ainvoke(messages)
            messages.append(ai_msg) # 把 LLM 的回复（不管是不是工具调用）记录到历史中
            full_messages.append(ai_msg)
            token_usage = ai_msg.response_metadata.get("token_usage", 0)
            prompt_tokens_details = token_usage.get("prompt_tokens_details", {})
            total_tokens += token_usage.get("total_tokens", 0)
            cached_tokens += prompt_tokens_details.get("cached_tokens", 0)
            # 2. 判断是否还需要调用工具
            if not ai_msg.tool_calls:
                # 没有 tool_calls 说明 LLM 认为信息已经充足，输出了最终答案
                if "【Final Answer】" in ai_msg.content:
                    result = ai_msg.content.split("【Final Answer】")[-1].strip()
                    parsed = parser(result)
                    parsed_result = parsed.get("result")
                    parse_fail_reason = parsed.get("reason")

                    if parsed_result is not None:
                        print(f"提取到的最终答案是: {parsed_result}")
                        if "【Reason】" in ai_msg.content:
                            reason = ai_msg.content.split("【Reason】")[-1].split("【Final Answer】")[0].strip()
                            print(f"LLM 给出的理由是: {reason}")
                        break

                    _error_msg = HumanMessage(content=f"⚠️ 系统拦截：你的回答严重违规! \n 理由: {parse_fail_reason if parse_fail_reason else '请在【Final Answer】后面严格按照要求的格式输出你的回答！'}")
                    messages.append(_error_msg)
                    full_messages.append(_error_msg)
                    max_iterations += 1
                    error_count += 1
                else :
                    print("AI 的回复中没有包含【Final Answer】标记，要求重新思考。")
                    warning_msg = (
                        "⚠️ 系统拦截：你的回答格式严重违规！你既没有触发真正的 Tool Call，也没有给出包含 '【Final Answer】' 的最终计划。\n"
                        "请重新阅读上一轮的工具返回结果，更新你的【信息消化】，然后立即发起一次【全新的 Tool Call】查缺补漏，"
                        "或者输出详尽的 Final Answer 结束任务。不要在文本里汇报 '已调用'！"
                    )
                    messages.append(HumanMessage(content=warning_msg))
                    full_messages.append(HumanMessage(content=warning_msg))
                    max_iterations += 1
                    error_count += 1
                    continue

            # 3. 如果走到了这里，说明有 tool_calls，准备执行
            print(f"🔍 AI 决定并行调用 {len(ai_msg.tool_calls)} 个工具...")
            tool_results_dict = {}
            summary_content = None
            # 1. 准备协程任务和映射字典
            tasks = []
            tool_calls_map = []  # 用来记录任务顺序，以便稍后对号入座

            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                tool_func = tool_dict.get(tool_name)

                # 将协程对象（不加 await）加入列表。注意使用 ainvoke
                tasks.append(tool_func.ainvoke(tool_args))
                tool_calls_map.append(tool_call)

            # 2. 并发执行所有工具
            # return_exceptions=True 让报错的工具返回 Exception 对象而不是直接崩溃退出
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 3. 处理返回结果
            for idx, observation in enumerate(results):
                tool_call = tool_calls_map[idx]

                if isinstance(observation, Exception):
                    observation_str = f"⚠️ 工具执行报错: {str(observation)}。请检查参数并重试。"
                    print(f"  ❌ 工具 '{tool_call['name']}' 执行失败: {observation}")
                else:
                    observation_str = observation
                    print(f"  ✅ 工具 '{tool_call['name']}' 执行成功。")

                # 处理 summary 逻辑
                if tool_call["name"] == "summary":
                    summary_content = observation_str
                    if current_iteration > 0:
                        print(f"  📝 提取到摘要内容: {observation_str}")
                    else:
                        observation_str = "第一轮没有摘要内容"

                tool_results_dict[tool_call["id"]] = observation_str

            # 2. 严格按照 ai_msg.tool_calls 的原始顺序，把 ToolMessage 加入到消息列表
            for tool_call in ai_msg.tool_calls:
                obs = tool_results_dict[tool_call["id"]]
                # clean_obs = obs.replace("\'", '"').strip() if isinstance(obs, str) else str(obs)
                clean_obs = obs.strip() if isinstance(obs, str) else str(obs)
                messages.append(ToolMessage(
                    content=clean_obs,
                    tool_call_id=tool_call["id"]
                ))
                full_messages.append(ToolMessage(
                    content=clean_obs,
                    tool_call_id=tool_call["id"]
                ))
            print(full_messages)
            # 3. 处理上下文压缩 (在完整的对话回合结束时进行)
            if summary_content and current_iteration > 0:
                len_sum = sum(len(m.content) for m in messages if hasattr(m, 'content') and m.content)
                
                if len_sum >= 4000:
                    original_system_prompt = messages[0].content.split("【全局摘要记忆】")[0].strip()
                    new_system_prompt = f"{original_system_prompt}\n\n【全局摘要记忆】\n{summary_content}"
                    len_to_keep = len(ai_msg.tool_calls)+1
                    content_to_keep = messages[-len_to_keep:]  # 只保留最新一轮工具调用及其结果
                    messages = [
                        SystemMessage(content=new_system_prompt),
                        # HumanMessage(content="请根据全局摘要记忆继续执行你的任务。"), # 维持阵型的常驻提示
                    ] + content_to_keep

            current_iteration += 1

        if current_iteration >= max_iterations:
            print("⚠️ 达到最大思考轮数，强行终止循环，可能是任务太复杂或遇到了死循环。")
            parsed_result = None
        if error_count >= max_retries:
            print("⚠️ 连续多次格式错误，强行终止循环")
            parsed_result = None

        print(f"本次交互使用了 {total_tokens} tokens。")
        print(f"其中 {cached_tokens} tokens 来自上下文缓存，{total_tokens - cached_tokens} tokens 来自本次输入。")
        ipynb_print(full_messages, exclude=["response_metadata", "id", "tool_call_id"])
        return {
            "result": parsed_result,
            "messages": full_messages,
            "reason": reason,
            "token_usage": {
                "total_tokens": total_tokens,
                "cached_tokens": cached_tokens,
                "uncached_tokens": total_tokens - cached_tokens
            }
        }
    


    async def check_feasibility(
        self, 
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
        ) -> dict:
        def parse_bool(text):
            result = None
            if "True" in text: result = True
            if "False" in text: result = False
            return {
                "result": result,
                "reason": None if result is not None else f"请直接明确回复 'True' 或 'False'，不要输出其他内容。"
            }

        response = await self.react(
            prompt = self.prompt.feasibility_check(
                completed = completed,
                target = target,
                snapshot = snapshot,
                enable_context_compression=enable_context_compression
            ),
            parser = parse_bool,
            tools = ["query_wiki", "query_skill", "grep_wiki_files", "read_wiki_section"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries = max_retries,
        )
        return response

    async def imaginate(
        self, 
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> dict:
        def snapshot_parser(text) -> dict:
            result = Snapshot.parse(text)
            return {
                "result": result,
                "reason": None if result else f"请严格按照 JSON 格式输出完整信息。**参考格式**:\n{Snapshot.schema}"
            }
        response = await self.react(
            prompt = self.prompt.imaginate(
                completed = completed,
                target = target,
                snapshot = snapshot,
                enable_context_compression=enable_context_compression
            ),
            parser=snapshot_parser,
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries= max_retries,
        )
        return response
    
    async def chat(
        self, 
        query: str, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> dict:
        response = await self.react(
            prompt = self.prompt.react(
                role="你是一个 Minecraft 游戏聊天助手，负责与玩家进行对话，提供游戏内的帮助和建议。",
                query = query,
                enable_context_compression=enable_context_compression
            ),
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries= max_retries,
            enable_context_compression=enable_context_compression
        )
        return response

    async def expand_path(
        self,
        completed: list[Waypoint | str], 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> dict:
        def path_parser(text) -> list[Waypoint] | None:
            text_lines = text.strip().split("\n")
            waypoints = []
            for line in text_lines:
                if not line.strip():
                    continue
                if ":" not in line:
                    waypoints.append(Waypoint(name=line.strip()))
                    continue
                name, action = line.split(":", 1)
                name = name.replace("\\n", "").strip()
                action = action.replace("\\n", "").strip()
                waypoints.append(Waypoint(name=name, description=action))
            return {
                "result": waypoints,
                "reason": None if waypoints else "请严格按照每行一个[步骤名称]:[动作指令]的格式输出一个子目标列表！"
            }    
        response = await self.react(
            prompt = self.prompt.expand_path(
                completed = completed,
                snapshot = snapshot,
                target = target.line if isinstance(target, Waypoint) else target,
                enable_context_compression=enable_context_compression
            ),
            parser=path_parser,
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries= max_retries,
        )
        if response["result"][-1].line == (target.line if isinstance(target, Waypoint) else target):
            response["result"] = response["result"][:-1]
        return response
    
    async def navigate(
        self,
        target: Waypoint, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
    ) -> dict:
        def navigate_parser(ind: int) -> Waypoint | None:
            if ind is None:
                result = None
            if isinstance(ind, str):
                try:
                    ind = ind.strip()
                    if not ind.isdigit():
                        return None
                    ind = int(ind)
                    result = self.quest.get_waypoint(ind)
                except Exception as e:
                    reason = e.__str__()
            return {
                "result": result,
                "reason": None if result else f"遇到错误{reason}，请直接输出下一个要执行的步骤的数字索引，不要输出其他内容。"
            }
        response = await self.react(
            prompt = self.prompt.navigate(
                snapshot = snapshot,
                target = target.details if isinstance(target, Waypoint) else target,
                enable_context_compression=enable_context_compression
            ),
            parser=navigate_parser,
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section", "get_next_waypoints"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries= max_retries,
        )
        return response
    
    async def check_granularity(
        self, 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
        ) -> dict:
        def parse_bool(text):
            result = None
            if "True" in text: result = True
            if "False" in text: result = False
            return {
                "result": result,
                "reason": None if result is not None else f"请直接明确回复 'True' 或 'False'，不要输出其他内容。"
            }

        response = await self.react(
            prompt = self.prompt.granularity_check(
                target = target,
                snapshot = snapshot,
                enable_context_compression=enable_context_compression
            ),
            parser = parse_bool,
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries = max_retries,
        )
        return response
    
    async def generate_code(
        self, 
        target: Waypoint | str, 
        snapshot: Snapshot, 
        reason: str,
        max_iterations: int = 10, 
        max_retries: int = 5, 
        enable_context_compression: bool = True
        ) -> bool:
        def parse_js(text):
            result = None
            reason = None
            if text.startswith("```js") and text.endswith("```"):
                text = text[5:-3].strip()
            elif text.startswith("```") and text.endswith("```"):
                text = text[3:-3].strip()
            elif text.startswith("```javascript") and text.endswith("```"):
                text = text[11:-3].strip()

            js_template = Template("(async () => { $code_body })();")
            final_js = js_template.substitute(code_body=text)
            try:
                parsed = esprima.parseScript(final_js)
                result = text
            except Exception as e:
                reason = f"生成的代码无法通过语法检查，错误信息: {str(e)}"
            return {
                "result": result,
                "reason": reason
            }

        response = await self.react(
            prompt = self.prompt.generate_code(
                target = target,
                snapshot = snapshot,
                reason = reason,
                enable_context_compression=enable_context_compression
            ),
            parser = parse_js,
            tools = ["query_wiki", "grep_wiki_files", "read_wiki_section", "query_skill"] + (["summary"] if enable_context_compression else []),
            max_iterations = max_iterations,
            max_retries = max_retries,
        )
        return response