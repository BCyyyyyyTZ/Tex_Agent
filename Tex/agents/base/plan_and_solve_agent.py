# ============================================================
# agents/base/plan_and_solve_agent.py
# PlanAndSolveAgent —— 计划-执行模式智能体
# ============================================================
# PlanAndSolveAgent 实现"先规划后执行"的两阶段范式。
# 第一阶段：对复杂任务进行结构化分解，生成步骤化执行计划。
# 第二阶段：按计划逐步执行每个子步骤，并在执行中动态调整计划。
#
# 适用场景：
# - 复杂统计分析任务（需要多步计算）
# - 多节文章写作规划
# - 需要明确执行路径的综合任务
#
# 参考论文：Plan-and-Solve Prompting: Improving Zero-Shot
#           Chain-of-Thought Reasoning by Large Language Models
#
# 负责人：唐骏涛
#
# 【需要实现的内容】
#
# 1. ExecutionStep — 数据类，执行计划中的单个步骤
#    字段:
#    - step_id: str               # 步骤唯一 ID
#    - step_number: int
#    - description: str           # 步骤描述
#    - action_type: str           # 步骤类型（think/tool_call/synthesize）
#    - tool_name: Optional[str]   # 如果是工具调用，工具名
#    - tool_params: dict          # 工具调用参数（可能包含模板变量）
#    - dependencies: list[str]    # 依赖的前置步骤 ID
#    - status: str                # pending/running/completed/skipped/failed
#    - result: Optional[Any]      # 执行结果
#    - error: Optional[str]       # 错误信息
#
# 2. ExecutionPlan — 数据类，完整执行计划
#    字段:
#    - plan_id: str
#    - task_description: str
#    - steps: list[ExecutionStep]
#    - created_at: datetime
#    - completed_at: Optional[datetime]
#    - total_steps: int
#    - completed_steps: int
#    - overall_goal: str          # 任务总体目标（用于最终汇总）
#    - notes: str                 # 规划时的额外备注
#
#    方法:
#    - get_next_step() -> Optional[ExecutionStep]: 获取下一个待执行步骤
#    - get_completed_results() -> dict: 获取所有已完成步骤的结果字典
#    - is_complete() -> bool: 判断是否所有步骤都已完成
#    - update_step(step_id, status, result) -> None: 更新步骤状态
#    - can_execute(step_id) -> bool: 检查步骤的依赖是否都已完成
#
# 3. PlanAndSolveAgent 类（继承 BaseAgent）
#    agent_type = "plan_and_solve"
#
#    额外属性:
#    - planning_model: str        # 规划阶段使用的模型（可能更强）
#    - execution_model: str       # 执行阶段使用的模型
#    - max_plan_steps: int = 8    # 最大计划步骤数
#    - enable_plan_revision: bool # 执行中是否允许修改计划
#    - current_plan: Optional[ExecutionPlan]
#    - plan_output_format: str    # "json" 或 "markdown"
#
#    实现 run(context: TaskContext) -> AgentResult:
#    执行流程:
#    a. 阶段1 - 规划:
#       - 调用 _create_plan(context) 生成执行计划
#       - 打印/记录计划概览（步骤数、预计复杂度）
#    b. 阶段2 - 执行:
#       - 循环获取下一个可执行步骤
#       - 对每个步骤调用 _execute_step(step, plan)
#       - 更新步骤状态和结果
#       - 如果 enable_plan_revision，检查是否需要修订计划
#    c. 阶段3 - 汇总:
#       - 调用 _synthesize_results(plan) 整合所有步骤结果
#       - 生成最终输出
#    d. 构建并返回 AgentResult（artifacts 中包含执行计划）
#
#    实现 _think(context, history) -> str:
#    - 用于规划阶段的 LLM 调用
#
#    额外方法:
#
#    async _create_plan(context) -> ExecutionPlan:
#    - 调用 LLM（使用 planning_model）生成执行计划
#    - 提示词要求 LLM 输出 JSON 格式的步骤列表
#    - 解析 JSON 并构建 ExecutionPlan 对象
#    - 校验计划的合理性（步骤数、依赖关系无循环等）
#
#    async _execute_step(step, plan) -> Any:
#    - 根据 step.action_type 分发执行：
#      - "think": 调用 LLM 进行推理，输入前置步骤的结果
#      - "tool_call": 调用对应工具，参数支持 {{prev_step_result}} 模板
#      - "synthesize": 汇总多个前置步骤结果
#    - 返回步骤执行结果
#
#    async _synthesize_results(plan: ExecutionPlan) -> str:
#    - 将所有步骤结果汇总为最终答案
#    - 调用 LLM，输入所有步骤结果和总体目标
#
#    async _revise_plan(
#        plan: ExecutionPlan,
#        completed_step: ExecutionStep,
#        unexpected_result: Any
#    ) -> ExecutionPlan:
#    - 当某步骤结果与预期大相径庭时，重新规划后续步骤
#    - 保留已完成步骤，只修改未执行的步骤
#
#    _resolve_template_params(
#        params: dict, completed_results: dict
#    ) -> dict:
#    - 将步骤参数中的 {{step_N_result}} 模板变量替换为实际值
#
#    get_current_plan() -> Optional[ExecutionPlan]:
#    - 返回当前执行计划（供监控/UI 显示）
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentResult, TaskContext


