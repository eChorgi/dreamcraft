import os
from typing import Dict

from dreamcraft.app.common.messaging import Mailbox
from dreamcraft.app.orchestrator.action_orchestrator import ActionOrchestrator
from dreamcraft.app.orchestrator.logic_orchestrator import LogicOrchestrator
from dreamcraft.container import GlobalContainer
from dreamcraft.infra.repo.skill_repo import SkillRepo
from dreamcraft.config import settings
from dreamcraft.app.services.goal_service import GoalService
from dreamcraft.app.services.knowledge_service import KnowledgeService
from dreamcraft.infra.env.mineflayer import MineflayerClient
from dreamcraft.infra.llm.openai_llm import LLMClient
from dreamcraft.infra.repo.goal_repo import GoalRepo
from dreamcraft.infra.repo.prompt_repo import PromptRepo
from dreamcraft.infra.repo.wiki_repo import WikiRepo
from dreamcraft.interface.tools.tool_manager import ToolManager

def bootstrap():
    # 初始化全局容器和服务
    container = GlobalContainer()

    llm = LLMClient(settings)
    wiki = WikiRepo(settings)
    i_path = GoalRepo(settings)
    prompt = PromptRepo(settings)
    skill = SkillRepo(settings)

    infra = GlobalContainer()
    container.register("infra", infra)

    infra.register("llm", llm)
    infra.register("wiki", wiki)
    infra.register("path", i_path)
    infra.register("prompt", prompt)
    infra.register("skill", skill)

    knowledge = KnowledgeService(wiki=wiki, llm=llm, skill=skill)
    s_path = GoalService(goals=i_path)
    
    service = GlobalContainer()
    container.register("service", service)

    tools = ToolManager(knowledge)
    infra.register("tool", tools)

    logic_inbox = Mailbox()
    action_inbox = Mailbox()
    logic = LogicOrchestrator(
        goals=s_path, 
        llm=llm, 
        prompt=prompt,
        inbox=logic_inbox,  # 这里你需要实现一个 Mailbox 类，或者使用现成的消息队列
        outbox=action_inbox
    )
    action = ActionOrchestrator(
        inbox=action_inbox,
        outbox=logic_inbox,
    )
    
    service.register("logic", logic)
    service.register("action", action)

    service.register("knowledge", knowledge)
    service.register("path", s_path)
    return container

class DreamCraft:
    def __init__(
        self,
        mc_port: int = None,
        azure_login: Dict[str, str] = None,
        # openai_api_key: str = None,
        # env_wait_ticks: int = 20,
        # max_iterations: int = 160,
        # reset_placed_if_failed: bool = False,
        # action_agent_task_max_retries: int = 4,
    ):
        """
        DreamCraft 主类，负责整体协调和管理。
        """
        env = MineflayerClient(settings, mc_port=mc_port, azure_login=azure_login)
        
        self.container = bootstrap()

    def learn(self, reset_env=True):
        self.env.reset(
            options={
                "mode": "hard",
                "wait_ticks": self.env_wait_ticks,
            }
        )
        self.last_events = self.env.step("")
