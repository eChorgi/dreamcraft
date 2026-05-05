from dreamcraft.domain.quest import Quest
from dreamcraft.domain.waypoint import Waypoint
import pickle


class QuestRepo:
    """路径仓库，负责管理和存储所有的路径数据。

    主要职责：
    1) 提供接口创建、查询、更新路径；
    2) 维护路径数据结构（如 Quest）；
    3) 处理路径的持久化（如保存到文件或数据库）；
    4) 提供路径相关的工具方法（如路径验证、格式转换等）。

    说明：
    - 该类是路径管理的核心组件，其他模块通过它来访问和操作路径数据。
    - 可以根据需要扩展更多功能，如路径版本控制、路径比较等。
    """

    def __init__(self, settings):
        self.quests: list[Quest] = []
        self.file_path = settings.path_pkl_path
    
    def load_path(self, file_path = None):
        """从外部数据加载路径，构造 Quest 对象。"""
        if file_path is None:
            file_path = self.file_path
        with open(file_path, 'rb') as f:
             data = pickle.load(f)
        self.quests = data

    def save_path(self, file_path = None):
        """将当前路径数据保存到指定文件（如 JSON 格式）。"""
        if file_path is None:
            file_path = self.file_path
        with open(file_path, 'wb') as f:
            pickle.dump(self.quests, f)
    
    def add(self, quest: Quest):
        """添加新的路径数据。"""
        self.quests.append(quest)
    
    def get_quest(self, quest_id: int) -> Quest:
        """根据Quest ID 查询路径数据。"""
        return self.quests[quest_id]

    def get_waypoint(self, ref: Waypoint | int | str, quest: Quest = None) -> Waypoint:
        if quest is None:
            quest = self.get_quest(-1)  # 默认使用最后一个目标地图
        return quest.get_waypoint(ref)
