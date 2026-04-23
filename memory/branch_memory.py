# memory/branch_memory.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from copy import deepcopy
from memory.simple_memory import SimpleMemory
from utils.logger import get_logger

logger = get_logger(__name__)


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
        
        out = {
            "success": True,
            "merged_count": merged_count,
            "branch": source_branch
        }
        self._rewrite_persist_from_memory()
        return out
    
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
        self._rewrite_persist_from_memory()
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

        evicted = False
        # 保持大小限制
        if hasattr(self, "max_size") and len(self._storage) > self.max_size:
            self._storage.pop(0)
            evicted = True

        # 更新索引
        self._index[key] = memory_item

        br_name = (
            self.current_branch
            if self.branch_enabled and self.current_branch
            else "main"
        )
        self._persist_append(str(br_name), memory_item)
        if evicted and getattr(self, "persist_path", None):
            self._rewrite_persist_from_memory()

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
        """搜索记忆（支持分支）：复用 SimpleMemory 的混合检索算法。"""
        return super().search(query, limit)
    
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
        self._rewrite_persist_from_memory()
    
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


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()


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
    
    def __init__(
        self,
        *args,
        branch_enabled: bool = False,
        persist_path: Optional[Union[str, Path]] = None,
        **kwargs,
    ):
        self.persist_path = Path(persist_path) if persist_path else None
        # 与历史行为一致：不在此把 branch_enabled 传给 BranchMixin，避免 SimpleMemory
        # 初始化覆盖分支 storage；由本类在 super() 之后打开分支并初始化。
        super().__init__(*args, **kwargs)
        self.branch_enabled = branch_enabled
        self.branches = {}
        self.current_branch = None
        self.branch_history = {}
        if self.branch_enabled:
            self._init_branch_system()
        if self.persist_path:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_persisted()

    def _persist_append(self, branch_name: str, memory_item: Dict[str, Any]) -> None:
        if not self.persist_path:
            return
        ts = memory_item.get("timestamp")
        if isinstance(ts, datetime):
            ts_s = ts.isoformat()
        else:
            ts_s = str(ts)
        rec = {
            "branch": branch_name,
            "key": memory_item.get("key"),
            "value": memory_item.get("value"),
            "metadata": memory_item.get("metadata") or {},
            "timestamp": ts_s,
            "agent": memory_item.get("agent"),
        }
        try:
            with self.persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.warning(f"记忆追加落盘失败 {self.persist_path}: {e}")

    def _rewrite_persist_from_memory(self) -> None:
        if not self.persist_path:
            return
        lines: List[str] = []
        try:
            if self.branch_enabled and self.branches:
                for br_name, data in self.branches.items():
                    for it in data.get("storage", []):
                        ts = it.get("timestamp")
                        ts_s = ts.isoformat() if isinstance(ts, datetime) else str(ts)
                        rec = {
                            "branch": br_name,
                            "key": it.get("key"),
                            "value": it.get("value"),
                            "metadata": it.get("metadata") or {},
                            "timestamp": ts_s,
                            "agent": it.get("agent"),
                        }
                        lines.append(json.dumps(rec, ensure_ascii=False, default=str))
            else:
                for it in self._storage:
                    ts = it.get("timestamp")
                    ts_s = ts.isoformat() if isinstance(ts, datetime) else str(ts)
                    rec = {
                        "branch": "main",
                        "key": it.get("key"),
                        "value": it.get("value"),
                        "metadata": it.get("metadata") or {},
                        "timestamp": ts_s,
                        "agent": it.get("agent"),
                    }
                    lines.append(json.dumps(rec, ensure_ascii=False, default=str))
            self.persist_path.write_text(
                ("\n".join(lines) + "\n") if lines else "",
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"记忆重写落盘失败 {self.persist_path}: {e}")

    def _load_persisted(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        try:
            raw = self.persist_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"记忆加载失败 {self.persist_path}: {e}")
            return
        max_sz = getattr(self, "max_size", 1000) or 1000
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = {
                "key": rec.get("key"),
                "value": rec.get("value"),
                "metadata": rec.get("metadata") or {},
                "timestamp": _parse_ts(rec.get("timestamp")),
                "agent": rec.get("agent"),
            }
            if item["key"] is None:
                continue
            br_name = str(rec.get("branch") or "main")
            if self.branch_enabled:
                if br_name not in self.branches:
                    self.branches[br_name] = {
                        "storage": [],
                        "index": {},
                        "created_at": datetime.now(),
                        "parent": "main",
                    }
                st = self.branches[br_name]["storage"]
                ix = self.branches[br_name]["index"]
                st.append(item)
                ix[item["key"]] = item
                while len(st) > max_sz:
                    old = st.pop(0)
                    ix.pop(old.get("key"), None)
            else:
                self._storage.append(item)
                self._index[item["key"]] = item
                while len(self._storage) > max_sz:
                    old = self._storage.pop(0)
                    self._index.pop(old.get("key"), None)
        if self.branch_enabled and "main" in self.branches:
            self.current_branch = "main"
            self._storage = self.branches["main"]["storage"]
            self._index = self.branches["main"]["index"]

