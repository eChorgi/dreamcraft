from dreamcraft.app.core.message import MessageBus
from dreamcraft.app.core.quest_executor import QuestExecutor
from dreamcraft.app.core.quest_orchestrator import QuestOrchestrator
from dreamcraft.app.protocols import ILLMClient, IPromptRepo, IQuestRepo, ISkillRepo, IToolRepo, IWikiRepo
from dreamcraft.app.services.llm_service import LLMService
from dreamcraft.app.services.llm_service_mock import LLMServiceMock
from dreamcraft.container import GlobalContainer
from dreamcraft.infra.env.azure_instance import AzureInstance
from dreamcraft.infra.repo.skill_repo import SkillRepo
from dreamcraft.config import settings
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.app.services.knowledge_service import KnowledgeService
from dreamcraft.infra.env.minecraft_client import MinecraftClient
from dreamcraft.infra.llm.openai_llm import LLMClient
from dreamcraft.infra.repo.quest_repo import QuestRepo
from dreamcraft.infra.repo.prompt_repo import PromptRepo
from dreamcraft.infra.repo.wiki_repo import WikiRepo
from dreamcraft.interface.tool_repo import ToolRepo

def bootstrap(azure_login=False):
    #类型提示
    class InfraContainer(GlobalContainer):
        llm: ILLMClient
        wiki: IWikiRepo
        path: IQuestRepo
        prompt: IPromptRepo
        skill: ISkillRepo
        tool: IToolRepo
        mc: MinecraftClient
        azure: AzureInstance
    
    class ServiceContainer(GlobalContainer):
        knowledge: KnowledgeService
        quest: QuestService
        llm: LLMService
        orchestrator: QuestOrchestrator
        executor: QuestExecutor

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
    i_azure = None
    if azure_login:
        i_azure = AzureInstance(settings = settings)
    i_mc = MinecraftClient(settings, azure_instance=i_azure)

    # 初始化服务层组件
    s_knowledge = KnowledgeService(settings, wiki=i_wiki, llm=i_llm, skill=i_skill)
    s_quest = QuestService(quests=i_quest)

    # 初始化工具管理器
    i_tools = ToolRepo(s_knowledge, s_quest)

    # s_llm = LLMServiceMock(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)
    s_llm = LLMService(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)

    # 初始化 Orchestrator
    s_orchestrator = QuestOrchestrator(s_quest=s_quest, llm=s_llm, prompt=i_prompt, bus=message_bus)
    s_executor = QuestExecutor(bus=message_bus, quest=s_quest, llm=s_llm, knowledge=s_knowledge, mc_client=i_mc)

    container.register("infra", infra)
    container.register("service", service)
    infra.register("llm", i_llm)
    infra.register("wiki", i_wiki)
    infra.register("quest", i_quest)
    infra.register("prompt", i_prompt)
    infra.register("skill", i_skill)
    infra.register("tool", i_tools)
    infra.register("azure", i_azure)
    infra.register("mc", i_mc)
    service.register("knowledge", s_knowledge)
    service.register("quest", s_quest)
    service.register("llm", s_llm)
    service.register("orchestrator", s_orchestrator)
    service.register("executor", s_executor)

    return container

class DreamCraft:
    def __init__(
        self,
        azure_login: bool = False,
    ):
        """
        DreamCraft 主类，负责整体协调和管理。
        """
        self.container = bootstrap(azure_login=azure_login)
        self.mc_client = self.container.infra.mc

    def learn(self, reset_env=True):
        self.mc_client.reset(
            options={
                "mode": "hard"
            }
        )
        self.last_events = self.mc_client.step("")
