import json
from typing import TYPE_CHECKING, Union
from dreamcraft.domain.snapshot import Snapshot

if TYPE_CHECKING:
    from dreamcraft.domain.quest import Quest  # 只有在静态检查时才导入
    
class Waypoint:
    def __init__(self, name, next:list['Waypoint'] = None, description = None, imaginated_snapshot: Snapshot = None, actual_snapshot: Snapshot = None):
        # 基础属性
        #   节点名称
        self.name = name
        #   节点llm描述（可选)
        self.description = description

        # 运行时赋值
        #   节点想象与实际状态
        self.imaginated_snapshot = imaginated_snapshot
        self.actual_snapshot = actual_snapshot

               
        # 内部属性
        #   拓扑结构
        self.next:set[Waypoint] = set(next) if next else set()
        for waypoint in self.next:
            waypoint.prev.add(self)
        self.prev = set()
        #   map对象相关属性
        self.ind = None
        self.quest: Quest = None
        

    def __repr__(self):
        if self.description:
            return f"Waypoint(name={self.name}, description={self.description})"
        return f"Waypoint(name={self.name})"

    def __str__(self):
        if self.description:
            return f"Waypoint(name={self.name}, description={self.description})"
        return f"Waypoint(name={self.name})"
    
    @property
    def line(self):
        string = f"{self.name}"
        if self.description:
            string += f" : {self.description}"
        return string
    
    @property
    def details(self):
        _dict = {
            "ind": self.ind,
            "name": self.name,
        }
        if self.description:
            _dict["description"] = self.description
        if self.imaginated_snapshot:
            _dict["imaginated_snapshot"] = self.imaginated_snapshot.details
        if self.actual_snapshot:
            _dict["actual_snapshot"] = self.actual_snapshot.details
        return _dict
    
    @property
    def all_successors(self):
        successors = set()
        for waypoint in self.next:
            successors.add(waypoint)
            successors.update(waypoint.all_successors)
        return successors
    
    @property
    def all_predecessors(self):
        predecessors = set()
        for waypoint in self.prev:
            predecessors.add(waypoint)
            predecessors.update(waypoint.all_predecessors)
        return predecessors


    def branch_to(self, waypoint):
        """
        在当前节点基础上添加一个新的分支节点（不替换原有子节点）。适用于路径扩展场景。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
        self.next.add(waypoint)
        waypoint.prev.add(self)

    def insert_replace_after(self, waypoint):
        """
        在当前节点后插入一个新节点，原有子节点成为新节点的子节点。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
            if self.quest.next == self:
                self.quest.next = waypoint
        waypoint.next = set(self.next)
        waypoint.prev.add(self)
        self.next = set([waypoint])

    def insert_after(self, waypoint):
        """
        在当前节点后插入一个新节点，原有子节点仍然是当前节点的子节点。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
            if self.quest.next == self:
                self.quest.next = waypoint
        waypoint.prev.add(self)
        self.next.add(waypoint)
    
    def insert_replace_before(self, waypoint):
        """
        在当前节点前插入一个新节点，原有父节点成为新节点的父节点。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
        waypoint.prev = set(self.prev)
        waypoint.next.add(self)
        self.prev = set([waypoint])

    def insert_before(self, waypoint):
        """
        在当前节点前插入一个新节点，原有父节点仍然是当前节点的父节点。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
        waypoint.next.add(self)
        self.prev.add(waypoint)
    
    def insert_between(self, target, waypoint):
        """
        在当前节点和target之间插入一个新节点，原有子节点成为新节点的子节点。
        """
        if target in self.next:
            if self.quest:
                self.quest.waypoints_append(waypoint)
            waypoint.next.add(target)
            waypoint.prev.add(self)
            self.next.discard(target)
            self.next.add(waypoint)
            target.prev.discard(self)
            target.prev.add(waypoint)
            return
        
        if target in self.prev:
            if self.quest:
                self.quest.waypoints_append(waypoint)
            waypoint.prev.add(target)
            waypoint.next.add(self)
            self.prev.discard(target)
            self.prev.add(waypoint)
            target.next.discard(self)
            target.next.add(waypoint)
            return
        
        raise ValueError(f"目标节点 {target} 既不是当前节点 {self} 的直接子节点，也不是直接父节点，无法插入")
        

    
    def remove(self):
        for prev_waypoint in self.prev:
            prev_waypoint.next.discard(self)
            prev_waypoint.next.extend(self.next)
        
        for next_waypoint in self.next:
            next_waypoint.prev.discard(self)
            next_waypoint.prev.extend(self.prev)

        if self.quest:
            self.quest.waypoints.remove(self)
            self.quest.init()  # 重新生成 waypoints 确保索引正确
    
    #剪枝
    def prune(self):
        for prev_waypoint in self.prev:
            prev_waypoint.next.discard(self)
        
        for next_waypoint in self.next:
            next_waypoint.prev.discard(self)

        self.next.clear()
        self.prev.clear()

        if self.quest:
            self.quest.waypoints.remove(self)
            self.quest.init()  # 重新生成 waypoints 确保索引正确

        
    def inject_between(self, target: 'Waypoint', path: list[Union['Waypoint', str]]):
        if target in self.next:
            is_target_next = True
        elif target in self.prev:
            is_target_next = False
        else:
            raise ValueError(f"目标节点 {target} 既不是当前节点 {self} 的直接子节点，也不是直接父节点，无法扩展路径")

        path = [Waypoint.coerce(wp) for wp in path]
        current_ptr = self
        for waypoint in path:
            # 可以在这里自动绑定 quest，保证领域对象一致性
            current_ptr.insert_between(target, waypoint)
            if is_target_next:
                current_ptr = waypoint
            else:
                target = waypoint
    
    def link_between(self, target: 'Waypoint', path: list[Union['Waypoint', str]]):
        if target in self.all_successors:
            is_target_next = True
        elif target in self.all_predecessors:
            is_target_next = False
        else:
            raise ValueError(f"目标节点 {target} 既不是当前节点 {self} 的后续节点，也不是前置节点，无法链接路径")

        path = [Waypoint.coerce(wp) for wp in path]
        self.branch_to(path[0])
        for i in range(len(path)-1):
            waypoint = path[i]
            next_waypoint = path[i+1]
            waypoint.branch_to(next_waypoint)
        path[-1].branch_to(target)
        

    #静态类方法，提供从字符串描述创建节点的便捷方式
    @staticmethod
    def coerce(ref: Union["Waypoint", str]) -> "Waypoint":
        """用于确保获得一个节点，如果是字符串则创建新节点"""
        if isinstance(ref, str):
            return Waypoint(name=ref)
        return ref
    
