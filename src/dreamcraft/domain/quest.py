from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Union
from dreamcraft.domain.snapshot import Snapshot

class Waypoint:
    def __init__(self, description = None, next = None, imaginated_snapshot: Snapshot = None, actual_snapshot: Snapshot = None):
        # 创建时定义
        #   节点llm描述
        self.description = description

        # 运行时赋值
        #   节点想象与实际状态
        self.imaginated_snapshot = imaginated_snapshot
        self.actual_snapshot = actual_snapshot
        #   节点可行性
        self.is_feasible: bool = None
        self.dead_ends: dict[Waypoint, str] = {} # 记录不可行的子节点以及对应的失败原因

               
        # 内部属性
        #   拓扑结构
        self.next = set(next) if next else set()
        for waypoint in self.next:
            waypoint.prev.add(self)
        self.prev = set()
        #   map对象相关属性
        self.ind = None
        self.quest: Quest = None
        


    def __repr__(self):
        return f"Waypoint(description={self.description})"
    
    def __str__(self):
        return f"Waypoint(description={self.description})"

    
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
            if self.quest.target == self:
                self.quest.target = waypoint
        waypoint.next = set(self.next)
        waypoint.prev.add(self)
        self.next = set([waypoint])

    def insert_after(self, waypoint):
        """
        在当前节点后插入一个新节点，原有子节点仍然是当前节点的子节点。
        """
        if self.quest:
            self.quest.waypoints_append(waypoint)
            if self.quest.target == self:
                self.quest.target = waypoint
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

        
    def expand_between(self, target: 'Waypoint', path: list[Union['Waypoint', str]]):
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
            waypoint.quest = self.quest 
            current_ptr.insert_between(target, waypoint)
            if is_target_next:
                current_ptr = waypoint
            else:
                target = waypoint

    #静态类方法，提供从字符串描述创建节点的便捷方式
    @staticmethod
    def coerce(ref: Union["Waypoint", str]) -> "Waypoint":
        """用于确保获得一个节点，如果是字符串则创建新节点"""
        if isinstance(ref, str):
            return Waypoint(description=ref)
        return ref
    

