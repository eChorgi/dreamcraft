from dreamcraft.domain.quest import Quest
from dreamcraft.domain.waypoint import Waypoint

class QuestContext:
    """上下文总线：在整个状态机流转中传递的唯一数据包"""
    def __init__(self, target):
        self.target: str = target
        self.quest: Quest | None = None  # 当前任务地图
        self.current: Waypoint | None = None
        self.target: Waypoint | None = None 

        self.snapshot = None

        self.executing: Waypoint | None = None # 当前正在执行的节点

        self.completed: list[Waypoint] = []  # 已完成的节点列表

        self.executable_waypoints: set[Waypoint] = set()
        self.error_history = []
        self.step_count = 0