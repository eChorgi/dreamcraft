from typing import Protocol
from langchain_core.tools import tool
import numpy as np
from dreamcraft.domain.quest import Quest, Waypoint

from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage

from dreamcraft.domain.skill import Skill
from dreamcraft.domain.snapshot import Snapshot
from dreamcraft.domain.wiki import WikiDocument

class IQuestRepo(Protocol):
    def add(self, quest: Quest):
        ...
    def get_quest(self, quest_id: int) -> Quest:
        ...
    def get_waypoint(self, ref: Waypoint | int | str, quest: Quest = None) -> Waypoint:
        ...

class IWikiRepo(Protocol):
    def query(self, query_embedding, top_k=3) -> list[dict]:
        ...

class ISkillRepo(Protocol):
    def query(self, query_embedding, top_k=3) -> list[dict]:
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
    def react(self, role: str, query: str) -> str:
        ...
    def imaginate(self, completed: list[Waypoint | str], target: Waypoint | str, snapshot: Snapshot) -> str:
        ...
    def feasibility_check(self, completed: list[Waypoint | str], target: Waypoint | str, snapshot: Snapshot) -> str:
        ...

class IToolRepo(Protocol):
    @property
    def all_tools(self) -> dict[str, tool]:
        ...
    def get_tools(self, tools: list[str]) -> list[tool]:
        ...