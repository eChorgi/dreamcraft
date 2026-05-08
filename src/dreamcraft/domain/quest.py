from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Union
from dreamcraft.domain.snapshot import Snapshot
from dreamcraft.domain.waypoint import Waypoint

@dataclass
class Executable:
    waypoint: Waypoint
    reason: str = ""

@dataclass
class Edge:
    wps: set[Waypoint]
    def __hash__(self):
        return hash(frozenset(self.wps))

class Quest:
    def __init__(self, origin: Waypoint, target: Waypoint):
        self.origin = origin
        self.target = target
        self.waypoints = []

        self.next = origin
        self.current = origin
        self.snapshot = Snapshot.default()

        self.exec_path: list[Executable] = []
        self.exec_ind: int | None = None
        self.step_count = 0
        self.block_reason = dict[Edge, str]()
        self.error_history = defaultdict(list)

        self.token_usage = 0
        self.history_log = []

        self.init()
    
    @property
    def executing(self) -> Waypoint | None:
        if self.exec_ind is not None and 0 <= self.exec_ind < len(self.exec_path):
            return self.exec_path[self.exec_ind].waypoint
        return None
    
    @property
    def completed(self) -> list[Waypoint]:
        if self.exec_ind is not None and 0 <= self.exec_ind < len(self.exec_path):
            return [executable.waypoint for executable in self.exec_path[:self.exec_ind]]
        return []

    @staticmethod
    def copy(quest: 'Quest') -> 'Quest':
        mapping = {}
        
        def _copy_waypoint(waypoint: Waypoint) -> Waypoint:
            if waypoint in mapping:
                return mapping[waypoint]
            new_waypoint = Waypoint(
                name=waypoint.name,
                description=waypoint.description,
                imaginated_snapshot=waypoint.imaginated_snapshot,
                actual_snapshot=waypoint.actual_snapshot
            )
            mapping[waypoint] = new_waypoint
            for next_waypoint in waypoint.next:
                new_next_waypoint = _copy_waypoint(next_waypoint)
                new_waypoint.next.add(new_next_waypoint)
                new_next_waypoint.prev.add(new_waypoint)
            return new_waypoint
        
        new_start = _copy_waypoint(quest.origin)
        new_final = mapping[quest.next]
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
                name=waypoint.name,
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
    
    def set_edge_feasible(self, from_waypoint: Waypoint, to_waypoint: Waypoint,value: bool, reason: str = ""):
        edge = Edge(wps={from_waypoint, to_waypoint})
        if value == False and self.block_reason.get(edge, "None") != "None":
            del self.block_reason[edge]
        elif value == True:
            self.block_reason[edge] = reason

    def get_edge_feasible(self, from_waypoint: Waypoint, to_waypoint: Waypoint) -> dict:
        class FeasibilityResult:
            def __init__(self, value: bool, reason: str = ""):
                self.value = value
                self.reason = reason
        edge = Edge(wps={from_waypoint, to_waypoint})
        if self.block_reason.get(edge, "None") != "None":
            return FeasibilityResult(
                value = True,
                reason = self.block_reason[edge],
            )
        return FeasibilityResult(value = False)

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
                return self.next
            return self.waypoints[key]
        if isinstance(key, str):
            for waypoint in self.waypoints:
                if waypoint.name == key:
                    return waypoint
            raise ValueError(f"在 {self} 中未找到名称为 '{key}' 的节点")

        raise TypeError("节点引用必须是整数索引或字符串名称")
    
    def waypoints_append(self, waypoint: Waypoint):
        if waypoint in self.waypoints:
            return
        if not self.waypoints or self.waypoints[0] != self.origin:
            self.waypoints.insert(0,self.origin)
            self.origin.ind = 0
            self.origin.quest = self

        if not self.waypoints or self.waypoints[-1] != self.next:
            self.waypoints.append(self.next)
            self.next.ind = len(self.waypoints) - 1
            self.next.quest = self
            
        if waypoint == self.next:
            return
        
        if waypoint == self.origin:
            return
        

        waypoint.ind = len(self.waypoints) - 1
        waypoint.quest = self

        self.waypoints.insert(-1,waypoint)
        self.next.ind = len(self.waypoints) - 1
        
    
    def all_paths(self, origin = None, target = None, return_ind = False , is_ind_from_zero = True):
        if not origin:
            origin = self.origin
        if not target:
            target = self.next
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
                if self.next != waypoint:
                    raise ValueError("存在多个叶子节点")

                continue
            self.waypoints_append(waypoint)
            for _waypoint in waypoint.next:
                queue.append(_waypoint)
        self.waypoints_append(self.next)
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
                flag = (waypoint == self.next) or flag
            is_valid[waypoint] = flag
            if not flag:
                waypoint.prune()  # 如果这个节点不可达终点，则从图中移除
            return flag
        
        _validate(self.origin)
        
        self.index_waypoints()

    def get_waypoint(self, ref: Waypoint | int | str) -> Waypoint|None:
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
                return None
            if ref == -1:
                return self.next
            return self.waypoints[ref]
        
        if isinstance(ref, str):
            for waypoint in self.waypoints:
                if waypoint.name == ref:
                    return waypoint
            return None
        
        raise TypeError("ref 必须是 Waypoint 对象、整数索引或字符串名称")
    
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
            "waypoints": [waypoint.line for waypoint in self.waypoints],
            "adjacency_list": self.adjancency_list,
        }
    
    def slice(self, origin: Waypoint | int | str, target: Waypoint | int | str = None) -> 'Quest':
        origin = self.get_waypoint(origin)
        if target is None:
            target = self.next
        else:
            target = self.get_waypoint(target)
        
        return Quest.clip(origin, target)
    
    
    