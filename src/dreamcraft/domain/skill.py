from dataclasses import dataclass
import json


class Skill:
    def __init__(self, name: str, description: str = None, impact: str = None, dependencies: list["Skill"] = None, function: str = None, provider: str = None):
        self.name = name
        self.description = description
        self.impact = impact
        self.function = function
        self.dependencies:set[Skill] = dependencies if dependencies else set()
        self.provider = provider
    
    def __repr__(self):
        return json.dumps(self.json, ensure_ascii=False)
    
    def __str__(self):
        return json.dumps(self.json, ensure_ascii=False)

    def __eq__(self, value):
        if not isinstance(value, Skill):
            return False
        return self.name == value.name and self.provider == value.provider

    def __hash__(self):
        return hash((self.name, self.provider))

    @property
    def json(self):
        _dict = {
            "name": self.name,
            "description": self.description.replace('"',"`")
        }
        if self.impact:
            _dict["impact"] = self.impact.replace('"',"`")
        return _dict
    
    @property
    def all_json(self):
        return {
            "name": self.name,
            "description": self.description,
            "impact": self.impact,
            "function": self.function,
            "dependencies": [d.name for d in self.dependencies],
        }

    @property
    def summary(self):
        if not self.impact:
            _sum = """### Identifier
{name}
### Description
{description}
        """.format(
            name=self.name,
            description=self.description
        )
        else:
            _sum = """### Identifier
{name}
### Description
{description}
### Impact
{impact}
        """.format(
            name=self.name,
            description=self.description,
            impact=self.impact,
        )
        return _sum
    
    @property
    def dict(self):
        if self.dependencies and isinstance(list(self.dependencies)[0], str):
            print(f"警告: 技能 {self.name} 的依赖项似乎未正确解析，依赖项列表包含字符串而非 Skill 对象")
        return {
            "name": self.name,
            "description": self.description,
            "impact": self.impact,
            "function": self.function,
            "dependencies": [d.name for d in self.dependencies]
        }
    
    def resolve_dependencies(self, layers: list["Skill"] = None):
        dep = set()
        if not layers:
            layers = [self]
        for skill in self.dependencies:
            dep.add(skill)
            if skill in layers:
                continue
            new_deps = skill.resolve_dependencies(layers + [skill])
            dep.update(new_deps)
        return dep

@dataclass
class LoadJSResults:
    skills: set[Skill]
    private_skills: set[Skill]

@dataclass
class LoadJSResult:
    skill: Skill
    is_private: bool
