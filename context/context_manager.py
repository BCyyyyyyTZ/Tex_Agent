# context/context_manager.py
from collections import deque
from typing import List, Optional, Dict, Any, Union
from context.base import BaseContext
from core.message import AgentMessage
from utils.logger import get_logger
from config.planner_config import METADATA_CHAIN_RESULT_MAX_CHARS

logger = get_logger(__name__)
MsgType = Union[Dict[str, Any], AgentMessage, str]

# metadata 中保留的系统键，不参与「节点产出」合成
_METADATA_RESERVED_KEYS = frozenset({
    "__execution_order__",
    "__run_output_dir__",
    "branch",
    "workflow",
    "timestamp",
})


def _is_structured_node_output(value: Any) -> bool:
    return isinstance(value, dict) and ("result" in value or "summary" in value)


def _is_tool_node_output(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    meta = value.get("metadata", {})
    return isinstance(meta, dict) and meta.get("node_type") == "tool"


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...（已截断，共{len(text)}字符）"


def format_metadata_chain_for_prompt(state: Dict[str, Any]) -> str:
    """
    当 state.messages 不累积中间对话时，用已执行节点的结构化 metadata 拼出可读上下文链。
    顺序优先使用 metadata['__execution_order__']，否则按节点 id 排序以保证稳定。
    """
    meta = state.get("metadata") or {}
    order = meta.get("__execution_order__")
    if isinstance(order, list) and order:
        node_ids = [str(x) for x in order if str(x) not in _METADATA_RESERVED_KEYS]
    else:
        node_ids = sorted(
            k for k in meta
            if k not in _METADATA_RESERVED_KEYS and _is_structured_node_output(meta.get(k))
        )
    blocks: List[str] = []
    for nid in node_ids:
        blob = meta.get(nid)
        if not _is_structured_node_output(blob):
            continue
        summary = str(blob.get("summary", "")).strip()
        result = str(blob.get("result", "")).strip()
        parts = [f"### [{nid}]"]
        if summary:
            parts.append(f"摘要: {summary}")
        if result:
            if _is_tool_node_output(blob):
                # 工具输出保留全量，确保后续节点拿到完整检索结果
                if result != summary:
                    parts.append(f"补充产出(完整):\n{result}")
            else:
                # metadata_chain 优先给摘要，普通节点 result 使用截断版降低噪声
                compact_result = _truncate_text(result, METADATA_CHAIN_RESULT_MAX_CHARS)
                if compact_result and compact_result != summary:
                    parts.append(f"补充产出(截断):\n{compact_result}")
        if len(parts) > 1:
            blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def _safe_get(msg: Any, key: str, default: str = "") -> str:
    """兼容 dict / AgentMessage / str 的安全取值"""
    if isinstance(msg, dict): return str(msg.get(key, default))
    if isinstance(msg, str): return default  # 纯字符串无属性，跳过
    return str(getattr(msg, key, default))


class ContextManager(BaseContext):
    def __init__(self, max_messages: Optional[int] = None, default_limit: Optional[int] = None):
        """
        Args:
            max_messages: 内存队列硬性上限（FIFO 淘汰阈值），None 表示不限制
            default_limit: GSSC 流水线默认上下文窗口大小，None 时回退到 max_messages
        """
        # 兼容旧代码传参
        self.max_messages = max_messages
        self.default_limit = default_limit if default_limit is not None else max_messages
        
        # deque 的 maxlen 仅由 max_messages 控制
        self._messages: deque = deque(maxlen=max_messages)

    def save(self, message: AgentMessage) -> None:
        if not isinstance(message, AgentMessage):
            raise TypeError(f"save() 仅接受 AgentMessage，收到 {type(message).__name__}")
        if self.max_messages == 0: return
        self._messages.append(message)

    def load(self, limit: Optional[int] = None) -> List[AgentMessage]:
        if limit is None: return list(self._messages)
        return list(self._messages)[-limit:]

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def structure(self, messages: List[MsgType], format_type: str = "plain") -> str:
        if not messages: return ""
        lines = []
        for m in messages:
            if isinstance(m, str):
                lines.append(f"[SYSTEM] {m}")
                continue
            role = _safe_get(m, "role", "unknown").upper()
            agent = _safe_get(m, "agent_name", "sys")
            content = _safe_get(m, "content", "")
            lines.append(f"[{role} | {agent}] {content}")
        return "\n".join(lines)

    def compress(self, text: str, max_tokens: Optional[int] = None) -> str:
        if max_tokens and len(text) > max_tokens:
            return text[-max_tokens:]
        return text

    def build(self, state: Dict[str, Any], memory: Any = None, config: Optional[Dict[str, Any]] = None) -> str:
        """GSSC 主入口：Gather → Select → Structure → Compress"""
        cfg = config or {}
        parts = []
        msgs = state.get("messages", [])
        retrieved = state.get("retrieved_context", "")
        
        # Query 提取
        query = state.get("input", "")
        if not query and msgs:
            last = msgs[-1]
            query = _safe_get(last, "content", "")
            
        # Memory 检索
        mem_items = []
        if memory and query:
            mem_items = memory.search(query=query, limit=cfg.get("mem_limit", 3))
            
        # Window 筛选
        limit = cfg.get("conv_limit", self.max_messages or 20)
        window = msgs[-limit:] if limit else msgs
        
        # 组装
        if retrieved and retrieved.strip():
            parts.append(f"<context type='retrieved'>\n{retrieved}\n</context>")
        if mem_items:
            mem_str = "\n".join(f"- {str(it)}" for it in mem_items)
            parts.append(f"<context type='memory'>\n{mem_str}\n</context>")
        if window:
            parts.append(f"<context type='history'>\n{self.structure(window, cfg.get('format', 'plain'))}\n</context>")
        elif cfg.get("synthetic_metadata_history"):
            chain = format_metadata_chain_for_prompt(state)
            if chain.strip():
                parts.append(f"<context type='metadata_chain'>\n{chain}\n</context>")

        structured = "\n\n".join(parts)
        return self.compress(structured, cfg.get("max_tokens"))