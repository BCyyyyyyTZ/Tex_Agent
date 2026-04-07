"""
[扩展] 多分支上下文机制接口定义。
设计类似 Git Branch 的状态管理数据结构，支持上下文无缝迁移与回退。
这是 TeX_Agent 未来的核心功能之一！

TODO: 开发者 D 负责设计并实现此类（第二阶段核心任务）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class BranchNode:
    """
    上下文分支节点数据结构（类比 Git Commit）。

    每个 BranchNode 代表一个独立的上下文状态快照，
    允许用户在不同的思路分支之间自由切换和回退。

    Attributes:
        branch_id: 分支唯一标识符（UUID 或自定义字符串）。
        parent_id: 父分支 ID（None 表示根节点/主分支）。
        name: 分支可读名称（如 "main", "try-structure-v2"）。
        messages: 该分支独有的消息列表（序列化为 dict，不与父分支共享）。
        created_at: 分支创建的 UTC 时间戳。
        metadata: 扩展元数据（分支描述、创建原因、标签等）。

    Design Notes:
        - 分支间共享的消息通过 parent_id 链形成隐式继承
        - 具体的继承与隔离策略由 ContextTree 实现决定
        - 类比 Git：branch_id ≈ commit hash，parent_id ≈ parent commit
    """

    branch_id: str
    parent_id: Optional[str] = None
    name: str = "main"
    messages: List[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


class ContextTree(ABC):
    """
    [扩展] 多分支上下文树管理器抽象基类。

    功能规划（类比 Git 操作）：
        1. create_branch()  ≈ git branch / git checkout -b
        2. switch_branch()  ≈ git checkout
        3. merge_branch()   ≈ git merge
        4. rollback()       ≈ git reset
        5. list_branches()  ≈ git branch -a

    设计目标：
        解决用户在论文写作时频繁更改思路、需要"可撤销的尝试"的场景。
        例如：
        - 尝试论文结构方案 A（创建分支），不满意时回退到主分支
        - 并行探索两种 Related Work 写法，最终选择最佳方案合并

    TODO: 开发者 D 实现建议：
          - 使用嵌套字典 {branch_id: BranchNode} 存储所有分支
          - merge 策略可参考 Git 的 fast-forward 和 3-way merge
          - 考虑持久化到本地 JSON 文件，支持跨会话恢复
    """

    @abstractmethod
    def create_branch(
        self, name: str, parent_id: Optional[str] = None
    ) -> BranchNode:
        """
        创建新分支（类比 git checkout -b）。

        Args:
            name: 分支名称（用户可读，如 "structure-v2"）。
            parent_id: 父分支 ID（None 则从当前活跃分支派生）。

        Returns:
            新创建的 BranchNode 对象。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def switch_branch(self, branch_id: str) -> BranchNode:
        """
        切换到指定分支（类比 git checkout）。

        Args:
            branch_id: 目标分支的唯一 ID。

        Returns:
            切换后的活跃 BranchNode。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def get_current_branch(self) -> BranchNode:
        """
        获取当前活跃分支。

        Returns:
            当前活跃的 BranchNode。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def merge_branch(self, source_id: str, target_id: str) -> BranchNode:
        """
        合并两个分支（类比 git merge）。

        Args:
            source_id: 源分支 ID（被合并的分支）。
            target_id: 目标分支 ID（合并到的分支）。

        Returns:
            合并后的 BranchNode（通常为更新后的 target 分支）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def rollback(self, branch_id: str, steps: int = 1) -> BranchNode:
        """
        回退分支状态指定步数（类比 git reset --soft HEAD~N）。

        Args:
            branch_id: 需要回退的分支 ID。
            steps: 回退的消息条数（从分支末尾移除）。

        Returns:
            回退后的 BranchNode。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def list_branches(self) -> List[BranchNode]:
        """
        列出所有分支信息。

        Returns:
            所有 BranchNode 列表（按创建时间正序）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    # TODO: 未来增加 migrate_memory(agent, from_branch_id, to_branch_id) 接口，
    #       支持 Agent 对话历史在分支间迁移
    # TODO: 未来增加 get_branch_diff(branch_id_a, branch_id_b) 接口，
    #       显示两个分支之间的上下文差异
