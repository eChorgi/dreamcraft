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
    description: str
    
    @property
    def dict(self):
        return {
            "inventory": self.inventory,
            "equipment": self.equipment,
            "health": self.health,
            "hunger": self.hunger,
            "entities": self.entities,
            "voxels": self.voxels,
            "description": self.description
        }
    
    @property
    def json(self):
        return json.dumps(self.dict, ensure_ascii=False)

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
            description=""
        )