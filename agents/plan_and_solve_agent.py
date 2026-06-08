"""
[扩展] PlanAndSolveAgent 接口定义。
实现先规划后执行的两阶段推理：先将复杂任务分解为子任务列表，再逐一执行解决。

TODO: 开发者 B 负责实现此类（第一阶段任务）
"""
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from agents.base_agent import BaseAgent
from core.message import AgentMessage


@dataclass
class SubTask:
    """
    子任务数据结构。

    Attributes:
        task_id: 子任务唯一标识（如 "subtask_1"）。
        description: 子任务的自然语言描述。
        depends_on: 依赖的前置子任务 ID 列表（空则无依赖，可并行执行）。
        result: 子任务执行完成后的结果文本（初始为空）。
        completed: 是否已执行完成。
    """

    task_id: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    result: str = ""
    completed: bool = False


class PlanAndSolveAgent(BaseAgent):
    """
    [扩展] 计划与执行 Agent 抽象基类。

    工作流程：
        1. Plan:      将复杂任务分解为有序子任务列表（考虑依赖关系）
        2. Solve:     按依赖顺序逐一（或并行）执行子任务
        3. Aggregate: 整合所有子任务结果，生成最终答案

    适用场景：复杂的多步骤论文写作任务，例如：
        "整理文献" → "分析研究现状" → "撰写 Related Work 章节"

    TODO: 开发者 B 实现时可考虑：
          - plan() 调用 LLM 进行任务分解
          - solve() 可并行执行无依赖的子任务（配合 concurrency.py）
          - 配合 MASPlanner 实现更复杂的多 Agent 协同分工
    """

    def __init__(self, name: str, system_prompt: str):
        """
        初始化计划-执行 Agent 的基础字段。

        Args:
            name: Agent 名称/标识
            system_prompt: system 提示词
        """
        self._name = name
        self.system_prompt = system_prompt

    @property
    def name(self) -> str:
        """
        返回 Agent 名称（只读）。
        """
        return self._name

    @abstractmethod
    def plan(self, message: AgentMessage) -> List[SubTask]:
        """
        规划阶段：将输入任务分解为有序的子任务列表。

        Args:
            message: 原始任务描述 AgentMessage。

        Returns:
            有序的 SubTask 列表（考虑 depends_on 依赖关系）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def solve(self, subtask: SubTask, context: List[SubTask]) -> str:
        """
        执行阶段：解决单个子任务。

        Args:
            subtask: 当前需要解决的子任务。
            context: 已完成的子任务列表（可通过 subtask.result 获取前置结果）。

        Returns:
            子任务的解决结果文本。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def aggregate(self, subtasks: List[SubTask]) -> str:
        """
        整合阶段：将所有子任务结果汇总为最终答案。

        Args:
            subtasks: 所有已完成的子任务列表（每项的 result 字段已填充）。

        Returns:
            最终整合的答案文本。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, message: AgentMessage) -> AgentMessage:
        """
        Plan-and-Solve 主流程（占位实现）。

        TODO: 开发者 B 在此实现完整的两阶段推理：
              1. subtasks = plan(message)
              2. for task in subtasks（按依赖顺序）:
                     context = [t for t in subtasks if t.completed]  # 已完成的子任务作为上下文
                     task.result = solve(task, context)
                     task.completed = True
              3. final = aggregate(subtasks)
              4. 返回 AgentMessage(role="assistant", content=final, ...)
        """
        raise NotImplementedError(
            "PlanAndSolveAgent.run() 尚未实现。"
            "请参考 plan()/solve()/aggregate() 接口实现两阶段推理逻辑。"
        )

    def reset(self) -> None:
        """
        重置 Agent 内部状态（占位，子类实现）。
        """
        raise NotImplementedError
