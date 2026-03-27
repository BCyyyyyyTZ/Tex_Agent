# ============================================================
# router/task_classifier.py
# TaskClassifier —— 任务意图分类器
# ============================================================
# TaskClassifier 分析用户输入，将任务分类到预定义的任务类型，
# 为 Router 的路由决策提供分类依据。
# 采用"规则 + 轻量级模型"双重分类策略，兼顾速度和准确性。
#
# 【需要实现的内容】
#
# 1. TaskCategory — 枚举，任务类别
#    - LATEX_SYNTAX_FIX      # LaTeX 语法修复
#    - LATEX_STYLE_OPTIMIZE  # LaTeX 格式/风格优化
#    - LITERATURE_SEARCH     # 文献检索
#    - TREND_ANALYSIS        # 趋势分析
#    - DATA_ANALYSIS         # 数据统计分析
#    - VISUALIZATION         # 数据可视化
#    - WRITING_OUTLINE       # 论文大纲生成
#    - SECTION_WRITING       # 章节内容撰写
#    - SECTION_REVIEW        # 章节内容评审
#    - IMAGE_GENERATION      # 图像生成
#    - GENERAL_QA            # 一般性问答
#    - EMOTIONAL_SUPPORT     # 情感支持（触发 CompanionAgent）
#    - COMPLEX_TASK          # 复杂任务（需要 Planner 分解）
#
# 2. ClassificationResult — 分类结果
#    字段:
#    - primary_category: TaskCategory   # 主分类
#    - secondary_category: Optional[TaskCategory]  # 次分类
#    - confidence: float                # 分类置信度（0-1）
#    - detected_entities: dict          # 识别到的实体（文件路径、关键词等）
#    - requires_files: bool             # 是否需要用户提供文件
#    - estimated_complexity: float      # 预估复杂度
#    - key_phrases: list[str]           # 关键短语
#
# 3. TaskClassifier 类
#
#    核心方法:
#
#    classify(
#        user_input: str,
#        context: dict = {}
#    ) -> ClassificationResult:
#    - 先用规则分类（关键词匹配，毫秒级）
#    - 规则置信度低时，调用轻量级 LLM 进行精确分类
#
#    _rule_based_classify(text: str) -> ClassificationResult:
#    - 基于关键词和模式匹配的快速分类
#    - 规则示例：
#      包含 "arXiv"/"Google Scholar"/"文献" -> LITERATURE_SEARCH
#      包含 "LaTeX"/"error"/"fix" -> LATEX_SYNTAX_FIX
#      包含 "数据"/"统计"/"p值" -> DATA_ANALYSIS
#      包含 "难受"/"头疼"/"焦虑" -> EMOTIONAL_SUPPORT
#
#    async _llm_based_classify(
#        text: str, initial_result: ClassificationResult
#    ) -> ClassificationResult:
#    - 调用轻量级 LLM 进行精确分类
#    - 只在规则分类置信度 < 0.7 时触发
#    - 使用结构化 JSON 输出
#
#    _extract_entities(text: str) -> dict:
#    - 提取文件路径、arXiv ID、关键词等实体
#
#    _estimate_complexity(
#        text: str, category: TaskCategory
#    ) -> float:
#    - 基于任务描述长度、复杂度词语、多目标检测估算难度
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskCategory(str, Enum):
    """任务类别枚举，【实现见上方注释】"""
    LATEX_SYNTAX_FIX = "latex_syntax_fix"
    LATEX_STYLE_OPTIMIZE = "latex_style_optimize"
    LITERATURE_SEARCH = "literature_search"
    TREND_ANALYSIS = "trend_analysis"
    DATA_ANALYSIS = "data_analysis"
    VISUALIZATION = "visualization"
    WRITING_OUTLINE = "writing_outline"
    SECTION_WRITING = "section_writing"
    SECTION_REVIEW = "section_review"
    IMAGE_GENERATION = "image_generation"
    GENERAL_QA = "general_qa"
    EMOTIONAL_SUPPORT = "emotional_support"
    COMPLEX_TASK = "complex_task"


@dataclass
class ClassificationResult:
    """分类结果，【实现字段见上方注释】"""
    primary_category: TaskCategory = TaskCategory.GENERAL_QA
    secondary_category: Optional[TaskCategory] = None
    confidence: float = 0.0
    detected_entities: Dict[str, Any] = field(default_factory=dict)
    requires_files: bool = False
    estimated_complexity: float = 0.5
    key_phrases: List[str] = field(default_factory=list)


class TaskClassifier:
    """
    任务意图分类器。
    规则 + 轻量级 LLM 双重策略，兼顾速度和准确性。
    【完整实现规范见上方注释】
    """

    # 关键词规则表 —— {关键词列表: TaskCategory}
    KEYWORD_RULES: Dict[TaskCategory, List[str]] = {
        TaskCategory.LITERATURE_SEARCH: ["文献", "arXiv", "论文", "检索", "找论文", "survey"],
        TaskCategory.DATA_ANALYSIS: ["数据", "统计", "分析", "p值", "t检验", "回归", "CSV"],
        TaskCategory.LATEX_SYNTAX_FIX: ["LaTeX", "错误", "error", "修复", "语法", "编译失败"],
        TaskCategory.WRITING_OUTLINE: ["大纲", "框架", "章节", "结构", "写什么"],
        TaskCategory.IMAGE_GENERATION: ["生成图", "画图", "流程图", "架构图", "DALL-E"],
        TaskCategory.EMOTIONAL_SUPPORT: ["难受", "头疼", "焦虑", "压力", "累了", "放弃"],
        TaskCategory.VISUALIZATION: ["可视化", "图表", "折线图", "柱状图", "散点图"],
    }

    def classify(
        self, user_input: str, context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """分类任务意图，【需要实现】"""
        pass

    def _rule_based_classify(self, text: str) -> ClassificationResult:
        """规则分类，【需要实现】"""
        pass

    async def _llm_based_classify(
        self, text: str, initial_result: ClassificationResult
    ) -> ClassificationResult:
        """LLM 精确分类，【需要实现】"""
        pass

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体信息，【需要实现】"""
        pass

    def _estimate_complexity(
        self, text: str, category: TaskCategory
    ) -> float:
        """估算任务复杂度，【需要实现】"""
        pass
