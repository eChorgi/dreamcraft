
from dreamcraft.domain.goal_model import GoalMap, GoalNode
from dreamcraft.app.protocols import IGoalRepo

class GoalService:
    def __init__(self, goals : IGoalRepo = None):
        self.goals = goals
    

    def new_goal(self, goal: str):
        """根据新的目标初始化路径"""
        start_node = GoalNode(description = "开始")
        final_node = GoalNode(description = goal)
        start_node.insert_after(final_node)
        m = GoalMap(start_node = start_node, final_node = final_node)
        self.goals.add_goal(m)
        print(f"新建目标地图: {m}")
        return m
    
    def expand_to_path(self, node: GoalNode | int | str, new_nodes: list[GoalNode | str], parent_goal: GoalMap = None):
        """根据当前目标扩展路径，生成新的子目标"""

        current = self._get_node(node, parent_goal)
        current.expand_to_path(new_nodes)
    
    def _get_node(self, node_ref: GoalNode | int | str, parent_goal: GoalMap = None) -> GoalNode:
        if parent_goal is None:
            parent_goal = self.goals.get_goal(-1)  # 默认使用最后一个目标地图
        return parent_goal.get_node(node_ref)