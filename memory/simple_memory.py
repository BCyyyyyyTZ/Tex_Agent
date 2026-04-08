#memory/simple_memory.py

from typing import List,Any, Dict
from memory.base_memory import BaseMemory,MemoryType
from datetime import datetime  # 正确

class SimpleMemory(BaseMemory):
    """
    基础记忆实现
    - 支持共享模式：所有 Agent 访问同一份数据
    - 支持单独模式：每个 Agent 独立数据
    """
    
    def __init__(self, memory_type: MemoryType = MemoryType.SHARED, 
                 agent_id: str = None, max_size: int = 1000):
        """
        Args:
            memory_type: SHARED（共享）或 PRIVATE（单独）
            agent_id: 当 memory_type=PRIVATE 时，用于区分不同 Agent
            max_size: 最大存储条数
        """
        self.memory_type = memory_type
        self.agent_id = agent_id
        self.max_size = max_size
        self._storage = []  # 简单列表存储
        self._index = {}    # 索引
        
    def save(self, key: str, value: Any, metadata: Dict = None) -> None:
        """保存记忆"""
        memory_item = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.now(),
            "agent": self.agent_id
        }
        
        self._storage.append(memory_item)
        
        # 保持大小限制
        if len(self._storage) > self.max_size:
            self._storage.pop(0)
        
        # 更新索引
        self._index[key] = memory_item

    
    def load(self, key: str = None, limit: int = None) -> List[Any]:
        """加载记忆"""
        if key:
            # 加载特定 key
            return [self._index[key]["value"]] if key in self._index else []
        
        # 加载所有
        items = self._storage
        if limit:
            items = items[-limit:]
        return [item["value"] for item in items]
    
    def search(self, query: str, limit: int = 10) -> List[Any]:
        """简单搜索（子串匹配）"""
        results = []
        for item in reversed(self._storage):  # 最新的优先
            if query.lower() in str(item["value"]).lower():
                results.append(item["value"])
                if len(results) >= limit:
                    break
        return results
    
    def clear(self) -> None:
        """清空记忆"""
        self._storage.clear()
        self._index.clear()
    
    def get_size(self) -> int:
        return len(self._storage)
