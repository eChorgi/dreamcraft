from dataclasses import dataclass
from typing import Dict, List


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
