# ============================================================
# config/prompt_templates.py
# 全局 Prompt 模板库（基于 Jinja2）
# ============================================================
# 本文件集中管理所有 Agent 使用的系统提示词、用户提示词模板。
# 采用 Jinja2 模板引擎，支持变量注入和条件渲染。
#
# 【设计原则】
# - 所有 Prompt 都应版本化管理，便于 A/B 测试
# - 模板文件存放在 config/prompts/ 目录下（.j2 文件）
# - 本模块提供统一的渲染接口，不直接拼接字符串
# - 支持多语言（中文/英文），根据用户偏好切换
#
# 【需要实现的内容】
#
# 1. PromptTemplate — 单个提示词模板的数据类
#    字段:
#    - name: str                      # 模板唯一名称
#    - version: str                   # 版本号（如 "v1.0"）
#    - description: str               # 模板用途说明
#    - system_prompt: str             # 系统提示词（Jinja2 模板字符串）
#    - user_prompt_prefix: str        # 用户消息前置模板（可选）
#    - required_variables: list[str]  # 必须提供的变量名列表
#    - optional_variables: dict       # 可选变量及其默认值
#    - language: str                  # 语言（zh/en）
#
# 2. PromptTemplateRegistry — 模板注册与管理
#    方法:
#    - register(template): 注册模板
#    - get(name, version=None): 获取模板（默认取最新版本）
#    - render(name, variables: dict) -> str: 渲染模板
#    - load_from_directory(path): 从目录批量加载 .j2 文件
#    - list_templates(): 列出所有模板名称
#
# 3. 预置核心 Prompt 模板（内联定义）
#
#    SYSTEM_PROMPTS 字典，包含:
#
#    "neurotex_base" — NeuroTeX 基础系统提示词
#    内容应包含:
#    - NeuroTeX 的身份定位（学术写作智能体）
#    - 核心能力描述
#    - 行为准则（严谨、友善、专业）
#    - 输出格式要求
#
#    "simple_agent" — SimpleAgent 系统提示词
#    内容应包含:
#    - 单次推理、直接行动的指导原则
#    - 工具调用格式说明
#    - 简洁输出要求
#
#    "react_agent" — ReActAgent 系统提示词
#    内容应包含:
#    - Thought-Action-Observation 循环说明
#    - 每步思考的格式要求：Thought: / Action: / Observation:
#    - 何时停止循环的条件
#    - Final Answer 格式
#
#    "reflection_agent" — ReflectionAgent 系统提示词
#    内容应包含:
#    - 初稿生成指导
#    - 自我批评维度（逻辑性/准确性/学术规范/语言质量）
#    - 修订改进的格式要求
#    - 最终输出标准
#
#    "plan_and_solve_agent" — PlanAndSolveAgent 系统提示词
#    内容应包含:
#    - 任务分析与规划阶段要求
#    - 计划输出格式（带序号的步骤列表）
#    - 逐步执行的规范
#    - 结果汇总格式
#
#    "planner_orchestrator" — 编排层 Planner 的系统提示词
#    内容应包含:
#    - 多 Agent 任务分解原则
#    - 子任务分配格式（JSON）
#    - 依赖关系描述方式
#    - 全局目标追踪
#
#    "literature_agent" — 文献检索 Agent 提示词
#    "analysis_agent"   — 统计分析 Agent 提示词
#    "latex_agent"      — LaTeX 处理 Agent 提示词
#    "writing_agent"    — 论文写作 Agent 提示词
#    "companion_agent"  — 情感陪伴 Agent 提示词（温暖、人性化风格）
#    "router_agent"     — 路由决策 Agent 提示词（输出 JSON 路由决策）
#    "evaluator_agent"  — 结果评估 Agent 提示词
#
# 4. 用户提示词构建辅助函数
#    build_latex_review_prompt(latex_content, focus_areas) -> str
#    build_literature_search_prompt(topic, constraints) -> str
#    build_writing_outline_prompt(topic, section, style) -> str
#    build_data_analysis_prompt(data_description, analysis_type) -> str
#    build_reflection_prompt(original_output, critique_dimensions) -> str
#
# 5. 多语言支持
#    - 所有模板提供 zh（中文）和 en（英文）版本
#    - get_template_by_language(name, language) -> PromptTemplate
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, Template


@dataclass
class PromptTemplate:
    """单个提示词模板，【实现字段见上方注释】"""
    name: str = ""
    version: str = "v1.0"
    description: str = ""
    system_prompt: str = ""
    user_prompt_prefix: str = ""
    required_variables: List[str] = field(default_factory=list)
    optional_variables: Dict[str, Any] = field(default_factory=dict)
    language: str = "zh"


class PromptTemplateRegistry:
    """
    Prompt 模板注册与渲染中心。
    【需要实现的方法见上方注释】
    """

    def __init__(self) -> None:
        # 【需要实现】
        # - 初始化 _templates: dict[str, list[PromptTemplate]]（支持多版本）
        # - 初始化 Jinja2 Environment
        # - 调用 _load_builtin_templates() 加载内置模板
        pass

    def register(self, template: PromptTemplate) -> None:
        """注册模板，【需要实现】"""
        pass

    def get(self, name: str, version: Optional[str] = None) -> PromptTemplate:
        """获取模板，【需要实现】"""
        pass

    def render(self, name: str, variables: Dict[str, Any]) -> str:
        """
        渲染指定模板。
        【需要实现】
        - 获取模板对象
        - 检查 required_variables 是否全部提供
        - 合并 optional_variables 默认值
        - 使用 Jinja2 渲染并返回字符串
        """
        pass

    def _load_builtin_templates(self) -> None:
        """加载内置 Prompt 模板，【需要实现】将所有预置模板注册到注册表"""
        pass


# ---- 预置系统提示词（内联版本） ----
# 【需要实现】以下每个变量应填入完整的 Prompt 文本

NEUROTEX_BASE_SYSTEM_PROMPT = """
# 【需要实现】
# NeuroTeX 基础系统提示词
# 定位：严谨的学术写作 AI 助手，同时具备人性化陪伴特质
# 内容要点：
# 1. 身份：你是 NeuroTeX，一个专为学术论文写作设计的多智能体 AI 系统
# 2. 能力：文献检索、统计分析、LaTeX 优化、数据可视化、写作辅助
# 3. 行为准则：学术严谨性、引用规范、逻辑清晰
# 4. 输出格式：根据任务类型自适应调整输出格式
# 5. 人性化：关注用户情绪，在适当时机给予鼓励
"""

REACT_AGENT_SYSTEM_PROMPT = """
# 【需要实现】
# ReAct Agent 系统提示词
# 严格遵循 Thought-Action-Observation 格式
"""

REFLECTION_AGENT_SYSTEM_PROMPT = """
# 【需要实现】
# Reflection Agent 系统提示词
# 包含自我批评维度和修订标准
"""

COMPANION_AGENT_SYSTEM_PROMPT = """
# 【需要实现】
# 情感陪伴 Agent 系统提示词
# 温暖、支持性、学术场景下的心理陪伴
# 关键：不是心理咨询师，是科研路上的智能伙伴
"""


# 全局模板注册表单例
# 【需要实现】在模块加载时初始化
_registry: Optional[PromptTemplateRegistry] = None


def get_prompt_registry() -> PromptTemplateRegistry:
    """获取全局 Prompt 模板注册表单例"""
    global _registry
    if _registry is None:
        _registry = PromptTemplateRegistry()
    return _registry


def render_prompt(name: str, variables: Dict[str, Any]) -> str:
    """快捷渲染函数，供外部模块直接调用"""
    return get_prompt_registry().render(name, variables)
