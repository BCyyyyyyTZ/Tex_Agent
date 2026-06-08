"""
[扩展] ReActAgent 接口定义。
实现 Reason-Act 循环推理模式：在每步先 Reason（推理）再 Act（执行工具），
循环直到满足终止条件后输出最终答案。

TODO: 开发者 B 负责实现此类（第一阶段任务）
"""
from abc import abstractmethod
from typing import List, Tuple, Optional

from agents.base_agent import BaseAgent
from core.message import AgentMessage
from tools.base_tool import BaseTool


class ReActAgent(BaseAgent):
    """
    [扩展] ReAct 模式 Agent 抽象基类。

    工作流程（循环直到 is_done() 返回 True 或达到 MAX_ITERATIONS）：
        1. Reason: 根据当前观察分析下一步应采取什么行动（Thought）
        2. Act:    选择并调用工具执行行动（Action + Action Input）
        3. Observe: 获取工具执行结果，作为下一轮 Reason 的输入（Observation）
        满足终止条件后 → 输出 Final Answer

    适用场景：需要多步推理和工具调用的复杂任务，如文献检索+分析、LaTeX 解析+修复等。

    Class Attributes:
        MAX_ITERATIONS: 最大 ReAct 循环轮数，防止无限循环，默认 10。

    TODO: 开发者 B 实现时建议参考 LangChain 的 ReActSingleInputOutputParser 进行格式解析
    """

    MAX_ITERATIONS: int = 10

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: Optional[List[BaseTool]] = None,
    ):
        """
        初始化 ReAct Agent 的基础字段。

        Args:
            name: Agent 名称/标识
            system_prompt: system 提示词
            tools: 可用工具列表
        """
        self._name = name
        self.system_prompt = system_prompt
        self.tools: List[BaseTool] = tools or []
        self._tool_map = {t.name: t for t in self.tools}

    @property
    def name(self) -> str:
        """
        返回 Agent 名称（只读）。
        """
        return self._name

    @abstractmethod
    def reason(self, observation: str, history: List[Tuple[str, str]]) -> str:
        """
        推理阶段：根据观察结果和历史记录决定下一步行动。

        Args:
            observation: 上一步工具执行的观察结果（首轮为空字符串）。
            history: 推理历史列表，每项为 (thought, action) 元组。

        Returns:
            本轮推理文本（Thought），描述下一步计划。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def act(self, thought: str) -> Tuple[str, str]:
        """
        行动阶段：根据推理结果选择并准备执行工具。

        Args:
            thought: reason() 返回的推理文本。

        Returns:
            (tool_name, tool_input) 元组。
            若 tool_name == "final_answer"，表示循环终止，tool_input 为最终答案。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def is_done(self, thought: str, action: str) -> bool:
        """
        终止条件判断。

        Args:
            thought: 当前推理文本。
            action: 当前行动（tool_name）。

        Returns:
            True 表示已得出最终答案，循环终止。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, message: AgentMessage) -> AgentMessage:
        """
        ReAct 循环主流程（占位实现）。

        TODO: 开发者 B 在此实现完整的 ReAct 循环逻辑：
              1. 初始化 observation = message.content，history = []
              2. 循环调用 reason() → act() → 执行工具 → 更新 observation
              3. 调用 is_done() 判断是否终止
              4. 构造并返回 AgentMessage(role="assistant", ...)
        """
        raise NotImplementedError(
            "ReActAgent.run() 尚未实现。"
            "请参考 reason()/act()/is_done() 接口文档实现 ReAct 循环主体逻辑。"
        )

    def reset(self) -> None:
        """重置 Agent 状态，子类需清空推理历史和工具调用记录。"""
        raise NotImplementedError
