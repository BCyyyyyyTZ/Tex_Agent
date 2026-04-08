#memory/factory.py

from memory.branch_memory import BranchMemory
from memory.base_memory import MemoryType
from typing import Dict
from memory.simple_memory import SimpleMemory


class MemoryFactory:
    """记忆工厂：简化创建"""
    @staticmethod
    def create_memory(mode: str = "shared", agent_id: str = None) -> SimpleMemory:
        """
        创建记忆实例
        
        Args:
            mode: "shared" - 全局共享， "private" - Agent 单独
            agent_id: 当 mode="private" 时必填
        """
        if mode == "shared":
            return SimpleMemory(MemoryType.SHARED)
        elif mode == "private":
            if not agent_id:
                raise ValueError("agent_id required for private memory")
            return SimpleMemory(MemoryType.PRIVATE, agent_id=agent_id)
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    @staticmethod
    def create_shared_memory(branch_enabled: bool = False) -> BranchMemory:
        """创建共享记忆"""
        return BranchMemory(
            memory_type=MemoryType.SHARED,
            branch_enabled=branch_enabled
        )
    
    @staticmethod
    def create_private_memory(agent_id: str, branch_enabled: bool = False) -> BranchMemory:
        """创建私有记忆"""
        return BranchMemory(
            memory_type=MemoryType.PRIVATE,
            agent_id=agent_id,
            branch_enabled=branch_enabled
        )
    
    @staticmethod
    def create_hybrid_memory(branch_enabled: bool = False) -> Dict[str, BranchMemory]:
        """创建混合记忆系统（各 Agent 独立）"""
        return {
            "design": BranchMemory(
                memory_type=MemoryType.PRIVATE,
                agent_id="design",
                branch_enabled=branch_enabled
            ),
            "think": BranchMemory(
                memory_type=MemoryType.PRIVATE,
                agent_id="think",
                branch_enabled=branch_enabled
            ),
            "execute": BranchMemory(
                memory_type=MemoryType.PRIVATE,
                agent_id="execute",
                branch_enabled=branch_enabled
            ),
            "shared": BranchMemory(
                memory_type=MemoryType.SHARED,
                branch_enabled=branch_enabled
            )
        }