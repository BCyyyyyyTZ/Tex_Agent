# ============================================================
# agents/base/simple_agent.py
# SimpleAgent —— 单次推理模式基础智能体
# ============================================================
# SimpleAgent 是最基础的 Agent 架构，实现"单次推理直接输出"模式。
# 特点：不进行多轮迭代，一次 LLM 调用直接给出最终结果。
# 适用场景：简单问答、快速响应、明确输入输出的任务。
#
# 负责人：于天泽
#
# 【需要实现的内容】
#
# 1. SimpleAgent 类（继承 BaseAgent）
#    agent_type = "simple"
#
#    额外属性:
#    - structured_output_schema: Optional[dict]  # 结构化输出 schema
#    - fallback_message: str                     # LLM 调用失败时的回退响应
#
#    实现 run(context: TaskContext) -> AgentResult:
#    执行流程:
#    a. 从 context 中提取任务描述和输入数据
#    b. 构建消息列表:
#       [SystemMessage(system_prompt), HumanMessage(task + input)]
#    c. 如果 RAG 启用，先检索相关知识并注入到用户消息中
#    d. 如果 Memory 启用，检索历史相关上下文注入
#    e. 一次性调用 LLM（可选结构化输出）
#    f. 解析 LLM 响应（如需 JSON 格式则解析 JSON）
#    g. 构建并返回 AgentResult
#    h. 将重要信息存入记忆（如启用）
#
#    实现 _think(context, history) -> str:
#    - 构建完整的消息列表（包含 system + history + current）
#    - 调用 self._llm 的 chat completion API
#    - 处理 streaming 输出（如启用）
#    - 返回模型输出文本
#
#    额外方法:
#
#    async run_with_tools(context, tools) -> AgentResult:
#    - 支持工具调用的单轮推理
#    - 调用 LLM 时附带工具定义
#    - 如果 LLM 返回工具调用，执行工具并将结果追加到消息
#    - 再次调用 LLM 得到最终答案（共 2 次调用，仍算"单次"）
#
#    set_structured_output(schema: dict) -> None:
#    - 设置 JSON 结构化输出约束
#    - 调用 LLM 时使用 response_format={"type": "json_object"}
#
#    _format_input(context) -> str:
#    - 将 TaskContext 格式化为清晰的用户提示词
#    - 支持不同的输入类型（纯文本/LaTeX/数据/文件路径）
#
#    _parse_output(raw_output: str) -> Any:
#    - 解析 LLM 原始输出
#    - 如果设置了 schema，尝试解析为 JSON
#    - 解析失败时返回原始字符串并记录警告
#
# 2. 使用示例（写在模块末尾的 if __name__ == "__main__" 中）
#    演示 SimpleAgent 完成一个 LaTeX 格式检查任务
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentResult, TaskContext


class SimpleAgent(BaseAgent):
    """
    单次推理模式 Agent。
    一次 LLM 调用直接返回结果，适合快速响应任务。
    【完整实现规范见上方注释】

    负责人：于天泽
    """

    agent_type: str = "simple"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "SimpleAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        # 【需要实现】初始化额外属性
        self.structured_output_schema: Optional[Dict] = None
        self.fallback_message: str = "抱歉，我暂时无法处理这个请求，请稍后重试。"

    async def run(self, context: TaskContext) -> AgentResult:
        """
        单次推理执行核心。
        【需要实现完整执行流程，详见上方注释】
        """
        pass

    async def _think(self, context: TaskContext, history: List[Any]) -> str:
        """
        调用 LLM 进行单次推理。
        【需要实现】构建消息并调用 LLM API
        """
        pass

    async def run_with_tools(
        self, context: TaskContext, tools: List[Any]
    ) -> AgentResult:
        """
        支持工具调用的单轮推理。
        【需要实现】见上方注释
        """
        pass

    def set_structured_output(self, schema: Dict) -> None:
        """设置结构化输出约束，【需要实现】"""
        pass

    def _format_input(self, context: TaskContext) -> str:
        """格式化输入为用户提示词，【需要实现】"""
        pass

    def _parse_output(self, raw_output: str) -> Any:
        """解析 LLM 原始输出，【需要实现】"""
        pass
