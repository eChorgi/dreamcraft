from typing import Protocol
from langchain_core.tools import tool
import numpy as np
from dreamcraft.domain.goal_model import GoalMap

from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage

class IGoalRepo(Protocol):
    def add_goal(self, goal_map: GoalMap):
        ...
    def get_goal(self, goal_id: int) -> GoalMap:
        ...

class IWikiRepo(Protocol):
    def search(self, query_embedding, top_k=5) -> list[dict]:
        ...

class ISkillRepo(Protocol):
    def search(self, query_embedding, top_k=5) -> list[dict]:
        ...

class ILLMClient(Protocol):
    def embed(self, text: str) -> np.ndarray:
        ...
    def with_tools(self, tools: list[tool]) -> Runnable[LanguageModelInput, AIMessage]:
        ...

class IPromptRepo(Protocol):
    def load(self, name: str)-> str:
        ...
