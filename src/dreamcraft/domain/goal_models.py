from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Union
from dreamcraft.domain.snapshot_models import Snapshot

class GoalNode:
    def __init__(self, description = None, next_nodes = None, predicted_snapshot: Snapshot = None, actual_snapshot: Snapshot = None):
        # 拓扑结构
        self.next_nodes = set(next_nodes) if next_nodes else set()
        for node in self.next_nodes:
            node.previous_nodes.add(self)
        self.previous_nodes = set()
        
        # 节点llm描述
        self.description = description

        # 节点想象与实际状态
        self.predicted_snapshot = predicted_snapshot
        self.actual_snapshot = actual_snapshot
        self.feasibility: bool = None

        self.ind = None
        self.parent_map: GoalMap = None


    def __repr__(self):
        return f"GoalNode(description={self.description})"
    
    def __str__(self):
        return f"GoalNode(description={self.description})"

    
    def add_new_branch_node(self, node):
        """
        在当前节点基础上添加一个新的分支节点（不替换原有子节点）。适用于路径扩展场景。
        """
        if self.parent_map:
            self.parent_map.node_list_append(node)
        self.next_nodes.add(node)
        node.previous_nodes.add(self)

    def insert_replace_after(self, node):
        """
        在当前节点后插入一个新节点，原有子节点成为新节点的子节点。
        """
        if self.parent_map:
            self.parent_map.node_list_append(node)
            if self.parent_map.final_node == self:
                self.parent_map.final_node = node
        node.next_nodes = set(self.next_nodes)
        node.previous_nodes.add(self)
        self.next_nodes = set([node])

    def insert_after(self, node):
        """
        在当前节点后插入一个新节点，原有子节点仍然是当前节点的子节点。
        """
        if self.parent_map:
            self.parent_map.node_list_append(node)
            if self.parent_map.final_node == self:
                self.parent_map.final_node = node
        node.previous_nodes.add(self)
        self.next_nodes.add(node)
    
    def insert_replace_before(self, node):
        """
        在当前节点前插入一个新节点，原有父节点成为新节点的父节点。
        """
        if self.parent_map:
            self.parent_map.node_list_append(node)
        node.previous_nodes = set(self.previous_nodes)
        node.next_nodes.add(self)
        self.previous_nodes = set([node])

    def insert_before(self, node):
        """
        在当前节点前插入一个新节点，原有父节点仍然是当前节点的父节点。
        """
        if self.parent_map:
            self.parent_map.node_list_append(node)
        node.next_nodes.add(self)
        self.previous_nodes.add(node)
    
    def insert_between(self, target, node):
        """
        在当前节点和target之间插入一个新节点，原有子节点成为新节点的子节点。
        """
        if target in self.next_nodes:
            if self.parent_map:
                self.parent_map.node_list_append(node)
            node.next_nodes.add(target)
            node.previous_nodes.add(self)
            self.next_nodes.discard(target)
            self.next_nodes.add(node)
            target.previous_nodes.discard(self)
            target.previous_nodes.add(node)
            return
        
        if target in self.previous_nodes:
            if self.parent_map:
                self.parent_map.node_list_append(node)
            node.previous_nodes.add(target)
            node.next_nodes.add(self)
            self.previous_nodes.discard(target)
            self.previous_nodes.add(node)
            target.next_nodes.discard(self)
            target.next_nodes.add(node)
            return
        
        raise ValueError(f"目标节点 {target} 既不是当前节点 {self} 的直接子节点，也不是直接父节点，无法插入")
        

    
    def remove(self):
        for prev_node in self.previous_nodes:
            prev_node.next_nodes.discard(self)
            prev_node.next_nodes.extend(self.next_nodes)
        
        for next_node in self.next_nodes:
            next_node.previous_nodes.discard(self)
            next_node.previous_nodes.extend(self.previous_nodes)

        if self.parent_map:
            self.parent_map.node_list.remove(self)
            self.parent_map.init()  # 重新生成 node_list 确保索引正确
    
    #剪枝
    def prune(self):
        for prev_node in self.previous_nodes:
            prev_node.next_nodes.discard(self)
        
        for next_node in self.next_nodes:
            next_node.previous_nodes.discard(self)

        self.next_nodes.clear()
        self.previous_nodes.clear()

        if self.parent_map:
            self.parent_map.node_list.remove(self)
            self.parent_map.init()  # 重新生成 node_list 确保索引正确

        
    def expand_path_between(self, target_node:'GoalNode', new_nodes: list[Union['GoalNode', str]]):
        if target_node in self.next_nodes:
            is_target_next = True
        elif target_node in self.previous_nodes:
            is_target_next = False
        else:
            raise ValueError(f"目标节点 {target_node} 既不是当前节点 {self} 的直接子节点，也不是直接父节点，无法扩展路径")

        new_nodes = [GoalNode.coerce(n) for n in new_nodes]
        current_ptr = self
        for node in new_nodes:
            # 可以在这里自动绑定 parent_map，保证领域对象一致性
            node.parent_map = self.parent_map 
            current_ptr.insert_between(target_node, node)
            if is_target_next:
                current_ptr = node
            else:
                target_node = node

    #静态类方法，提供从字符串描述创建节点的便捷方式
    @staticmethod
    def coerce(node_ref: Union["GoalNode", str]) -> "GoalNode":
        """用于确保获得一个节点，如果是字符串则创建新节点"""
        if isinstance(node_ref, str):
            return GoalNode(description=node_ref)
        return node_ref
    

