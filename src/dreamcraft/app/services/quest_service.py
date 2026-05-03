
from dreamcraft.domain.quest import Quest, Waypoint
from dreamcraft.app.protocols import IQuestRepo

class QuestService:
    def __init__(self, quests : IQuestRepo = None):
        self.quests = quests
    
    def __getitem__(self, key):
        return self.quests.get_map(key)

    def new_quest(self, target: str):
        """根据新的目标初始化路径"""
        origin = Waypoint(description = "开始")
        target = Waypoint(description = target)
        origin.insert_after(target)
        m = Quest(origin = origin, target = target)
        self.quests.add(m)
        print(f"新建目标地图: {m}")
        return m
    
    def expand_to_path(self, waypoint: Waypoint | int | str, waypoints: list[Waypoint | str], quest: Quest = None):
        """根据当前目标扩展路径，生成新的子目标"""

        current = self.get_waypoint(waypoint, quest)
        current.expand_to_path(waypoints)
    
    def get_waypoint(self, ref: Waypoint | int | str, quest: Quest = None) -> Waypoint:
        """根据节点引用获取节点对象"""
        return self.quests.get_waypoint(ref, quest)
    