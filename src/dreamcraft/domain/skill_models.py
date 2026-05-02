class Skill:
    def __init__(self, name: str, description: str = None, impact: str = None, dependency: list["Skill"] = None, javascript: str = None):
        self.name = name
        self.description = description
        self.impact = impact
        self.javascript = javascript
        self.dependency = dependency if dependency else []
    
    @property
    def summary(self):
        _sum = """## 标识符
{name}

## 功能简述
{description}

## 作用效果
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
            "javascript": self.javascript,
            "dependency": [d.name for d in self.dependency]
        }
        
