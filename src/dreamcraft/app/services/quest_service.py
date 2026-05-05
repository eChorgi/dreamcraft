
from dreamcraft.domain.quest import Quest
from dreamcraft.domain.waypoint import Waypoint
from dreamcraft.app.protocols import IQuestRepo
from dreamcraft.domain.snapshot import Snapshot

class QuestService:
    def __init__(self, quests : IQuestRepo = None):
        self.quests = quests

    def add_quest(self, target: str | Quest) -> Quest:
        """根据新的目标初始化路径"""
        if isinstance(target, Quest):
            quest = target
        else:
            origin = Waypoint(name = "开始")
            origin.actual_snapshot = Snapshot.default()  # 初始状态快照
            origin.imaginated_snapshot = Snapshot.default()  # 初始状态快照
            target = Waypoint(name = target)
            origin.insert_after(target)
            quest = Quest(origin = origin, target = target)
        self.quests.add(quest)
        print(f"添加目标地图: {quest}")
        return quest

    def expand_between(self, start: Waypoint | int | str, end: Waypoint | int | str, path: list[Waypoint | str], quest: Quest = None):
        """根据当前目标扩展路径，生成新的子目标 , quest默认指定最新任务"""

        start = self.get_waypoint(start, quest)
        end = self.get_waypoint(end, quest)
        start.expand_between(end, path=path)

    def get_waypoint(self, ref: Waypoint | int | str, quest: Quest = None) -> Waypoint:
        """根据节点引用获取节点对象"""
        return self.quests.get_waypoint(ref, quest)
    
    def get_quest(self, quest_id: int) -> Quest:
        """根据Quest ID 查询路径数据。"""
        return self.quests.get_quest(quest_id)
    