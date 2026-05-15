import asyncio

from dreamcraft.app import MessageBus, QuestOrchestrator, QuestExecutor, LLMService, QuestService, KnowledgeService
from dreamcraft.infra import Agent, AzureInstance, QuestRepo, PromptRepo, WikiRepo, SkillRepo, LLMClient, ToolRepo
from dreamcraft.container import AppContainer, InfraContainer, ServiceContainer
from dreamcraft.config import Settings

# from dreamcraft.app.services.llm_service_mock import LLMServiceMock


class DreamCraft:
    def __init__(self, container: AppContainer = None):
        """
        DreamCraft 主类，负责整体协调和管理。
        """
        if container is None:
            raise ValueError("请通过 DreamCraft.create(settings) 方法创建实例，以确保正确的依赖注入和初始化。")
        self.container = container
        self._running = False
        if not self.container:
            self = self.create(Settings())
    
    @classmethod
    async def create(cls, settings: Settings):
        container = await bootstrap(settings)
        return cls(container)
    
    async def start(self):
        if self._running:
            print("DreamCraft 已经在运行中。")
            return
        self._running = True
        print("启动 DreamCraft...")
        self.container.infra.mc.start()
    
    async def run(self, target: str):
        if not self._running:
            raise RuntimeError("DreamCraft 未启动。 请先调用 start() 方法。")
        print(f"开始执行任务: {target}")
        context = self.container.service.quest.add_quest(target)
        await asyncio.gather(
            self.container.service.orchestrator.run(context),
            self.container.service.executor.run(context)
        )

async def bootstrap(settings: Settings = Settings()):
    # 初始化全局容器和服务
    container = AppContainer()
    infra = InfraContainer()
    service = ServiceContainer()
    message_bus = MessageBus()

    # 初始化基础设施组件
    i_wiki = WikiRepo(settings)
    i_skill = SkillRepo(settings)
    i_llm = LLMClient(settings)
    i_quest = QuestRepo(settings)
    i_prompt = PromptRepo(settings)
    i_azure = None
    if settings.azure_login:
        i_azure = AzureInstance(settings = settings)
    i_mc = Agent(settings, azure_instance=i_azure)

    # 初始化服务层组件
    s_knowledge = KnowledgeService(settings, wiki=i_wiki, llm=i_llm, skill=i_skill)
    s_quest = QuestService(quests=i_quest)

    # 初始化工具管理器
    i_tools = ToolRepo(s_knowledge, s_quest)

    # s_llm = LLMServiceMock(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)
    s_llm = LLMService(llm=i_llm, prompt=i_prompt, tool=i_tools, quest=i_quest)

    # 初始化 Orchestrator
    s_executor = QuestExecutor(bus=message_bus, llm=s_llm, knowledge=s_knowledge, mc=i_mc)
    s_orchestrator = QuestOrchestrator(quest=s_quest, llm=s_llm, prompt=i_prompt, bus=message_bus, mc=i_mc, executor=s_executor)

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

    await asyncio.gather(
        i_wiki.load(),
        i_skill.load()
    )

    return container
