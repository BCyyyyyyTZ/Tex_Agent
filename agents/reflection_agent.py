"""
[扩展] ReflectionAgent 接口定义。
实现自我反思迭代模式：生成初始答案后，通过批判性反思机制识别不足并迭代改进。

TODO: 开发者 B 负责实现此类（第一阶段任务）
"""
from abc import abstractmethod
from typing import Optional

from agents.base_agent import BaseAgent
from core.message import AgentMessage


class ReflectionAgent(BaseAgent):
    """
    [扩展] 自我反思 Agent 抽象基类。

    工作流程（循环直到 is_satisfactory() 返回 True 或达到 MAX_REFLECTION_ROUNDS）：
        1. Generate: 生成初始答案
        2. Reflect:  批判性分析答案的不足（充当"评审者"角色）
        3. Refine:   基于反思结果改进答案（充当"修改者"角色）
        重复 2-3 直到质量满足要求

    适用场景：论文润色、表达改进、逻辑一致性检查等高质量要求的写作任务。

    Class Attributes:
        MAX_REFLECTION_ROUNDS: 最大反思迭代轮数，默认 3。

    TODO: 开发者 B 实现时建议将 Generate/Reflect/Refine 分配给不同 system prompt 的 LLM 调用
    """

    MAX_REFLECTION_ROUNDS: int = 3

    def __init__(self, name: str, system_prompt: str):
        self._name = name
        self.system_prompt = system_prompt

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def generate(self, message: AgentMessage) -> str:
        """
        生成阶段：根据输入消息生成初始答案。

        Args:
            message: 用户输入的 AgentMessage。

        Returns:
            初始答案文本字符串。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def reflect(self, answer: str, context: str) -> str:
        """
        反思阶段：以评审者身份批判性分析答案的不足之处。

        Args:
            answer: 当前答案文本。
            context: 原始任务上下文（用户的问题/要求）。

        Returns:
            反思评论文本，指出具体问题和改进方向。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def refine(self, answer: str, reflection: str) -> str:
        """
        改进阶段：基于反思评论修改并改善答案。

        Args:
            answer: 当前答案文本。
            reflection: reflect() 返回的反思评论。

        Returns:
            改进后的答案文本。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def is_satisfactory(self, answer: str, reflection: str) -> bool:
        """
        质量评估：判断当前答案是否已满足质量要求，决定是否继续迭代。

        Args:
            answer: 当前答案文本。
            reflection: 当前轮的反思评论。

        Returns:
            True 表示质量达标，停止迭代；False 表示继续反思改进。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, message: AgentMessage) -> AgentMessage:
        """
        Generate-Reflect-Refine 迭代主流程（占位实现）。

        TODO: 开发者 B 在此实现完整逻辑：
              1. answer = generate(message)
              2. for round in range(MAX_REFLECTION_ROUNDS):
                     reflection = reflect(answer, message.content)
                     if is_satisfactory(answer, reflection): break
                     answer = refine(answer, reflection)
              3. 返回 AgentMessage(role="assistant", content=answer, ...)
        """
        raise NotImplementedError(
            "ReflectionAgent.run() 尚未实现。"
            "请参考 generate()/reflect()/refine()/is_satisfactory() 接口实现迭代逻辑。"
        )

    def reset(self) -> None:
        raise NotImplementedError