class Quest:
    def __init__(self, origin: Waypoint, target: Waypoint):
        self.origin = origin
        self.target = target
        self.waypoints = []
        self.init()

    @staticmethod
    def copy(quest: 'Quest') -> 'Quest':
        mapping = {}
        
        def _copy_waypoint(waypoint: Waypoint) -> Waypoint:
            if waypoint in mapping:
                return mapping[waypoint]
            new_waypoint = Waypoint(
                description=waypoint.description,
                imaginated_snapshot=waypoint.imaginated_snapshot,
                actual_snapshot=waypoint.actual_snapshot,
                feasibility=waypoint.is_feasible
            )
            mapping[waypoint] = new_waypoint
            for next_waypoint in waypoint.next:
                new_next_waypoint = _copy_waypoint(next_waypoint)
                new_waypoint.next.add(new_next_waypoint)
                new_next_waypoint.prev.add(new_waypoint)
            return new_waypoint
        
        new_start = _copy_waypoint(quest.origin)
        new_final = mapping[quest.target]
        return Quest(new_start, new_final)
    
    @staticmethod
    def clip(origin: Waypoint, target: Waypoint) -> 'Quest':
        mapping = {}
        if not origin.quest or not target.quest or origin.quest != target.quest:
            raise ValueError("origin 和 target 必须属于同一个 Quest")
        
        def _copy_waypoint(waypoint: Waypoint) -> Waypoint:
            if waypoint in mapping:
                return mapping[waypoint]
            new_waypoint = Waypoint(
                description=waypoint.description,
                imaginated_snapshot=waypoint.imaginated_snapshot,
                actual_snapshot=waypoint.actual_snapshot,
            )
            mapping[waypoint] = new_waypoint
            for next_waypoint in waypoint.next:
                new_next_waypoint = _copy_waypoint(next_waypoint)
                new_waypoint.next.add(new_next_waypoint)
                new_next_waypoint.prev.add(new_waypoint)
            return new_waypoint
        
            
        
        new_start = _copy_waypoint(origin)
        if target not in mapping:
            raise ValueError("target 不在 origin 的子树中，无法剪裁")
        new_final = mapping[target]
        return Quest(new_start, new_final) # final之后节点的裁剪操作在构造函数的init()方法中完成

    def __repr__(self):
        ret = "Quest(waypoints=["
        for ind, waypoint in enumerate(self.waypoints):
            ret += f"\n{ind}:  {waypoint}"
        ret += "\n])"
        return ret
    
    def __str__(self):
        ret = "Quest(waypoints=["
        for ind, waypoint in enumerate(self.waypoints):
            ret += f"\n{ind}:  {waypoint}"
        ret += "\n])"
        return ret
    
    def __getitem__(self, key: int | str) -> Waypoint:
        if isinstance(key, int):
            if key >= len(self.waypoints) or key < -1:
                raise ValueError(f"节点索引 {key} 超出{self}的范围 [0, {len(self.waypoints) - 1}]")
            if key == -1:
                return self.target
            return self.waypoints[key]
        if isinstance(key, str):
            for waypoint in self.waypoints:
                if waypoint.description == key:
                    return waypoint
            raise ValueError(f"在 {self} 中未找到描述为 '{key}' 的节点")

        raise TypeError("节点引用必须是整数索引或字符串描述")
    
    def waypoints_append(self, waypoint: Waypoint):
        if not self.waypoints or self.waypoints[0] != self.origin:
            self.waypoints.insert(0,self.origin)
            self.origin.ind = 0
            self.origin.quest = self

        if not self.waypoints or self.waypoints[-1] != self.target:
            self.waypoints.append(self.target)
            self.target.ind = len(self.waypoints) - 1
            self.target.quest = self
            
        if waypoint == self.target:
            return
        
        if waypoint == self.origin:
            return
        

        waypoint.ind = len(self.waypoints) - 1
        waypoint.quest = self

        self.waypoints.insert(-1,waypoint)
        self.target.ind = len(self.waypoints) - 1
        
    
    def all_paths(self, origin = None, target = None, return_ind = False , is_ind_from_zero = True):
        if not origin:
            origin = self.origin
        if not target:
            target = self.target
        if origin == target:
            return [[origin]]
        paths = []
        for next_waypoint in origin.next:
            _paths = self.all_paths(next_waypoint, target)
            for _path in _paths:
                paths.append([origin] + _path)
        if return_ind:
            if is_ind_from_zero:
                return [[self.waypoints.index(y) for y in x] for x in paths]
            return [[self.waypoints.index(y)+1 for y in x] for x in paths]
        return paths
    
    def index_waypoints(self):
        """
        根据当前的 origin 和 target(可选) 以及它们之间的连接关系，生成 waypoints 和每个节点的 ind 属性。
        """
        if not self.origin:
            raise ValueError("为了建立索引 origin 是必须的")
        self.waypoints = []
        queue = deque([self.origin])
        visited = set()
        while (len(queue) > 0):
            waypoint = queue.popleft()
            if waypoint in visited:
                continue
            visited.add(waypoint)
            if not waypoint.next:
                if self.target != waypoint:
                    raise ValueError("存在多个叶子节点")

                continue
            self.waypoints_append(waypoint)
            for _waypoint in waypoint.next:
                queue.append(_waypoint)
        self.waypoints_append(self.target)
        return self.waypoints
        
    def init(self):
        is_valid = {}
        def _validate(waypoint: Waypoint) -> bool:
            flag = False
            for next_waypoint in set(waypoint.next):
                if next_waypoint in is_valid:
                    flag = is_valid[next_waypoint] or flag
                else:
                    flag = _validate(next_waypoint) or flag
            if not waypoint.next:
                flag = (waypoint == self.target) or flag
            is_valid[waypoint] = flag
            if not flag:
                waypoint.prune()  # 如果这个节点不可达终点，则从图中移除
            return flag
        
        _validate(self.origin)
        
        self.index_waypoints()

    def get_waypoint(self, ref: Waypoint | int | str) -> Waypoint:
        """
        辅助函数：根据引用解析出 Waypoint 对象
        解析规则：
            - 如果 ref 是 Waypoint 对象，直接返回。
            - 如果 ref 是整数索引，则在 quest 的 waypoints 中查找对应的节点（-1 代表 target）。
            - 如果 ref 是字符串，则在 quest 的 waypoints 中查找描述匹配的节点。
        """
        if isinstance(ref, Waypoint):
            return ref
        
        if isinstance(ref, int):
            if ref >= len(self.waypoints) or ref < -1:
                raise ValueError(f"节点索引 {ref} 超出{self}的范围 [0, {len(self.waypoints) - 1}]")
            if ref == -1:
                return self.target
            return self.waypoints[ref]
        
        if isinstance(ref, str):
            for waypoint in self.waypoints:
                if waypoint.description == ref:
                    return waypoint
            raise ValueError(f"在 {self} 中未找到描述为 '{ref}' 的节点")
        
        raise TypeError("ref 必须是 Waypoint 对象、整数索引或字符串描述")
    
    @property
    def adjancency_list(self, return_ind = False, is_ind_from_zero = True):
        adj_list = []
        for waypoint in self.waypoints:
            adj_list.append([wp.ind for wp in waypoint.next])
        return adj_list
    
    @property
    def json(self):
        return {
            "waypoint_num": len(self.waypoints),
            "descriptions": [waypoint.description for waypoint in self.waypoints],
            "adjacency_list": self.adjancency_list,
        }
    
    def slice(self, origin: Waypoint | int | str, target: Waypoint | int | str = None) -> 'Quest':
        origin = self.get_waypoint(origin)
        if target is None:
            target = self.target
        else:
            target = self.get_waypoint(target)
        
        return Quest.clip(origin, target)
    
    
    