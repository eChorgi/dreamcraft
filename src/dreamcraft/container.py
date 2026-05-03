from typing import Dict
from dreamcraft.config import settings
from dreamcraft.app.services.quest_service import QuestService
from dreamcraft.infra.env.mineflayer import MineflayerClient
from dreamcraft.infra.llm.openai_llm import LLMClient


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

# class AppContainer:
#     """应用容器，负责管理应用中的各种服务和组件"""
#     def __init__(self,
#             mc_port: int = settings.mc_port,
#             azure_login: Dict[str, str] = settings.azure_login,
#             mineflayer_port: int = settings.mineflayer_port,
#             env_request_timeout: int = settings.mineflayer_request_timeout         
#         ):
#         self.path_manager = PathManager()
#         self.mineflayer = MineflayerClient(
#             mc_port=mc_port,
#             azure_login=azure_login,
#             server_port=mineflayer_port,
#             request_timeout=env_request_timeout,
#         )
#         self.llm = OpenaiLLMClient()