class GoalMap:
    def __init__(self, start_node: GoalNode, final_node: GoalNode):
        self.start_node = start_node
        self.final_node = final_node
        self.node_list = []
        self.init()

    @staticmethod
    def copy(goal_map: 'GoalMap') -> 'GoalMap':
        node_mapping = {}
        
        def _copy_node(node: GoalNode) -> GoalNode:
            if node in node_mapping:
                return node_mapping[node]
            new_node = GoalNode(
                description=node.description,
                predicted_snapshot=node.predicted_snapshot,
                actual_snapshot=node.actual_snapshot,
                feasibility=node.feasibility
            )
            node_mapping[node] = new_node
            for next_node in node.next_nodes:
                new_next_node = _copy_node(next_node)
                new_node.next_nodes.add(new_next_node)
                new_next_node.previous_nodes.add(new_node)
            return new_node
        
        new_start = _copy_node(goal_map.start_node)
        new_final = node_mapping[goal_map.final_node]
        return GoalMap(new_start, new_final)
    
    @staticmethod
    def clip(start_node: GoalNode, end_node: GoalNode) -> 'GoalMap':
        node_mapping = {}
        if not start_node.parent_map or not end_node.parent_map or start_node.parent_map != end_node.parent_map:
            raise ValueError("start_node 和 end_node 必须属于同一个 GoalMap")
        
        def _copy_node(node: GoalNode) -> GoalNode:
            if node in node_mapping:
                return node_mapping[node]
            new_node = GoalNode(
                description=node.description,
                predicted_snapshot=node.predicted_snapshot,
                actual_snapshot=node.actual_snapshot,
            )
            node_mapping[node] = new_node
            for next_node in node.next_nodes:
                new_next_node = _copy_node(next_node)
                new_node.next_nodes.add(new_next_node)
                new_next_node.previous_nodes.add(new_node)
            return new_node
        
            
        
        new_start = _copy_node(start_node)
        if end_node not in node_mapping:
            raise ValueError("end_node 不在 start_node 的子树中，无法剪裁")
        new_final = node_mapping[end_node]
        return GoalMap(new_start, new_final) # final之后节点的裁剪操作在构造函数的init()方法中完成

    def __repr__(self):
        ret = "GoalMap(node_list=["
        for ind, node in enumerate(self.node_list):
            ret += f"\n{ind}:  {node}"
        ret += "\n])"
        return ret
    
    def __str__(self):
        ret = "GoalMap(node_list=["
        for ind, node in enumerate(self.node_list):
            ret += f"\n{ind}:  {node}"
        ret += "\n])"
        return ret
    
    def __getitem__(self, key: int | str) -> GoalNode:
        if isinstance(key, int):
            if key >= len(self.node_list) or key < -1:
                raise ValueError(f"节点索引 {key} 超出{self}的范围 [0, {len(self.node_list) - 1}]")
            if key == -1:
                return self.final_node
            return self.node_list[key]
        if isinstance(key, str):
            for node in self.node_list:
                if node.description == key:
                    return node
            raise ValueError(f"在 {self} 中未找到描述为 '{key}' 的节点")

        raise TypeError("节点引用必须是整数索引或字符串描述")
    
    def node_list_append(self, node: GoalNode):
        if not self.node_list or self.node_list[0] != self.start_node:
            self.node_list.insert(0,self.start_node)
            self.start_node.ind = 0
            self.start_node.parent_map = self

        if not self.node_list or self.node_list[-1] != self.final_node:
            self.node_list.append(self.final_node)
            self.final_node.ind = len(self.node_list) - 1
            self.final_node.parent_map = self
            
        if node == self.final_node:
            return
        
        if node == self.start_node:
            return
        

        node.ind = len(self.node_list) - 1
        node.parent_map = self

        self.node_list.insert(-1,node)
        self.final_node.ind = len(self.node_list) - 1
        
    
    def all_paths(self, start_node = None, end_node = None, return_ind = False , is_ind_from_zero = True):
        if not start_node:
            start_node = self.start_node
        if not end_node:
            end_node = self.final_node
        if start_node == end_node:
            return [[start_node]]
        paths = []
        for next_node in start_node.next_nodes:
            _paths = self.all_paths(next_node, end_node)
            for _path in _paths:
                paths.append([start_node] + _path)
        if return_ind:
            if is_ind_from_zero:
                return [[self.node_list.index(y) for y in x] for x in paths]
            return [[self.node_list.index(y)+1 for y in x] for x in paths]
        return paths
    
    def index_nodes(self):
        """
        根据当前的 start_node 和 final_node(可选) 以及它们之间的连接关系，生成 node_list 和每个节点的 ind 属性。
        """
        if not self.start_node:
            raise ValueError("为了建立索引 start_node 是必须的")
        self.node_list = []
        queue = deque([self.start_node])
        visited = set()
        while (len(queue) > 0):
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if not node.next_nodes:
                if self.final_node != node:
                    raise ValueError("存在多个叶子节点")

                continue
            self.node_list_append(node)
            for _node in node.next_nodes:
                queue.append(_node)
        self.node_list_append(self.final_node)
        return self.node_list
        
    def init(self):
        is_valid = {}
        def _validate(node: GoalNode) -> bool:
            flag = False
            for next_node in set(node.next_nodes):
                if next_node in is_valid:
                    flag = is_valid[next_node] or flag
                else:
                    flag = _validate(next_node) or flag
            if not node.next_nodes:
                flag = (node == self.final_node) or flag
            is_valid[node] = flag
            if not flag:
                node.prune()  # 如果这个节点不可达终点，则从图中移除
            return flag
        
        _validate(self.start_node)
        
        self.index_nodes()

    def get_node(self, node_ref: GoalNode | int | str) -> GoalNode:
        """
        辅助函数：根据引用解析出 GoalNode 对象
        解析规则：
            - 如果 node_ref 是 GoalNode 对象，直接返回。
            - 如果 node_ref 是整数索引，则在 parent_map 的 node_list 中查找对应的节点（-1 代表 final_node）。
            - 如果 node_ref 是字符串，则在 parent_map 的 node_list 中查找描述匹配的节点。
        """
        if isinstance(node_ref, GoalNode):
            return node_ref
        
        if isinstance(node_ref, int):
            if node_ref >= len(self.node_list) or node_ref < -1:
                raise ValueError(f"节点索引 {node_ref} 超出{self}的范围 [0, {len(self.node_list) - 1}]")
            if node_ref == -1:
                return self.final_node
            return self.node_list[node_ref]
        
        if isinstance(node_ref, str):
            for node in self.node_list:
                if node.description == node_ref:
                    return node
            raise ValueError(f"在 {self} 中未找到描述为 '{node_ref}' 的节点")
        
        raise TypeError("node_ref 必须是 GoalNode 对象、整数索引或字符串描述")
    
    @property
    def adjancency_list(self, return_ind = False, is_ind_from_zero = True):
        adj_list = []
        for node in self.node_list:
            adj_list.append([n.ind for n in node.next_nodes])
        return adj_list
    
    @property
    def json(self):
        return {
            "node_num": len(self.node_list),
            "descriptions": [node.description for node in self.node_list],
            "adjacency_list": self.adjancency_list,
        }
    
    def sub_map(self, start_node: GoalNode | int | str, end_node: GoalNode | int | str = None) -> 'GoalMap':
        start_node = self.get_node(start_node)
        if end_node is None:
            end_node = self.final_node
        else:
            end_node = self.get_node(end_node)
        
        return GoalMap.clip(start_node, end_node)
    
    
    