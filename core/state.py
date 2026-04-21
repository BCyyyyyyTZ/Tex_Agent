"""
全局工作流状态定义。

Breaking Change v2:
  - messages 字段使用 operator.add reducer：节点只需返回【新增消息】，
    LangGraph 自动追加到历史列表，并发安全。
  - metadata 字段使用 _merge_metadata reducer：节点只需返回【增量 dict】，
    reducer 执行深合并，保证并发节点的 metadata 键互不覆盖。
  - current_node / output / error / retrieved_context 字段均添加 reducer，
    解决并行分支同一超步多写冲突（InvalidUpdateError）。
  - 移除了旧的"节点返回完整 messages/metadata 替换语义"，由 reducer 统一接管。
"""
import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from core.message import MessageLike, NodeOutput, normalize_message_list


# ---------------------------------------------------------------------------
# State 字段 Reducer 函数
# ---------------------------------------------------------------------------

def _last_wins(a: Any, b: Any) -> Any:
    """最后写入者胜（last-write-wins）。并行分支中取最后完成的节点的值。"""
    return b


def _last_nonempty(a: Any, b: Any) -> Any:
    """最后非空者胜：b 非空则取 b，否则保留 a。适用于 output / retrieved_context。"""
    if b is None or b == "":
        return a
    return b


def _first_error(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """
    首次错误保留策略：a 已有错误则保留，否则取 b。
    保证并行分支中任一分支报错都能被捕获，且不被后续成功分支的 None 覆盖。
    """
    if a is not None:
        return a
    return b


def _merge_metadata(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    深合并 metadata 字典。

    特殊处理 "__execution_order__"：追加新节点 ID（去重保序）。
    其他 dict 类型值递归合并；其余类型直接覆盖（update 优先）。

    这是 metadata 字段的 LangGraph reducer，保证并行节点写回互不覆盖。
    """
    result: Dict[str, Any] = dict(base)
    for key, value in update.items():
        if key == "__execution_order__":
            existing: List[str] = list(result.get(key, []))
            new_items = value if isinstance(value, list) else [value]
            for item in new_items:
                if item not in existing:
                    existing.append(item)
            result[key] = existing
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_metadata(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# 状态标准化工具
# ---------------------------------------------------------------------------

def normalize_messages_for_state(messages: List[MessageLike]) -> List[Dict[str, Any]]:
    """
    将任意消息列表规范化为 state.messages 标准格式（list[dict]）。

    Breaking Change: 调用方只应传入【新增消息】，不再传入完整历史列表。
    LangGraph 的 operator.add reducer 负责追加到全量历史。
    """
    return normalize_message_list(messages)


def normalize_node_output(raw: Any) -> Dict[str, Any]:
    """将任意节点产出收敛为 NodeOutput dict（metadata[node_id] 的标准格式）。"""
    return NodeOutput.model_validate(raw).to_dict()


# ---------------------------------------------------------------------------
# 核心状态类型
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict):
    """
    LangGraph 工作流全局状态（v2 带 reducer）。

    Breaking Change v2 - Reducer 语义：
      messages:
        reducer = operator.add（列表拼接）
        节点返回 {"messages": [new_msg1, new_msg2]} 时，
        LangGraph 自动 append 到历史末尾（非替换）。
        并发安全：多个并行节点各自 append，不会互相覆盖。

      metadata:
        reducer = _merge_metadata（深合并）
        节点返回 {"metadata": {"node_id": output, "__execution_order__": [node_id]}} 时，
        LangGraph 自动深合并到现有 metadata（非替换）。
        并发安全：并行节点各自写独立键（metadata[node_id]），不冲突。

    所有字段均带 reducer，并行超步中多写安全：
      current_node  : last-write-wins（取最后完成节点）
      output        : last-nonempty-wins（非空才覆盖，避免中间节点清空最终输出）
      error         : first-error-wins（首次出错保留，成功节点的 None 不覆盖已有错误）
      retrieved_context : last-nonempty-wins
      input         : last-wins（仅在初始化时设置，实际只写一次）

    Fields:
        messages:
            工作流消息历史（统一 WorkflowMessage 协议的 dict 列表）。
            仅用于上下文构造/审计，不存结构化节点结果。
        current_node:
            当前正在执行的节点名称，由各节点自行写回（last-write-wins）。
        input:
            用户的原始输入文本，在整个工作流中保持不变。
        output:
            工作流最终输出，由末端交付节点写入（last-nonempty-wins）。
        error:
            执行过程中的错误信息，None 表示正常（first-error-wins）。
        metadata:
            结构化节点产物与运行元信息。
            约定 metadata[node_id] = NodeOutput dict。
            保留键：
              __execution_order__  : List[str]，已执行节点的有序列表
              __run_output_dir__   : str，本次运行的 trace 落盘目录
              branch               : str，当前分支名
              workflow             : str，workflow 名称
              timestamp            : str，启动时间戳
        retrieved_context:
            RAG 检索结果（由 retrieve_node 写入），未启用时为空字符串。
    """

    messages: Annotated[List[Dict[str, Any]], operator.add]
    current_node: Annotated[str, _last_wins]
    input: Annotated[str, _last_wins]
    output: Annotated[str, _last_nonempty]
    error: Annotated[Optional[str], _first_error]
    metadata: Annotated[Dict[str, Any], _merge_metadata]
    retrieved_context: Annotated[str, _last_nonempty]
