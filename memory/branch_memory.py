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
        
        # 初始化分支相关属性（避免属性不存在错误）
        self.branches: Dict[str, Dict] = {}
        self.current_branch: Optional[str] = None
        self.branch_history: Dict[str, List[Dict]] = {}
        
        if self.branch_enabled:
            self._init_branch_system()
        
        super().__init__(*args, **kwargs)
    
    def _init_branch_system(self):
        """初始化分支系统"""
        self.branches = {
            "main": {  # 主分支
                "storage": [],
                "index": {},
                "created_at": datetime.now()
            }
        }
        self.current_branch = "main"
        self.branch_history = {}
        
        # 同步到 SimpleMemory 的 _storage 和 _index
        self._storage = self.branches["main"]["storage"]
        self._index = self.branches["main"]["index"]
    
    def enable_branch(self):
        """启用分支功能（如果还没启用）"""
        if not self.branch_enabled:
            self.branch_enabled = True
            self._init_branch_system()
    
    def disable_branch(self):
        """禁用分支功能（合并回主分支）"""
        if self.branch_enabled:
            # 可选：自动合并当前分支到主分支
            if self.current_branch and self.current_branch != "main":
                self.merge_to_main()
            self.branch_enabled = False
            # 清空分支数据但保留属性
            self.branches.clear()
            self.current_branch = None
    
    # ========== 分支操作 ==========
    
    def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """创建新分支"""
        if not self.branch_enabled:
            return False
        
        if branch_name in self.branches:
            return False
        
        if from_branch not in self.branches:
            return False
        
        # 保存当前分支状态
        if self.current_branch:
            self._save_current_branch_state()
        
        # 复制源分支数据
        source = self.branches[from_branch]
        self.branches[branch_name] = {
            "storage": deepcopy(source["storage"]),
            "index": deepcopy(source["index"]),
            "created_at": datetime.now(),
            "parent": from_branch
        }
        
        return True
    
    def _save_current_branch_state(self):
        """保存当前分支的状态"""
        if (self.current_branch and self.current_branch in self.branches):
            self.branches[self.current_branch]["storage"] = deepcopy(self._storage)
            self.branches[self.current_branch]["index"] = deepcopy(self._index)
    
    def switch_branch(self, branch_name: str) -> bool:
        """切换分支"""
        if not self.branch_enabled:
            return False
        
        if branch_name not in self.branches:
            return False
        
        # 保存当前分支状态
        if self.current_branch:
            self._save_current_branch_state()
        
        # 切换到新分支
        self.current_branch = branch_name
        # 直接引用分支数据，而不是深拷贝（提高性能并保持引用）
        self._storage = self.branches[branch_name]["storage"]
        self._index = self.branches[branch_name]["index"]
        
        return True
    
    def list_branches(self) -> List[str]:
        """列出所有分支"""
        if not self.branch_enabled or not self.branches:
            return ["main"]
        
        return list(self.branches.keys())
    
    def merge_to_main(self, branch_name: str = None) -> Dict[str, Any]:
        """将分支合并到主分支"""
        if not self.branch_enabled:
            return {"success": False, "reason": "branch not enabled"}
        
        if not self.branches:
            return {"success": False, "reason": "branches not initialized"}
        
        source_branch = branch_name or self.current_branch
        if not source_branch or source_branch == "main":
            return {"success": False, "reason": "cannot merge main to main"}
        
        if source_branch not in self.branches:
            return {"success": False, "reason": f"branch '{source_branch}' not found"}
        
        # 保存当前状态
        if self.current_branch == source_branch:
            self._save_current_branch_state()
        
        # 获取分支数据
        branch_data = self.branches[source_branch]
        main_branch = self.branches["main"]
        
        # 合并：将分支的新记忆添加到主分支
        original_size = len(main_branch["storage"])
        merged_count = 0
        
        # 找出分支独有的记忆（基于 key）
        for item in branch_data["storage"]:
            # 检查是否已存在（基于 key）
            existing_keys = [existing.get("key") for existing in main_branch["storage"]]
            if item["key"] not in existing_keys:
                main_branch["storage"].append(deepcopy(item))
                main_branch["index"][item["key"]] = main_branch["storage"][-1]
                merged_count += 1
        
        # 如果当前在这个分支，切换到主分支
        if self.current_branch == source_branch:
            self.switch_branch("main")
        
        return {
            "success": True,
            "merged_count": merged_count,
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
        if self.branch_enabled and self.current_branch:
            # 保存前记录到历史
            if self.current_branch not in self.branch_history:
                self.branch_history[self.current_branch] = []
            
            self.branch_history[self.current_branch].append({
                "key": key,
                "value": value,
                "action": "save",
                "timestamp": datetime.now()
            })
        
        # 创建记忆项
        memory_item = {
            "key": key,
            "value": value,
            "metadata": metadata or {},
            "timestamp": datetime.now(),
            "agent": getattr(self, 'agent_id', None)
        }
        
        # 直接添加到当前存储
        self._storage.append(memory_item)
        
        # 保持大小限制
        if hasattr(self, 'max_size') and len(self._storage) > self.max_size:
            self._storage.pop(0)
        
        # 更新索引
        self._index[key] = memory_item
    
    def load(self, key: str = None, limit: int = None) -> List[Any]:
        """加载记忆（支持分支）"""
        if not self.branch_enabled:
            return super().load(key, limit)
        
        if key:
            # 加载特定 key
            return [self._index[key]["value"]] if key in self._index else []
        
        # 加载所有
        items = self._storage
        if limit:
            items = items[-limit:]
        return [item["value"] for item in items]
    
    def search(self, query: str, limit: int = 10) -> List[Any]:
        """搜索记忆（支持分支）"""
        if not self.branch_enabled:
            return super().search(query, limit)
        
        results = []
        for item in reversed(self._storage):  # 最新的优先
            if query.lower() in str(item["value"]).lower():
                results.append(item["value"])
                if len(results) >= limit:
                    break
        return results
    
    def clear(self) -> None:
        """清空记忆（支持分支）"""
        if not self.branch_enabled:
            super().clear()
        else:
            self._storage.clear()
            self._index.clear()
            # 同时清空分支存储中的引用
            if self.current_branch and self.current_branch in self.branches:
                self.branches[self.current_branch]["storage"] = self._storage
                self.branches[self.current_branch]["index"] = self._index
    
    def get_size(self) -> int:
        """获取记忆数量（支持分支）"""
        if not self.branch_enabled:
            return super().get_size()
        return len(self._storage)
    
    def get_branch_info(self) -> Dict[str, Any]:
        """获取分支信息"""
        if not self.branch_enabled or not self.branches:
            return {"enabled": False, "current": "main", "branches": ["main"]}
        
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
        # 先初始化 SimpleMemory
        super().__init__(*args, **kwargs)
        
        # 设置分支相关属性
        self.branch_enabled = branch_enabled
        self.branches: Dict[str, Dict] = {}
        self.current_branch: Optional[str] = None
        self.branch_history: Dict[str, List[Dict]] = {}
        
        # 如果启用分支，初始化分支系统
        if self.branch_enabled:
            self._init_branch_system()

