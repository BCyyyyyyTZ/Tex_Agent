# ============================================================
# agents/base/reflection_agent.py
# ReflectionAgent —— 自我反思与修正智能体
# ============================================================
# ReflectionAgent 实现"生成-批评-修订"循环（Generate-Critique-Revise）。
# Agent 先生成初始输出，然后对输出进行自我批评，最后根据批评修订输出。
# 可配置多轮反思，每轮都在上一轮结果的基础上改进。
#
# 适用场景：
# - LaTeX 代码质量优化（多次润色）
# - 学术写作质量提升
# - 需要严格验证正确性的分析任务
#
# 负责人：毛炜翔
#
# 【需要实现的内容】
#
# 1. ReflectionRound — 数据类，记录一轮反思
#    字段:
#    - round_number: int
#    - initial_output: str       # 本轮的初始输出
#    - critique: str             # 对初始输出的批评
#    - revised_output: str       # 修订后的输出
#    - improvement_score: float  # 改进程度评分（0-1，由 LLM 评估）
#    - critique_dimensions: dict # 各批评维度的评分
#    - timestamp: datetime
#
# 2. CritiqueDimension — 枚举，批评维度
#    - ACCURACY         # 学术准确性
#    - LOGIC            # 逻辑连贯性
#    - ACADEMIC_STYLE   # 学术写作规范
#    - COMPLETENESS     # 内容完整性
#    - CLARITY          # 表达清晰度
#    - LATEX_CORRECTNESS# LaTeX 语法正确性（专用维度）
#    - CITATION_FORMAT  # 引用格式规范
#
# 3. ReflectionAgent 类（继承 BaseAgent）
#    agent_type = "reflection"
#
#    额外属性:
#    - max_reflection_rounds: int       # 最大反思轮次（默认3）
#    - reflection_threshold: float      # 质量阈值，达到则停止（默认0.85）
#    - critique_dimensions: list[CritiqueDimension]  # 启用的批评维度
#    - use_external_critic: bool        # 是否使用独立批评者 Agent/模型
#    - critic_model: str                # 批评者模型（可与生成者不同）
#    - reflection_history: list[ReflectionRound]
#
#    实现 run(context: TaskContext) -> AgentResult:
#    执行流程:
#    a. 生成初始输出（调用 _generate_initial_output）
#    b. 循环进行反思（最多 max_reflection_rounds 次）：
#       i.  对当前输出进行批评（_critique_output）
#       ii. 评估批评结果的质量分（_evaluate_quality）
#       iii.如果质量分 >= threshold，提前停止
#       iv. 根据批评修订输出（_revise_output）
#       v.  记录本轮反思到 reflection_history
#    c. 将最终输出（最后一轮的 revised_output）包装为 AgentResult
#    d. 在 artifacts 中附带所有反思轮次的记录
#
#    实现 _think(context, history) -> str:
#    - 基础生成调用，用于初始输出生成
#
#    额外方法:
#
#    async _generate_initial_output(context) -> str:
#    - 基于任务上下文生成第一版输出
#    - 使用生成者模型和生成专用提示词
#
#    async _critique_output(output: str, dimensions: list) -> dict:
#    - 对输出进行多维度批评
#    - 如果 use_external_critic=True，使用独立的 critic_model
#    - 返回字典：{"dimension": {"score": float, "comment": str}}
#    - 同时返回总体改进建议
#
#    async _revise_output(
#        original: str, critique: dict, context: TaskContext
#    ) -> str:
#    - 基于批评结果修订输出
#    - 提示词中明确列出每个维度的问题和改进要求
#    - 返回修订后的输出
#
#    _evaluate_quality(critique: dict) -> float:
#    - 将各维度评分聚合为单一质量分（加权平均）
#    - 返回 0-1 之间的浮点数
#
#    _has_improved(prev_round, curr_round) -> bool:
#    - 判断当前轮次是否相比上一轮有实质性改进
#    - 防止在已很好的结果上反复修改造成退化
#
#    get_reflection_history() -> list[ReflectionRound]:
#    - 返回完整的反思历史记录
#
#    _format_critique_for_revision(critique: dict) -> str:
#    - 将批评字典格式化为修订提示词中的可读格式
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, AgentResult, TaskContext


class CritiqueDimension(str, Enum):
    """批评维度枚举，【实现见上方注释】"""
    ACCURACY = "accuracy"
    LOGIC = "logic"
    ACADEMIC_STYLE = "academic_style"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    LATEX_CORRECTNESS = "latex_correctness"
    CITATION_FORMAT = "citation_format"


@dataclass
class ReflectionRound:
    """一轮反思记录，【实现字段见上方注释】"""
    round_number: int = 0
    initial_output: str = ""
    critique: Dict[str, Any] = field(default_factory=dict)
    revised_output: str = ""
    improvement_score: float = 0.0
    critique_dimensions: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ReflectionAgent(BaseAgent):
    """
    自我反思与修正 Agent（Generate-Critique-Revise 范式）。
    【完整实现规范见上方注释】

    负责人：毛炜翔
    """

    agent_type: str = "reflection"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "ReflectionAgent",
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(name=name, config=config)
        # 【需要实现】初始化额外属性
        self.max_reflection_rounds: int = 3
        self.reflection_threshold: float = 0.85
        self.critique_dimensions: List[CritiqueDimension] = list(CritiqueDimension)
        self.use_external_critic: bool = False
        self.critic_model: str = ""
        self.reflection_history: List[ReflectionRound] = []

    async def run(self, context: TaskContext) -> AgentResult:
        """
        生成-批评-修订循环主逻辑。
        【需要实现完整循环流程，详见上方注释】
        """
        pass

    async def _think(self, context: TaskContext, history: List[Any]) -> str:
        """基础生成调用，【需要实现】"""
        pass

    async def _generate_initial_output(self, context: TaskContext) -> str:
        """生成初始输出，【需要实现】"""
        pass

    async def _critique_output(
        self, output: str, dimensions: List[CritiqueDimension]
    ) -> Dict[str, Any]:
        """
        多维度批评输出。
        【需要实现】见上方注释中的批评格式要求
        """
        pass

    async def _revise_output(
        self,
        original: str,
        critique: Dict[str, Any],
        context: TaskContext,
    ) -> str:
        """基于批评修订输出，【需要实现】"""
        pass

    def _evaluate_quality(self, critique: Dict[str, Any]) -> float:
        """聚合各维度评分为质量分，【需要实现】"""
        pass

    def _has_improved(
        self,
        prev_round: Optional[ReflectionRound],
        curr_round: ReflectionRound,
    ) -> bool:
        """判断是否有实质性改进，【需要实现】"""
        pass

    def get_reflection_history(self) -> List[ReflectionRound]:
        """返回完整反思历史，【需要实现】"""
        return self.reflection_history.copy()

    def _format_critique_for_revision(self, critique: Dict[str, Any]) -> str:
        """格式化批评为修订提示词，【需要实现】"""
        pass
