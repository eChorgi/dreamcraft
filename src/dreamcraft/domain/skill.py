import json


class Skill:
    def __init__(self, name: str, description: str = None, impact: str = None, dependency: list["Skill"] = None, function: str = None):
        self.name = name
        self.description = description
        self.impact = impact
        self.function = function
        self.dependency = dependency if dependency else []
    
    def __repr__(self):
        return json.dumps(self.json, ensure_ascii=False)
    
    def __str__(self):
        return json.dumps(self.json, ensure_ascii=False)


    @property
    def json(self):
        return {
            "name": self.name,
            "description": self.description,
            "impact": self.impact,
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
        return {
            "name": self.name,
            "description": self.description,
            "impact": self.impact,
            "function": self.function,
            "dependency": [d.name for d in self.dependency]
        }
        
