from dataclasses import dataclass
from typing import Dict, List
import json

from pydantic import TypeAdapter, ValidationError


@dataclass
class Snapshot:
    inventory: Dict[str, int]
    equipment: Dict[str, str]
    health: int
    hunger: int
    entities: List[str]
    voxels: List[str]
    extra_info: str
    
    @property
    def dict(self):
        return {
            "inventory": self.inventory,
            "equipment": self.equipment,
            "health": self.health,
            "hunger": self.hunger,
            "entities": self.entities,
            "voxels": self.voxels,
            "extra_info": self.extra_info
        }
    
    @property
    def json(self):
        return json.dumps(self.dict, ensure_ascii=False)
    
    @property
    def details(self):
        return {
            "inventory": self.inventory,
            "equipment": self.equipment,
            "health": self.health,
            "hunger": self.hunger,
            "entities": self.entities,
            "voxels": self.voxels,
            "extra_info": self.extra_info
        }
    
    @property
    @staticmethod
    def schema() -> str:
        return json.dumps({
            "type": "object",
            "properties": {
                "inventory": {"type": "object", "additionalProperties": {"type": "integer"}},
                "equipment": {"type": "object", "additionalProperties": {"type": "string"}},
                "health": {"type": "integer"},
                "hunger": {"type": "integer"},
                "entities": {"type": "array", "items": {"type": "string"}},
                "voxels": {"type": "array", "items": {"type": "string"}},
                "extra_info": {"type": "string"}
            },
        }, ensure_ascii=False)

    @staticmethod
    def parse(json_str: str) -> 'Snapshot':
        adapter = TypeAdapter(Snapshot)
        try:
            data = json.loads(json_str)
            snapshot = adapter.validate_python(data)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"⚠️ JSON 解析错误: {e}")
            return None
        return snapshot
    
    @staticmethod
    def default():
        return Snapshot(
            inventory={},
            equipment={},
            health=20,
            hunger=20,
            entities=[],
            voxels=[],
            extra_info=""
        )