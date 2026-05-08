from typing import Dict, List
import json

from pydantic import BaseModel, ValidationError
from typing import List, Dict, Optional, Any

class Vec3(BaseModel):
    """用于表示三维空间中的坐标或速度向量"""
    x: float
    y: float
    z: float

class Status(BaseModel):
    """机器人的实时生理与物理状态"""
    health: int
    food: int
    saturation: int
    position: Vec3
    velocity: Vec3
    yaw: float
    pitch: float
    onGround: bool
    equipment: List[Optional[str]]
    name: str
    isInWater: bool
    isInLava: bool
    isCollidedHorizontally: bool
    isCollidedVertically: bool
    biome: str
    entities: Dict[str, float]
    timeOfDay: str
    inventoryUsed: int
    elapsedTime: float

class Observation(BaseModel):
    """最外层的全局快照 (Snapshot)"""
    voxels: List[str]
    status: Status
    inventory: Dict[str, int]
    nearbyChests: Dict[str, str]
    blockRecords: List[Any]

    @property
    def snapshot(self) -> 'Snapshot':
        """将 Observation 转换为 Snapshot，供 LLM 使用"""
        return Snapshot(
            inventoryUsed=self.status.inventoryUsed,
            inventory=self.inventory,
            equipment=self.status.equipment,
            position=self.status.position,
            nearbyChests=self.nearbyChests,
            health=self.status.health,
            saturation=self.status.saturation,
            food=self.status.food,
            entities=self.status.entities,
            voxels=self.voxels,
            extra_info=""
        )

class Snapshot(BaseModel):
    inventoryUsed: int
    inventory: Dict[str, int]
    equipment: List[Optional[str]]
    position: Vec3
    nearbyChests: Dict[str, str]
    voxels: List[str]
    health: int
    saturation: int
    food: int
    entities: Dict[str, float]
    extra_info: Optional[str] = None
    
    @property
    def dict(self):
        return self.model_dump()
    
    @property
    def json(self):
        return self.model_dump_json(ensure_ascii=False)
    
    @property
    @staticmethod
    def schema() -> str:
        return json.dumps({
            "type": "object",
            "properties": {
                "inventory": {"type": "object", "additionalProperties": {"type": "integer"}},
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"}
                    }
                },
                "nearbyChests": {"type": "object", "additionalProperties": {"type": "string"}},
                "equipment": {"type": "array", "items": {"type": ["string", "null"]}},
                "health": {"type": "integer"},
                "saturation": {"type": "integer"},
                "food": {"type": "integer"},
                "entities": {"type": "object", "additionalProperties": {"type": "number"}},
                "voxels": {"type": "array", "items": {"type": "string"}},
                "extra_info": {"type": "string"}
            },
        }, ensure_ascii=False)

    @staticmethod
    def parse(json_str: str) -> 'Snapshot':
        try:
            snapshot = Snapshot.model_validate_json(json_str)
            print("✅ JSON 完全符合格式，解析成功！")
        except ValidationError as e:
            print("❌ JSON 不符合格式，解析失败！")
            print(e.errors()) 
        return snapshot
    
    @staticmethod
    def default():
        return Snapshot(
            inventory={},
            inventoryUsed=0,
            equipment=[None] * 6,
            position=Vec3(x=0.0, y=0.0, z=0.0),
            nearbyChests={},
            health=20,
            saturation=20,
            food=20,
            entities={},
            voxels=[],
            extra_info=""
        )