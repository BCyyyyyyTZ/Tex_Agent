"""
统一条件表达式执行器。

所有条件边的计算逻辑必须且只能通过此模块执行，
禁止在其他模块散落各自实现的条件判断逻辑。

公开接口：
    ConditionExpr   - 结构化条件表达式（替代旧的裸字符串）
    evaluate_condition(state, expr) -> (bool, str)
    route_by_conditions(state, edges, fallback) -> str
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

# 所有支持的比较操作符
SUPPORTED_OPS = frozenset({
    "eq",       # ==
    "ne",       # !=
    "gt",       # >
    "gte",      # >=
    "lt",       # <
    "lte",      # <=
    "in",       # value in list
    "not_in",   # value not in list
    "contains", # str(expected) in str(actual)
    "exists",   # field path 存在（value 忽略）
    "not_exists",  # field path 不存在
})


@dataclass
class ConditionExpr:
    """
    结构化条件表达式：描述一条边的激活条件。

    取代旧的裸 Python 字符串条件，提供：
      - 明确的 field 路径引用（点路径，如 "metadata.risk.confidence"）
      - 类型安全的操作符枚举
      - 可审计的诊断信息

    Attributes:
        field: state 内的点路径，如 "metadata.risk_assessor.confidence"
        op:    比较操作符，必须在 SUPPORTED_OPS 中
        value: 参照值（exists / not_exists 时忽略，可为 None）
    """

    field: str
    op: str
    value: Any = None

    def __post_init__(self) -> None:
        op = str(self.op).strip().lower()
        if op not in SUPPORTED_OPS:
            raise ValueError(
                f"不支持的条件操作符: '{op}'，支持: {sorted(SUPPORTED_OPS)}"
            )
        self.op = op

    @classmethod
    def from_dict(cls, data: Any) -> "ConditionExpr":
        """
        从 JSON 配置字典解析 ConditionExpr。

        期望格式：
            {"field": "metadata.node_id.confidence", "op": "gte", "value": 0.7}

        Raises:
            ValueError: 字段缺失或操作符非法
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"ConditionExpr 必须是字典，得到: {type(data).__name__!r}"
            )
        field = str(data.get("field", "")).strip()
        if not field:
            raise ValueError("ConditionExpr 缺少 'field' 字段")
        op = str(data.get("op", "eq")).strip().lower()
        return cls(field=field, op=op, value=data.get("value"))

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "op": self.op, "value": self.value}


# ---------------------------------------------------------------------------
# 内部工具：从 state 读取点路径字段
# ---------------------------------------------------------------------------

def _resolve_field(state: Any, path: str) -> Tuple[bool, Any]:
    """
    按点路径从 state 中读取值。

    Returns:
        (exists: bool, value: Any)
        exists=False 表示路径不存在（中间任意一级为空/类型不符）
    """
    cur: Any = state
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict):
            if part not in cur:
                return False, None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return False, None
        else:
            return False, None
    return True, cur


# ---------------------------------------------------------------------------
# 核心执行函数
# ---------------------------------------------------------------------------

def evaluate_condition(
    state: Dict[str, Any],
    expr: ConditionExpr,
) -> Tuple[bool, str]:
    """
    执行单个条件表达式，返回结果与诊断字符串。

    Args:
        state: 当前工作流状态字典
        expr:  条件表达式

    Returns:
        (matched: bool, diagnostic: str)
        diagnostic 供日志追踪，描述匹配原因
    """
    exists, actual = _resolve_field(state, expr.field)
    op = expr.op
    expected = expr.value

    if op == "exists":
        matched = exists
        diag = f"field='{expr.field}' {'✓ exists' if matched else '✗ not found'}"
        return matched, diag

    if op == "not_exists":
        matched = not exists
        diag = f"field='{expr.field}' {'✓ not_exists' if matched else '✗ exists (should not)'}"
        return matched, diag

    if not exists:
        return False, f"field='{expr.field}' not found in state → skip"

    try:
        if op == "eq":
            matched = actual == expected
        elif op == "ne":
            matched = actual != expected
        elif op == "gt":
            matched = float(actual) > float(expected)
        elif op == "gte":
            matched = float(actual) >= float(expected)
        elif op == "lt":
            matched = float(actual) < float(expected)
        elif op == "lte":
            matched = float(actual) <= float(expected)
        elif op == "in":
            target = expected if isinstance(expected, list) else [expected]
            matched = actual in target
        elif op == "not_in":
            target = expected if isinstance(expected, list) else [expected]
            matched = actual not in target
        elif op == "contains":
            matched = str(expected) in str(actual)
        else:
            return False, f"unknown op: {op}"
    except (TypeError, ValueError) as exc:
        return False, f"comparison error ({exc}): {actual!r} {op} {expected!r}"

    diag = f"'{expr.field}' ({actual!r}) {op} {expected!r} → {matched}"
    return matched, diag


def route_by_conditions(
    state: Dict[str, Any],
    edges: List[Any],
    fallback: str,
) -> str:
    """
    根据一组条件边选择下一个节点。

    按 priority 降序遍历带条件的边，返回第一个满足条件的 to_node；
    全部不满足时返回 fallback。

    Args:
        state:    当前工作流状态
        edges:    EdgeConfig 列表（已含 condition/priority 字段）
        fallback: 无条件匹配时的默认目标节点

    Returns:
        下一个节点 ID
    """
    sorted_edges = sorted(edges, key=lambda e: getattr(e, "priority", 0), reverse=True)

    for edge in sorted_edges:
        cond = getattr(edge, "condition", None)
        if cond is None:
            continue
        matched, diag = evaluate_condition(state, cond)
        logger.debug(f"[ConditionEval] {getattr(edge, 'from_node', '?')} → {edge.to_node}: {diag}")
        if matched:
            logger.info(
                f"[ConditionEval] 条件命中: → {edge.to_node}  ({diag})"
            )
            return edge.to_node

    logger.info(f"[ConditionEval] 无条件命中，走 fallback: {fallback}")
    return fallback
