from typing import Protocol
from langchain_core.tools import tool
import numpy as np
from dreamcraft.domain.goal_models import GoalMap

from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage

from dreamcraft.domain.skill_models import Skill
from dreamcraft.domain.wiki_models import WikiDocument

class IGoalRepo(Protocol):
    def add(self, goal_map: GoalMap):
        ...
    def get(self, goal_id: int) -> GoalMap:
        ...

class IWikiRepo(Protocol):
    def query(self, query_embedding, top_k=3) -> list[WikiDocument]:
        ...

class ISkillRepo(Protocol):
    def query(self, query_embedding, top_k=3) -> list[Skill]:
        ...
    def add(self, skill: Skill, skill_embedding: np.ndarray):
        ...
    def get(self, ref: int | str) -> Skill:
        ...

class ILLMClient(Protocol):
    def embed(self, text: str) -> np.ndarray:
        ...
    def with_tools(self, tools: list[tool]) -> Runnable[LanguageModelInput, AIMessage]:
        ...

class IPromptRepo(Protocol):
    def load(self, name: str)-> str:
        ...
