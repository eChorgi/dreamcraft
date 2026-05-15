from dreamcraft.app import QuestOrchestrator, QuestExecutor, ILLMClient, IPromptRepo, IQuestRepo, ISkillRepo, IToolRepo, IWikiRepo, LLMService, QuestService, KnowledgeService
from dreamcraft.infra import Agent, AzureInstance

class GlobalContainer:
    def __init__(self):
        self._contents = {}

    def register(self, name, instance):
        self._contents[name] = instance

    def get(self, name):
        return self._contents[name]
    
    def __getitem__(self, name):
        return self.get(name)
    
    def __setitem__(self, name, instance):
        self.register(name, instance)
    
    def __getattr__(self, name):
        try:
            return self.get(name)
        except KeyError:
            raise AttributeError(f"'{name}' not found in container")


class InfraContainer(GlobalContainer):
    llm: ILLMClient
    wiki: IWikiRepo
    path: IQuestRepo
    prompt: IPromptRepo
    skill: ISkillRepo
    tool: IToolRepo
    mc: Agent
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