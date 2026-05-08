
from string import Template
from typing import ClassVar

import esprima
from pydantic import BaseModel

from dreamcraft.domain.observation import Snapshot
from dreamcraft.domain.waypoint import Waypoint

def parse_bool(text) -> dict:
    result = None
    if "True" in text: result = True
    if "False" in text: result = False
    return {
        "result": result,
        "reason": None if result is not None else f"请直接明确回复 'True' 或 'False'，不要输出其他内容。"
    }

class BaseTask(BaseModel):
    """所有任务的基座"""
    max_iterations: int = 10
    max_retries: int = 5
    enable_context_compression: bool = True

    prompt_name: ClassVar[str] = ""
    extra_tools: ClassVar[list[str]] = []
    def parse(self, text) -> dict:
        """默认的 parser 是一个简单的身份函数，直接返回原始字符串"""
        return {
            "result": text,
            "reason": None
        }

class FeasibilityCheckTask(BaseTask):
    prompt_name = "feasibility_check"
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot

    def parse(self, text) -> dict:
        return parse_bool(text)
    extra_tools = ["query_skill"]

class ImaginateTask(BaseTask):
    prompt_name = "imaginate"
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot
    def parse(self, text) -> dict:
        result = Snapshot.parse(self, text)
        return {
            "result": result,
            "reason": None if result else f"请严格按照 JSON 格式输出完整信息。**参考格式**:\n{Snapshot.schema}"
        }
    extra_tools = ["query_skill"]

class ChatTask(BaseTask):
    prompt_name = "react"
    query: str

class ExpandPathTask(BaseTask):
    prompt_name = "expand_path"
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot
    def parse(self, text) -> dict:
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
    
class NavigateTask(BaseTask):
    prompt_name = "navigate"
    target: Waypoint
    snapshot: Snapshot
    max_valid_index: int
    def parse(self, text) -> dict:
        if text is None:
            result = None
        try:
            ind = ind.strip()
            if not ind.isdigit():
                return None
            ind = int(ind)
            if ind < 0 or ind > self.max_valid_index:
                return None
        except Exception as e:
            reason = e.__str__()
        return {
            "result": result,
            "reason": None if result else f"遇到错误{reason}，请直接输出下一个要执行的步骤的数字索引，不要输出其他内容。"
        }
    
class CheckGranularityTask(BaseTask):
    prompt_name = "check_granularity"
    target: Waypoint | str
    snapshot: Snapshot
    def parse(self, text) -> dict:
        return parse_bool(text)
    
class GenerateCodeTask(BaseTask):
    prompt_name = "generate_code"
    target: Waypoint | str
    snapshot: Snapshot
    reason: str
    error: str = None
    def parse(self, text) -> dict:
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