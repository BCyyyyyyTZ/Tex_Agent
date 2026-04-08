# memory/branch_memory.py
from typing import Dict, List, Optional, Any
from datetime import datetime
from copy import deepcopy
from memory.simple_memory import SimpleMemory


class BranchMixin:
    """
    分支功能混入类（Mixin）
    为 SimpleMemory 添加分支能力，可以按需启用
    """
    
    def __init__(self, *args, **kwargs):
        # 分支功能默认关闭
        self.branch_enabled = kwargs.get('branch_enabled', False)
        
        if self.branch_enabled:
            self._init_branch_system()
        
        super().__init__(*args, **kwargs)
    
    def _init_branch_system(self):
        """初始化分支系统"""
        self.branches: Dict[str, Dict] = {
            "main": {  # 主分支
                "storage": [],
                "index": {},
                "created_at": datetime.now()
            }
        }
        self.current_branch = "main"
        self.branch_history: Dict[str, List[Dict]] = {}  # 分支历史
    
    def enable_branch(self):
        """启用分支功能（如果还没启用）"""
        if not self.branch_enabled:
            self.branch_enabled = True
            self._init_branch_system()
    
    def disable_branch(self):
        """禁用分支功能（合并回主分支）"""
        if self.branch_enabled:
            # 可选：自动合并当前分支到主分支
            self.merge_to_main()
            self.branch_enabled = False
            self.branches = None
            self.current_branch = None
    
    # ========== 分支操作 ==========
    
    def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """创建新分支"""
        if not self.branch_enabled:
            return False
        
        if branch_name in self.branches:
            return False
        
        # 复制源分支数据
        source = self.branches[from_branch]
        self.branches[branch_name] = {
            "storage": deepcopy(source["storage"]),
            "index": deepcopy(source["index"]),
            "created_at": datetime.now(),
            "parent": from_branch
        }
        
        return True
    
    def switch_branch(self, branch_name: str) -> bool:
        """切换分支"""
        if not self.branch_enabled:
            return False
        
        if branch_name not in self.branches:
            return False
        
        # 保存当前分支状态
        if self.current_branch:
            self.branches[self.current_branch]["storage"] = deepcopy(self._storage)
            self.branches[self.current_branch]["index"] = deepcopy(self._index)
        
        # 切换到新分支
        self.current_branch = branch_name
        self._storage = deepcopy(self.branches[branch_name]["storage"])
        self._index = deepcopy(self.branches[branch_name]["index"])
        
        return True
    
    def list_branches(self) -> List[str]:
        """列出所有分支"""
        if not self.branch_enabled:
            return ["main"]  # 只有主分支
        
        return list(self.branches.keys())
    
    def merge_to_main(self, branch_name: str = None) -> Dict[str, Any]:
        """将分支合并到主分支"""
        if not self.branch_enabled:
            return {"success": False, "reason": "branch not enabled"}
        
        source_branch = branch_name or self.current_branch
        if source_branch == "main":
            return {"success": False, "reason": "cannot merge main to main"}
        
        if source_branch not in self.branches:
            return {"success": False, "reason": "branch not found"}
        
        # 获取分支数据
        branch_data = self.branches[source_branch]
        
        # 合并：将分支的新记忆添加到主分支
        main_storage = self.branches["main"]["storage"]
        original_size = len(main_storage)
        
        # 找出分支独有的记忆（简化实现：直接合并所有）
        for item in branch_data["storage"]:
            # 检查是否已存在（基于 key）
            if not any(existing["key"] == item["key"] for existing in main_storage):
                main_storage.append(item)
        
        # 更新索引
        self.branches["main"]["index"] = {}
        for item in main_storage:
            self.branches["main"]["index"][item["key"]] = item
        
        # 如果当前在这个分支，切换到主分支
        if self.current_branch == source_branch:
            self.switch_branch("main")
        
        return {
            "success": True,
            "merged_count": len(main_storage) - original_size,
            "branch": source_branch
        }
    
    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """删除分支"""
        if not self.branch_enabled:
            return False
        
        if branch_name == "main":
            return False
        
        if branch_name not in self.branches:
            return False
        
        if self.current_branch == branch_name and not force:
            return False
        
        del self.branches[branch_name]
        return True
    
    # ========== 覆盖父类方法以支持分支 ==========
    
    def save(self, key: str, value: Any, metadata: Dict = None) -> None:
        """保存记忆（支持分支）"""
        if self.branch_enabled:
            # 保存前记录到历史
            if self.current_branch not in self.branch_history:
                self.branch_history[self.current_branch] = []
            
            self.branch_history[self.current_branch].append({
                "key": key,
                "value": value,
                "action": "save",
                "timestamp": datetime.now()
            })
        
        # 调用父类方法
        super().save(key, value, metadata)
    
    def get_branch_info(self) -> Dict[str, Any]:
        """获取分支信息"""
        if not self.branch_enabled:
            return {"enabled": False, "current": "main"}
        
        return {
            "enabled": True,
            "current": self.current_branch,
            "branches": list(self.branches.keys()),
            "branch_details": {
                name: {
                    "size": len(data["storage"]),
                    "created": data["created_at"],
                    "parent": data.get("parent")
                }
                for name, data in self.branches.items()
            }
        }

class BranchMemory(BranchMixin, SimpleMemory):
    """
    高级记忆：基础记忆 + 可选分支功能
    
    使用方式：
        # 1. 无分支模式（默认）
        memory = BranchMemory(memory_type=MemoryType.SHARED)
        
        # 2. 启用分支
        memory = BranchMemory(memory_type=MemoryType.PRIVATE, 
                                agent_id="design",
                                branch_enabled=True)
        
        # 3. 运行时启用分支
        memory = BranchMemory()
        memory.enable_branch()
        memory.create_branch("experiment")
    """
    
    def __init__(self, *args, branch_enabled: bool = False, **kwargs):
        # 初始化分支系统（如果需要）
        self.branch_enabled = branch_enabled
        
        # 调用父类初始化
        super().__init__(*args, **kwargs)

