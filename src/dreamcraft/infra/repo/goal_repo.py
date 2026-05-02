from dreamcraft.domain.goal_model import GoalMap
import pickle


class GoalRepo:
    """路径仓库，负责管理和存储所有的路径数据。

    主要职责：
    1) 提供接口创建、查询、更新路径；
    2) 维护路径数据结构（如 GoalPath）；
    3) 处理路径的持久化（如保存到文件或数据库）；
    4) 提供路径相关的工具方法（如路径验证、格式转换等）。

    说明：
    - 该类是路径管理的核心组件，其他模块通过它来访问和操作路径数据。
    - 可以根据需要扩展更多功能，如路径版本控制、路径比较等。
    """

    def __init__(self, settings):
        self.maps: list[GoalMap] = []
        self.file_path = settings.path_pkl_path
    
    def load_path(self, file_path = None):
        """从外部数据加载路径，构造 GoalPath 对象。"""
        if file_path is None:
            file_path = self.file_path
        with open(file_path, 'rb') as f:
             data = pickle.load(f)
        self.maps = data

    def save_path(self, file_path = None):
        """将当前路径数据保存到指定文件（如 JSON 格式）。"""
        if file_path is None:
            file_path = self.file_path
        with open(file_path, 'wb') as f:
            pickle.dump(self.maps, f)
    
    def add_goal(self, goal_map: GoalMap):
        """添加新的路径数据。"""
        self.maps.append(goal_map)
    
    def get_goal(self, goal_id: int) -> GoalMap:
        """根据路径 ID 查询路径数据。"""
        return self.maps[goal_id]
