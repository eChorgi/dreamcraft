
import re
import esprima
from string import Template
from typing import ClassVar
from pydantic import BaseModel, ConfigDict

from dreamcraft.domain import Snapshot, Waypoint

class BaseTask(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    """所有任务的基座"""
    max_iterations: int = 10
    max_retries: int = 5
    enable_context_compression: bool = True

    extra_tools: ClassVar[list[str]] = []
    # 增加两个类变量，指明该任务对应哪两个模板文件！
    @property
    def name(self) -> str:
        """默认的任务名称是类名转换成小写加下划线的形式，可以被 PromptRepo 识别到对应的模板文件"""
        class_name = self.__class__.__name__.replace("Task", "")
        class_name = re.sub(r'(.)([A-Z])([a-z])', r'\1_\2\3', class_name)
        class_name = re.sub(r'([a-z])([A-Z])', r'\1_\2', class_name)
        return class_name.lower()
    
    @property
    def role_template(self) -> str:
        """默认的角色模板名称"""
        return f"{self.name}_role"
    
    @property
    def query_template(self) -> str:
        """默认的查询模板名称"""
        return f"{self.name}_query"

    def get_prompt_kwargs(self) -> dict:
        """自动化格式化参数，供 Prompt 模板替换使用"""
        kwargs = {}
        # 自动扫描当前类的所有字段，按规则格式化
        for field_name, value in self.__dict__.items():
            kwargs[field_name] = str(value)
        return kwargs
    
    def parser(self, text) -> dict:
        """默认的 parser 是一个简单的身份函数，直接返回原始字符串"""
        return {
            "result": text,
            "reason": None
        }

class FeasibilityCheckTask(BaseTask):
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot
    extra_tools = ["query_skill"]

    def parser(self, text) -> dict:
        return parse_bool(text)

class ImaginateTask(BaseTask):
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot
    def parser(self, text) -> dict:
        reason = None
        result = None
        try:
            result = Snapshot.model_validate_json(text)
        except Exception as e:
            reason = f"解析失败，错误信息: {str(e)}"
        return {
            "result": result,
            "reason": None if result else f"遇到错误: {reason}。**参考格式**:\n{Snapshot.schema()}"
        }

# class ChatTask(BaseTask):
#     query: str

class ExpandPathTask(BaseTask):
    completed: list[Waypoint | str]
    target: Waypoint | str
    snapshot: Snapshot
    def parser(self, text) -> dict:
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
    target: Waypoint
    snapshot: Snapshot
    max_valid_index: int
    extra_tools = ["get_next_waypoints"]
    def parser(self, text) -> dict:
        result = None
        reason = None
        try:
            text = text.strip()
            if text.isdigit() and 0 <= int(text) <= self.max_valid_index:
                result = int(text)
        except Exception as e:
            reason = e.__str__()
        return {
            "result": result,
            "reason": None if result else f"遇到错误{reason}，请直接输出下一个要执行的步骤的数字索引，不要输出其他内容。"
        }
    
class GranularityCheckTask(BaseTask):
    target: Waypoint | str
    snapshot: Snapshot
    def parser(self, text) -> dict:
        return parse_bool(text)
    
class GenerateCodeTask(BaseTask):
    target: Waypoint | str
    snapshot: Snapshot
    reason: str = "无"
    error: str = "无"
    extra_tools = ["query_skill"]
    def parser(self, text) -> dict:
        return parse_js(text)
    
class VerifyTask(BaseTask):
    target: Waypoint | str
    imagine: Snapshot
    actual: Snapshot
    def parser(self, text) -> dict:
        return parse_bool(text)
    



def parse_bool(text) -> dict:
    result = None
    if "True" in text: result = True
    if "False" in text: result = False
    return {
        "result": result,
        "reason": None if result is not None else f"请直接明确回复 'True' 或 'False'，不要输出其他内容。"
    }

def parse_js(text) -> dict:
    result = None
    reason = None
    if text.startswith("```js") and text.endswith("```"):
        text = text[5:-3].strip()
    elif text.startswith("```javascript") and text.endswith("```"):
        text = text[13:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()

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