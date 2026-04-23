# context/context_manager.py
from collections import deque
from typing import List, Optional, Dict, Any, Union
from context.base import BaseContext
from core.message import WorkflowMessage, ensure_message
from memory.simple_memory import SimpleMemory
from memory.base_memory import MemoryType
from utils.logger import get_logger
from config.planner_config import METADATA_CHAIN_RESULT_MAX_CHARS

logger = get_logger(__name__)
MsgType = Union[Dict[str, Any], WorkflowMessage]

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
            compact_result = _truncate_text(result, METADATA_CHAIN_RESULT_MAX_CHARS)
            if compact_result and compact_result != summary:
                parts.append(f"补充产出:\n{compact_result}")
        if len(parts) > 1:
            blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


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

    def save(self, message: WorkflowMessage) -> None:
        if not isinstance(message, WorkflowMessage):
            raise TypeError(f"save() 仅接受 WorkflowMessage，收到 {type(message).__name__}")
        if self.max_messages == 0: return
        self._messages.append(message)

    def load(self, limit: Optional[int] = None) -> List[WorkflowMessage]:
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
            msg = ensure_message(m, default_role="assistant", default_source_type="system", default_source_id="history")
            role = str(msg.role).upper()
            source = f"{msg.source_type}:{msg.source_id}"
            content = str(msg.content)
            lines.append(f"[{role} | {source}] {content}")
        return "\n".join(lines)

    def compress(self, text: str, max_tokens: Optional[int] = None) -> str:
        if max_tokens and len(text) > max_tokens:
            return text[-max_tokens:]
        return text

    def search(self, query: str, limit: int = 10, state: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        在「会话消息」中检索，不读写图内 metadata。

        优先使用本轮 LangGraph state.messages（已包含 invoke 前从本 Context 注入的历史）；
        若未提供 state 或 messages 为空，则回退到当前 Context 队列。
        """
        lim = max(1, int(limit or 10))
        q = (query or "").strip()
        if not q:
            return []

        msgs_raw: List[Any]
        if state is not None:
            msgs_raw = state.get("messages", []) or []
        else:
            msgs_raw = list(self._messages)

        if not msgs_raw:
            return []

        mem = SimpleMemory(MemoryType.SHARED, max_size=max(len(msgs_raw), 16))
        for i, raw in enumerate(msgs_raw):
            msg = ensure_message(
                raw,
                default_role="assistant",
                default_source_type="system",
                default_source_id="session",
            )
            meta = dict(msg.metadata or {})
            meta.setdefault("role", msg.role)
            meta.setdefault("source_type", msg.source_type)
            meta.setdefault("source_id", msg.source_id)
            mem.save(f"session:{i}", str(msg.content or ""), metadata=meta)

        return mem.search(q, lim)

    def build(self, state: Dict[str, Any], memory: Any = None, config: Optional[Dict[str, Any]] = None) -> str:
        """GSSC 主入口：Gather → Select → Structure → Compress"""
        cfg = config or {}
        parts = []
        msgs_raw = state.get("messages", []) or []
        msgs = [
            ensure_message(m, default_role="assistant", default_source_type="system", default_source_id="state")
            for m in msgs_raw
        ]
        retrieved = state.get("retrieved_context", "")
        history_mode = str(cfg.get("history_mode") or "").strip().lower()
        if history_mode not in ("full", "minimal"):
            # 兼容旧参数：synthetic_metadata_history=True 等价于 minimal
            history_mode = "minimal" if cfg.get("synthetic_metadata_history") else "full"
        
        # Query 提取
        query = state.get("input", "")
        if not query and msgs:
            query = str(msgs[-1].content)
            
        # Memory 检索
        mem_items: List[Any] = []
        if memory and query:
            mem_limit = int(cfg.get("mem_limit", 3) or 3)
            try:
                mem_items = memory.search(query=query, limit=mem_limit, state=state)
            except TypeError:
                mem_items = memory.search(query=query, limit=mem_limit)
            
        # 组装
        if retrieved and retrieved.strip():
            parts.append(f"<context type='retrieved'>\n{retrieved}\n</context>")
        if mem_items:
            mem_str = "\n".join(f"- {str(it)}" for it in mem_items)
            parts.append(f"<context type='memory'>\n{mem_str}\n</context>")
        if history_mode == "minimal":
            chain = format_metadata_chain_for_prompt(state)
            if chain.strip():
                parts.append(f"<context type='metadata_chain'>\n{chain}\n</context>")
        else:
            limit = cfg.get("conv_limit", self.max_messages or 20)
            window = msgs[-limit:] if limit else msgs
            if window:
                parts.append(f"<context type='history'>\n{self.structure(window, cfg.get('format', 'plain'))}\n</context>")

        structured = "\n\n".join(parts)
        return self.compress(structured, cfg.get("max_tokens"))