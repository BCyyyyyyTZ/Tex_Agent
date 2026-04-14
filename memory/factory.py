#memory/factory.py

from pathlib import Path
from typing import Dict, Optional

from memory.branch_memory import BranchMemory
from memory.base_memory import MemoryType
from memory.simple_memory import SimpleMemory

_DEFAULT_STORE_DIR = Path(__file__).resolve().parent.parent / "memory_store"


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
    def create_shared_memory(
        branch_enabled: bool = False,
        persist_path: Optional[str] = None,
    ) -> BranchMemory:
        """创建共享记忆；默认持久化到 memory_store/shared.jsonl。"""
        path = persist_path or str(_DEFAULT_STORE_DIR / "shared.jsonl")
        return BranchMemory(
            memory_type=MemoryType.SHARED,
            branch_enabled=branch_enabled,
            persist_path=path,
        )

    @staticmethod
    def create_private_memory(
        agent_id: str,
        branch_enabled: bool = False,
        persist_path: Optional[str] = None,
    ) -> BranchMemory:
        """创建私有记忆；默认持久化到 memory_store/private_<agent_id>.jsonl。"""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent_id) or "agent"
        path = persist_path or str(_DEFAULT_STORE_DIR / f"private_{safe}.jsonl")
        return BranchMemory(
            memory_type=MemoryType.PRIVATE,
            agent_id=agent_id,
            branch_enabled=branch_enabled,
            persist_path=path,
        )
    
    @staticmethod
    def create_hybrid_memory(branch_enabled: bool = False) -> Dict[str, BranchMemory]:
        """创建混合记忆系统（各 Agent 独立），各槽位默认独立 JSONL 文件。"""
        return {
            "design": MemoryFactory.create_private_memory(
                "design", branch_enabled=branch_enabled
            ),
            "think": MemoryFactory.create_private_memory(
                "think", branch_enabled=branch_enabled
            ),
            "execute": MemoryFactory.create_private_memory(
                "execute", branch_enabled=branch_enabled
            ),
            "shared": MemoryFactory.create_shared_memory(
                branch_enabled=branch_enabled
            ),
        }