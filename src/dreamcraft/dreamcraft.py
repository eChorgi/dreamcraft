import os
from typing import Dict

from dreamcraft.app.core.messaging import MessageBus
from dreamcraft.app.core.quest_orchestrator import QuestOrchestrator
from dreamcraft.app.protocols import ILLMClient, IPromptRepo, IQuestRepo, ISkillRepo, IToolRepo, IWikiRepo
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.app.services.llm_service_mock import LLMServiceMock
from dreamcraft.container import GlobalContainer
from dreamcraft.infra.repo.skill_repo import SkillRepo
from dreamcraft.config import settings
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.knowledge_service import KnowledgeService
from dreamcraft.infra.env.mineflayer_client import MineflayerClient
from dreamcraft.infra.llm.openai_llm import LLMClient
from dreamcraft.infra.repo.quest_repo import QuestRepo
from dreamcraft.infra.repo.prompt_repo import PromptRepo
from dreamcraft.infra.repo.wiki_repo import WikiRepo
from dreamcraft.interface.tool_repo import ToolRepo

def bootstrap():
    class InfraContainer(GlobalContainer):
        llm: ILLMClient
        wiki: IWikiRepo
        path: IQuestRepo
        prompt: IPromptRepo
        skill: ISkillRepo
        tool: IToolRepo
    
    class ServiceContainer(GlobalContainer):
        knowledge: KnowledgeService
        quest: QuestService
        llm: LLMServiceMock
        orchestrator: QuestOrchestrator


    class AppContainer(GlobalContainer):
        infra: InfraContainer
        service: ServiceContainer

    # 初始化全局容器和服务
    container = AppContainer()
    infra = InfraContainer()
    service = ServiceContainer()
    message_bus = MessageBus()

    # 初始化基础设施组件
    i_llm = LLMClient(settings)
    i_wiki = WikiRepo(settings)
    i_quest = QuestRepo(settings)
    i_prompt = PromptRepo(settings)
    i_skill = SkillRepo(settings)

    # 初始化服务层组件
    s_knowledge = KnowledgeService(settings, wiki=i_wiki, llm=i_llm, skill=i_skill)
    s_quest = QuestService(quests=i_quest)

    # 初始化工具管理器
    i_tools = ToolRepo(s_knowledge, s_quest)

    # s_llm = LLMServiceMock(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)
    s_llm = LLMService(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)

    # 初始化 Orchestrator
    s_quest = QuestOrchestrator(s_quest=s_quest, llm=s_llm, prompt=i_prompt, bus=message_bus)
    # o_action = QuestRunner(inbox=action_inbox,outbox=quest_inbox)

    container.register("infra", infra)
    container.register("service", service)
    infra.register("llm", i_llm)
    infra.register("wiki", i_wiki)
    infra.register("quest", i_quest)
    infra.register("prompt", i_prompt)
    infra.register("skill", i_skill)
    infra.register("tool", i_tools)
    service.register("knowledge", s_knowledge)
    service.register("quest", s_quest)
    service.register("llm", s_llm)

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
        
        self.container = bootstrap()
        self.bot = MineflayerClient(settings, mc_port=mc_port, azure_login=azure_login)

    def learn(self, reset_env=True):
        self.bot.reset(
            options={
                "mode": "hard",
                "wait_ticks": self.env_wait_ticks,
            }
        )
        self.last_events = self.bot.step("")
