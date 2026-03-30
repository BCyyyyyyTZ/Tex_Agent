# ============================================================
# agents/base/react_agent.py
# ReActAgent —— 思考-行动-观察循环智能体
# ============================================================
# ReActAgent 实现经典的 ReAct（Reasoning + Acting）范式。
# 在每一步中交替进行"思考（Thought）→ 行动（Action）→ 观察（Observation）"，
# 直到得出最终答案或达到最大步数。
#
# 参考论文：ReAct: Synergizing Reasoning and Acting in Language Models
#
# 负责人：乔雨霖
#
# 【需要实现的内容】
#
# 1. ReActStep — 数据类，记录一步 ReAct 循环
#    字段:
#    - step_number: int
#    - thought: str          # Thought: 当前的推理想法
#    - action: str           # Action: 决定执行的工具/操作名
#    - action_input: dict    # 工具调用的参数
#    - observation: str      # Observation: 工具执行结果
#    - timestamp: datetime
#
# 2. ReActAgent 类（继承 BaseAgent）
#    agent_type = "react"
#
#    额外属性:
#    - max_steps: int                     # 最大循环步数（防止死循环）
#    - thought_delimiter: str             # 解析 Thought 的分隔符
#    - action_delimiter: str              # 解析 Action 的分隔符
#    - observation_delimiter: str         # 解析 Observation 的分隔符
#    - steps: list[ReActStep]             # 当前任务的步骤记录
#    - stop_sequences: list[str]          # 触发停止的字符串列表
#
#    实现 run(context: TaskContext) -> AgentResult:
#    执行流程:
#    a. 初始化 steps 列表
#    b. 构建初始提示词（包含工具列表说明）
#    c. 循环执行 ReAct 步骤，直到：
#       - LLM 输出 "Final Answer:" 或
#       - 达到 max_steps 或
#       - 发生不可恢复错误
#    d. 在每一步中:
#       i.  调用 _think() 获取模型输出
#       ii. 调用 _parse_react_output() 解析 Thought/Action/ActionInput
#       iii.调用 _execute_action() 执行工具
#       iv. 获取 Observation
#       v.  将本步结果添加到对话历史
#    e. 提取 Final Answer 并构建 AgentResult
#
#    实现 _think(context, history) -> str:
#    - 将当前所有 steps 序列化为对话历史消息
#    - 调用 LLM，使用 stop=["Observation:"] 让模型在观察前停止
#    - 返回模型输出（包含 Thought 和 Action）
#
#    额外方法:
#
#    _parse_react_output(output: str) -> tuple[str, str, dict]:
#    - 解析 LLM 输出，提取 Thought、Action、ActionInput
#    - 格式示例:
#      Thought: 我需要先搜索相关文献
#      Action: search_arxiv
#      Action Input: {"query": "transformer attention mechanism", "max_results": 5}
#    - 解析失败时抛出 AgentError 或回退到自然语言解析
#
#    async _execute_action(action: str, action_input: dict) -> str:
#    - 根据 action 名称调用对应工具
#    - 格式化工具返回结果为字符串（Observation）
#    - 处理工具异常：将错误信息作为 Observation 返回（而非中断）
#    - 记录工具调用日志
#
#    _build_tool_description() -> str:
#    - 生成所有可用工具的描述文本
#    - 格式：工具名、参数说明、使用示例
#    - 注入到系统提示词中
#
#    _is_final_answer(output: str) -> bool:
#    - 判断输出是否包含最终答案标记
#
#    _extract_final_answer(output: str) -> str:
#    - 从输出中提取 "Final Answer:" 后的内容
#
#    get_reasoning_trace() -> list[ReActStep]:
#    - 返回完整的推理步骤轨迹（供调试和日志）
#
#    _build_scratchpad(steps) -> str:
#    - 将已执行的步骤构建为 scratchpad 格式字符串
#    - 注入到下一次 LLM 调用的用户消息中
#
# 3. ReAct 格式规范（用于提示词工程）
#    系统提示词中需要明确告知模型：
#    - 每一步必须以 "Thought:" 开头
#    - 然后 "Action:" 指定工具名
#    - 然后 "Action Input:" 提供 JSON 格式参数
#    - 系统会提供 "Observation:" 作为工具结果
#    - 得出结论时输出 "Final Answer:"
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.base_agent import BaseAgent, AgentResult, TaskContext


@dataclass
class ReActStep:
    """ReAct 循环单步记录，【实现字段见上方注释】"""
    step_number: int = 0
    thought: str = ""
    action: str = ""
    action_input: Dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ReActAgent(BaseAgent):
    """
    思考-行动-观察循环 Agent（ReAct 范式）。
    【完整实现规范见上方注释】

    负责人：乔雨霖
    """

    agent_type: str = "react"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "ReActAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        # 【需要实现】初始化额外属性
        self.max_steps: int = 10
        self.thought_delimiter: str = "Thought:"
        self.action_delimiter: str = "Action:"
        self.observation_delimiter: str = "Observation:"
        self.steps: List[ReActStep] = []
        self.stop_sequences: List[str] = ["Observation:"]

    async def run(self, context: TaskContext) -> AgentResult:
        """
        ReAct 循环主执行逻辑。
        【需要实现完整循环流程，详见上方注释】
        """
        pass

    async def _think(self, context: TaskContext, history: List[Any]) -> str:
        """
        调用 LLM 进行一步推理。
        【需要实现】使用 stop sequences 在 Observation 前停止
        """
        pass

    def _parse_react_output(
        self, output: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        解析 LLM 输出的 Thought/Action/ActionInput。
        【需要实现】见上方注释中的格式规范
        """
        pass

    async def _execute_action(
        self, action: str, action_input: Dict[str, Any]
    ) -> str:
        """
        执行工具调用并返回 Observation。
        【需要实现】见上方注释
        """
        pass

    def _build_tool_description(self) -> str:
        """生成工具描述文本，【需要实现】"""
        pass

    def _is_final_answer(self, output: str) -> bool:
        """判断是否包含最终答案，【需要实现】"""
        pass

    def _extract_final_answer(self, output: str) -> str:
        """提取最终答案内容，【需要实现】"""
        pass

    def get_reasoning_trace(self) -> List[ReActStep]:
        """返回完整推理轨迹，【需要实现】"""
        return self.steps.copy()

    def _build_scratchpad(self, steps: List[ReActStep]) -> str:
        """将已执行步骤构建为 scratchpad，【需要实现】"""
        pass
