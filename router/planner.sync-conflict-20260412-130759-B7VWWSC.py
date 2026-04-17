"""
[扩展] MASPlanner 多智能体系统规划器接口定义。
预留主控引擎的任务分解、Agent 分配与执行验证接口。

TODO: 开发者 D 负责实现此类（第二阶段任务，建议与 BaseRouter 配合使用）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    # 仅用于类型提示，运行时不导入，避免与 workflow 层产生循环依赖
    from workflow.workflow_parser import NodeConfig, EdgeConfig


@dataclass
class TaskPlan:
    """
    多 Agent 任务执行计划数据结构。

    Attributes:
        plan_id: 计划唯一标识符。
        original_task: 原始用户任务描述文本。
        subtasks: 分解后的子任务描述列表（自然语言）。
        assigned_agents: 子任务与 Agent 的分配映射
                         {subtask_index: agent_name}。
        status: 计划状态（"pending" / "running" / "done" / "failed"）。
        created_at: 计划创建的 UTC 时间戳。
        results: 各子任务的执行结果列表（与 subtasks 对应）。
    """

    plan_id: str
    original_task: str
    subtasks: List[str] = field(default_factory=list)
    assigned_agents: dict = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    results: List[str] = field(default_factory=list)


class MASPlanner(ABC):
    """
    [扩展] 多智能体系统规划器抽象基类。

    功能规划：
        1. 任务分解（Task Decomposition）：
           将用户的复杂任务分解为可并行或串行的子任务列表
        2. 任务分配（Task Assignment）：
           将子任务分配给最合适的 Agent（配合 BaseRouter 使用）
        3. 执行监控（Execution Monitoring）：
           追踪各子任务的执行状态，处理失败重试
        4. 结果验证（Result Validation）：
           验证子任务结果是否满足质量要求

    适用场景：复杂的多 Agent 协同任务，如：
        用户任务："帮我写论文的 Introduction 章节"
        分解为：
          - subtask_1 → DesignAgent：规划 Introduction 结构
          - subtask_2 → ArxivSearchTool：检索背景文献
          - subtask_3 → ExecuteAgent：撰写 Introduction 草稿
          - subtask_4 → ReflectionAgent：润色与优化

    TODO: 开发者 D 实现建议：
          - decompose() 使用 LLM 进行任务分解，输出结构化的子任务列表
          - assign() 配合 BaseRouter.evaluate_complexity() 选择合适 Agent
          - validate() 使用 LLM 评估结果质量，决定是否需要重试
    """

    @abstractmethod
    def decompose(self, task: str) -> TaskPlan:
        """
        将复杂任务分解为子任务计划。

        Args:
            task: 原始用户任务描述字符串。

        Returns:
            包含子任务列表的 TaskPlan 对象（subtasks 已填充，status="pending"）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def assign(self, plan: TaskPlan, available_agents: List[str]) -> TaskPlan:
        """
        为计划中的每个子任务分配合适的 Agent。

        Args:
            plan: 待分配的 TaskPlan（subtasks 已填充）。
            available_agents: 当前可用的 Agent 名称列表。

        Returns:
            填充了 assigned_agents 字典的 TaskPlan。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, plan: TaskPlan, results: List[str]) -> bool:
        """
        验证子任务执行结果是否满足质量要求。

        Args:
            plan: 原始任务计划（含任务描述和分配信息）。
            results: 各子任务的执行结果列表（与 plan.subtasks 对应）。

        Returns:
            True 表示所有结果满足要求，可进入整合阶段；
            False 表示结果不满足要求，需要重试或调整策略。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def to_graph_config(
        self,
        plan: "TaskPlan",
    ) -> "Tuple[List[NodeConfig], List[EdgeConfig]]":
        """
        [扩展] 将 MASPlanner 生成的 TaskPlan 翻译为图拓扑配置。

        这是 MASPlanner 与 WorkflowParser 之间的"协议转换器"，
        填补任务规划层与图构建层之间缺失的翻译环节。

        典型调用链（未来）：
            plan          = planner.decompose(task)
            plan          = planner.assign(plan, available_agents)
            nodes, edges  = planner.to_graph_config(plan)   ← 此方法
            app           = parser.build_graph(nodes, edges)

        翻译规则（实现建议）：
          - plan.subtasks[i]        → NodeConfig(node_id=f"step_{i}", ...)
          - plan.assigned_agents[i] → NodeConfig.agent_name
          - 串行依赖                → EdgeConfig(from_node="step_i",
                                                  to_node="step_{i+1}")
          - 含 "validate"/"reflect" → EdgeConfig(condition="state['validated']")
            的校验类子任务            带条件边，支持质量不达标时的回环重试

        Args:
            plan: 已填充 subtasks 和 assigned_agents 的 TaskPlan 实例。

        Returns:
            (nodes, edges) 元组，可直接传入 WorkflowParser.build_graph()。

        Raises:
            NotImplementedError: 子类实现前调用时抛出。
        """
        raise NotImplementedError(
            "to_graph_config() 尚未实现，"
            "请由开发者 D 在 MASPlanner 子类中完成此翻译逻辑。"
        )

    # TODO: 未来增加 monitor(plan_id) 接口，实时追踪计划执行状态
    # TODO: 未来增加 replan(plan, failed_subtask_idx) 接口，
    #       当子任务失败时动态调整执行计划
    # TODO: 未来增加 aggregate(plan, results) 接口，
    #       整合所有子任务结果生成最终答案
