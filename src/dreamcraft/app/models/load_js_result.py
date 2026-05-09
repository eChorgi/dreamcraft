from dataclasses import dataclass

from dreamcraft.domain import Skill

@dataclass
class LoadJSResults:
    skills: set[Skill]
    private_skills: set[Skill]

@dataclass
class LoadJSResult:
    skill: Skill
    is_private: bool
