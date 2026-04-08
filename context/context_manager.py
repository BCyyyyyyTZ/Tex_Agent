# context/context_manager.py
"""
ContextManager / ContextBuilder
遵循 GSSC (Gather-Select-Structure-Compress) 上下文工程流水线。
无内部状态，所有操作基于传入的 messages 列表，完美适配 LangGraph state["messages"]。
"""
from typing import List, Optional, Dict, Any, Callable
from core.message import AgentMessage
from utils.logger import get_logger
from memory.simple_memory import SimpleMemory

logger = get_logger(__name__)


class ContextManager:
    """
    纯函数式上下文构建器。
    设计原则：零状态、显式流水线、阶段可替换。
    """
    def __init__(self, default_limit: int = 20):
        self.default_limit = default_limit

    # ================= G: Gather（汇聚） =================
    def gather(
        self,
        state_messages: List[AgentMessage],
        external_sources: Optional[List[Any]] = None
    ) -> List[AgentMessage]:
        """
        汇聚原始上下文数据源。
        MVP：仅使用 state["messages"]，预留 external_sources 接口（如 RAG 片段、系统提示、配置文件）。
        """
        gathered = list(state_messages)
        if external_sources:
            # TODO: 后续可在此处将外部源转为 AgentMessage 并注入时间戳/来源标记
            logger.debug(f"Gather: 接入了 {len(external_sources)} 个外部上下文源")
        return gathered

    # ================= S: Select（筛选） =================
    def select(
        self,
        messages: List[AgentMessage],
        agent_name: Optional[str] = None,
        roles: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[AgentMessage]:
        """
        按规则过滤/排序消息。
        """
        filtered = messages

        if agent_name:
            filtered = [m for m in filtered if getattr(m, "agent_name", None) == agent_name]
        if roles:
            filtered = [m for m in filtered if m.role in roles]
            
        # 默认取最新 N 条（时间正序保留）
        lim = limit or self.default_limit
        if lim and lim > 0:
            filtered = filtered[-lim:]
            
        return filtered

    # ================= S: Structure（结构化） =================
    def structure(
        self,
        messages: List[AgentMessage],
        format_type: str = "plain",
        template: Optional[str] = None
    ) -> str:
        """
        将消息列表格式化为 LLM 可读的字符串。
        """
        if format_type == "plain":
            return "\n".join(
                f"[{m.role.upper()} | {getattr(m, 'agent_name', 'sys')}] {m.content}"
                for m in messages
            )
        if format_type == "xml":
            return "\n".join(
                f"<message role='{m.role}' agent='{getattr(m, 'agent_name', '')}'>{m.content}</message>"
                for m in messages
            )
        if template:
            # 预留 Jinja2 / f-string 模板渲染能力
            return template.format(messages=messages)
        return self.structure(messages, "plain")

    # ================= C: Compress（压缩） =================
    def compress(
        self,
        context_str: str,
        max_tokens: Optional[int] = None,
        compression_mode: str = "truncate"  # truncate | summary | semantic
    ) -> str:
        """
        上下文压缩策略。
        MVP: 基于字符串长度/消息数量的简单截断。
        后续可无缝替换为 tiktoken 计数 或 LLM 摘要模型。
        """
        if compression_mode == "truncate":
            # 当前按字符/消息数硬截断（实际生产建议按 token）
            return context_str[-max_tokens:] if max_tokens else context_str
            
        # TODO: 接入 tiktoken 精确计数
        # TODO: 接入 LLM 摘要: compress_mode="summary" -> self.llm.summarize(context_str)
        return context_str

    # ================= 🚀 Pipeline 封装 =================
    # context/context_manager.py (build 方法改造)
    def build(
        self,
        state: Dict[str, Any],
        memory: SimpleMemory,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        GSSC 多源上下文构建流水线。
        自动聚合: 对话历史(state["messages"]) + RAG检索(state["retrieved_context"]) + 长期记忆(memory.search)
        """
        cfg = config or {}
        
        # ========== G: Gather（汇聚） ==========
        conv_messages = state.get("messages", [])
        query = state.get("input", "") or state.get("messages", [])[-1].content if state.get("messages") else ""
        
        # 从 Memory 检索相关经验
        mem_limit = cfg.get("mem_limit", 3)
        mem_items = memory.search(query=query, limit=mem_limit) if memory else []
        
        # ========== S: Select（筛选对话窗口） ==========
        conv_window = self.select(
            conv_messages,
            agent_name=cfg.get("agent_filter"),
            roles=cfg.get("role_filter"),
            limit=cfg.get("conv_limit", 15)
        )
        
        # ========== S: Structure（结构化组装） ==========
        prompt_parts = []
        
        # 1. RAG 文档（优先级最高，放在前面）
            
        # 2. Memory 经验（结构化摘要）
        if mem_items:
            mem_str = "\n".join(f"- {str(item)}" for item in mem_items)
            prompt_parts.append(f"<context type='long_term_memory'>\n{mem_str}\n</context>")
            
        # 3. 对话历史（使用 ContextManager 自身格式化）
        conv_str = self.structure(conv_window, format_type=cfg.get("format", "plain"))
        prompt_parts.append(f"<context type='conversation_history'>\n{conv_str}\n</context>")
        
        structured_prompt = "\n\n".join(prompt_parts)
        
        # ========== C: Compress（压缩防超限） ==========
        return self.compress(
            structured_prompt,
            max_tokens=cfg.get("max_tokens"),
            compression_mode=cfg.get("compression_mode", "truncate")
        )