@dataclass
class ExecutionStep:
    """执行计划中的单个步骤，【实现字段见上方注释】"""
    step_id: str = ""
    step_number: int = 0
    description: str = ""
    action_type: str = "think"
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """完整执行计划，【实现字段和方法见上方注释】"""
    plan_id: str = ""
    task_description: str = ""
    steps: List[ExecutionStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    overall_goal: str = ""
    notes: str = ""

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    def get_next_step(self) -> Optional[ExecutionStep]:
        """获取下一个可执行步骤，【需要实现】"""
        pass

    def get_completed_results(self) -> Dict[str, Any]:
        """获取所有已完成步骤的结果，【需要实现】"""
        pass

    def is_complete(self) -> bool:
        """判断计划是否全部完成，【需要实现】"""
        pass

    def update_step(
        self, step_id: str, status: str, result: Any = None
    ) -> None:
        """更新步骤状态，【需要实现】"""
        pass

    def can_execute(self, step_id: str) -> bool:
        """检查步骤的依赖是否满足，【需要实现】"""
        pass


class PlanAndSolveAgent(BaseAgent):
    """
    计划-执行模式 Agent。
    【完整实现规范见上方注释】

    负责人：唐骏涛
    """

    agent_type: str = "plan_and_solve"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "PlanAndSolveAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        # 【需要实现】初始化额外属性
        self.planning_model: str = ""
        self.execution_model: str = ""
        self.max_plan_steps: int = 8
        self.enable_plan_revision: bool = True
        self.current_plan: Optional[ExecutionPlan] = None
        self.plan_output_format: str = "json"

    async def run(self, context: TaskContext) -> AgentResult:
        """
        计划-执行主逻辑（三阶段：规划/执行/汇总）。
        【需要实现完整流程，详见上方注释】
        """
        pass

    async def _think(self, context: TaskContext, history: List[Any]) -> str:
        """规划阶段 LLM 调用，【需要实现】"""
        pass

    async def _create_plan(self, context: TaskContext) -> ExecutionPlan:
        """生成执行计划，【需要实现】"""
        pass

    async def _execute_step(
        self, step: ExecutionStep, plan: ExecutionPlan
    ) -> Any:
        """执行单个步骤，【需要实现】"""
        pass

    async def _synthesize_results(self, plan: ExecutionPlan) -> str:
        """汇总所有步骤结果，【需要实现】"""
        pass

    async def _revise_plan(
        self,
        plan: ExecutionPlan,
        completed_step: ExecutionStep,
        unexpected_result: Any,
    ) -> ExecutionPlan:
        """动态修订计划，【需要实现】"""
        pass

    def _resolve_template_params(
        self, params: Dict[str, Any], completed_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析模板参数中的变量引用，【需要实现】"""
        pass

    def get_current_plan(self) -> Optional[ExecutionPlan]:
        """返回当前执行计划，【需要实现】"""
        return self.current_plan
