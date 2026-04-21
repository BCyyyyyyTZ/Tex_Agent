"""
统一并发结果汇聚器。

所有并行分支的结果合并逻辑必须且只能通过此模块执行，
禁止各 join 节点各自实现独立的合并策略。

公开接口：
    JoinPolicy          - 汇聚策略枚举
    BranchResult        - 单分支结果
    MergedResult        - 汇聚后综合结果
    merge_parallel_results(state, source_branches, policy) -> MergedResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class JoinPolicy(str, Enum):
    """
    并行汇聚策略。

    ALL_SUCCESS   : 所有分支必须成功，否则整体失败（默认，最严格）
    PARTIAL       : 至少一个分支成功即可继续（容错模式）
    FIRST_SUCCESS : 使用第一个成功分支的结果（竞速模式）
    """

    ALL_SUCCESS = "all_success"
    PARTIAL = "partial"
    FIRST_SUCCESS = "first_success"


@dataclass
class BranchResult:
    """单个并行分支的执行结果摘要。"""

    branch_id: str
    success: bool
    result: str = ""
    summary: str = ""
    confidence: float = 0.0
    error: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MergedResult:
    """
    并行分支汇聚结果。

    Attributes:
        success:           整体是否成功（由 JoinPolicy 决定）
        total_branches:    参与汇聚的分支总数
        succeeded_branches:成功分支数
        failed_branch_ids: 失败分支 ID 列表
        combined_result:   合并后的主体内容（可供 join agent 使用）
        error_summary:     失败摘要（成功时为空字符串）
        branch_outputs:    各分支原始 metadata dict（node_id → NodeOutput dict）
    """

    success: bool
    total_branches: int
    succeeded_branches: int
    failed_branch_ids: List[str]
    combined_result: str
    error_summary: str
    branch_outputs: Dict[str, Any]


def merge_parallel_results(
    state: Dict[str, Any],
    source_branches: List[str],
    policy: JoinPolicy = JoinPolicy.ALL_SUCCESS,
) -> MergedResult:
    """
    从 state.metadata 读取各并行分支输出，按策略汇聚。

    各分支在执行后已将结果写入 state["metadata"][branch_id]（NodeOutput dict）。
    本函数读取这些结果并按 policy 决定整体成功/失败，同时构造合并文本供
    join agent 作为上下文。

    Args:
        state:           当前完整工作流状态
        source_branches: 并行分支节点 ID 列表
        policy:          汇聚策略

    Returns:
        MergedResult（含 combined_result 可直接注入 join agent prompt）
    """
    metadata: Dict[str, Any] = state.get("metadata", {}) or {}

    results: List[BranchResult] = []
    for branch_id in source_branches:
        branch_meta: Any = metadata.get(branch_id, {})
        if not isinstance(branch_meta, dict):
            branch_meta = {}

        status = str(branch_meta.get("status", "pass")).strip().lower()
        is_success = status not in ("fail",)

        inner_meta = branch_meta.get("metadata", {})
        error: Optional[str] = None
        if isinstance(inner_meta, dict):
            error = inner_meta.get("error") or None

        results.append(
            BranchResult(
                branch_id=branch_id,
                success=is_success,
                result=str(branch_meta.get("result", "")),
                summary=str(branch_meta.get("summary", "")),
                confidence=float(branch_meta.get("confidence", 0.0)),
                error=error,
                raw_metadata=branch_meta,
            )
        )

    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if policy == JoinPolicy.ALL_SUCCESS:
        overall_success = len(failed) == 0
    elif policy == JoinPolicy.PARTIAL:
        overall_success = len(succeeded) > 0
    elif policy == JoinPolicy.FIRST_SUCCESS:
        overall_success = len(succeeded) > 0
    else:
        overall_success = len(failed) == 0

    # 构造合并内容文本
    if policy == JoinPolicy.FIRST_SUCCESS and succeeded:
        combined = succeeded[0].result
    else:
        parts: List[str] = []
        for r in results:
            status_label = "[OK]" if r.success else "[FAIL]"
            block = f"[{status_label} {r.branch_id}]"
            if r.summary:
                block += f"\n摘要: {r.summary}"
            if r.result:
                block += f"\n输出:\n{r.result}"
            if r.error:
                block += f"\n错误: {r.error}"
            parts.append(block)
        combined = "\n\n".join(parts)

    error_parts: List[str] = []
    for r in failed:
        err_msg = r.error or f"{r.branch_id} 返回 status=fail"
        error_parts.append(f"  - {r.branch_id}: {err_msg}")
    error_summary = "\n".join(error_parts)

    branch_outputs = {r.branch_id: r.raw_metadata for r in results}

    logger.info(
        f"[ParallelMerger] 汇聚 {len(results)} 个分支: "
        f"{len(succeeded)} 成功 / {len(failed)} 失败  "
        f"policy={policy.value}  overall={'OK' if overall_success else 'FAIL'}"
    )
    if failed:
        logger.warning(f"[ParallelMerger] 失败分支: {[r.branch_id for r in failed]}")

    return MergedResult(
        success=overall_success,
        total_branches=len(results),
        succeeded_branches=len(succeeded),
        failed_branch_ids=[r.branch_id for r in failed],
        combined_result=combined,
        error_summary=error_summary,
        branch_outputs=branch_outputs,
    )
