# memory/base_memory.py
from abc import ABC, abstractmethod
from typing import List,Any, Dict
from enum import Enum

class MemoryType(Enum):
    """记忆类型"""
    SHARED = "shared"      # 全局共享
    PRIVATE = "private"    # 单独使用

class BaseMemory(ABC):
    """记忆基类 - 最基础的功能"""
    
    @abstractmethod
    def save(self, key: str, value: Any, metadata: Dict = None) -> None:
        """保存记忆"""
        pass
    
    @abstractmethod
    def load(self, key: str = None, limit: int = None) -> List[Any]:
        """加载记忆"""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Any]:
        """搜索记忆"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空记忆"""
        pass
    
    @abstractmethod
    def get_size(self) -> int:
        """获取记忆数量"""
        pass
