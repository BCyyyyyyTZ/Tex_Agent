# ============================================================
# config/agent_configs.py
# 各类 Agent 的行为参数配置
# ============================================================
# 本文件定义每种 Agent 架构和专业化 Agent 的运行参数。
# 与 settings.py 的区别：settings.py 管理系统级配置（API Key、路径等），
# 本文件专注于 Agent 的行为配置（如最大推理步数、工具集等）。
#
# 【需要实现的内容】
#
# 1. BaseAgentConfig — 所有 Agent 共用的基础配置
#    字段:
#    - name: str                        # Agent 唯一标识名
#    - description: str                 # Agent 功能描述
#    - model: str                       # 使用的 LLM 模型名
#    - temperature: float               # 生成温度
#    - max_iterations: int              # 最大迭代/推理步数（防止死循环）
#    - timeout_seconds: int             # 单次任务超时时间
#    - retry_on_failure: bool           # 失败时是否重试
#    - max_retries: int                 # 最大重试次数
#    - system_prompt_template: str      # 系统提示词模板名（对应 prompt_templates.py）
#    - available_tools: list[str]       # 可调用的工具名称列表
#    - memory_enabled: bool             # 是否接入记忆系统
#    - rag_enabled: bool                # 是否接入 RAG
#
# 2. 各 Agent 专用配置（继承 BaseAgentConfig）
#
#    SimpleAgentConfig:
#    - single_pass: bool = True         # 是否单次推理（不循环）
#    - structured_output: bool          # 是否强制结构化输出
#
#    ReActAgentConfig:
#    - max_thought_steps: int = 10      # 最大 Thought-Action 循环次数
#    - thought_delimiter: str           # Thought/Action 分隔符
#    - enable_chain_of_thought: bool    # 是否启用 CoT
#    - tool_call_format: str            # 工具调用格式（json/text）
#
#    ReflectionAgentConfig:
#    - max_reflection_rounds: int = 3   # 最大自我反思轮次
#    - reflection_threshold: float      # 触发反思的质量评分阈值
#    - critic_model: str                # 批评者模型（可与主模型不同）
#    - reflection_prompt_template: str  # 反思提示词模板
#    - enable_external_critic: bool     # 是否使用独立批评者 Agent
#
#    PlanAndSolveAgentConfig:
#    - planning_model: str              # 规划阶段使用的模型
#    - execution_model: str             # 执行阶段使用的模型
#    - max_plan_steps: int = 8          # 计划最大步骤数
#    - enable_plan_revision: bool       # 执行中是否允许修改计划
#    - plan_output_format: str          # 计划输出格式（json/markdown）
#
# 3. 专业化 Agent 配置
#
#    LiteratureAgentConfig:
#    - max_papers_per_query: int = 20
#    - supported_sources: list[str]     # 支持的文献源
#    - enable_trend_analysis: bool
#    - clustering_algorithm: str        # 聚类算法（kmeans/dbscan）
#
#    LaTeXAgentConfig:
#    - supported_templates: list[str]   # 支持的 LaTeX 模板（IEEE/ACM等）
#    - max_file_size_kb: int
#    - enable_auto_compile: bool        # 是否自动尝试编译验证
#    - error_correction_rounds: int
#
#    VisualizationAgentConfig:
#    - default_style: str               # 图表风格（ieee/acm/default）
#    - output_dpi: int = 300
#    - output_formats: list[str]        # 输出格式（png/pdf/svg）
#    - color_palette: str
#
#    CompanionAgentConfig:
#    - emotion_check_interval: int      # 每 N 轮检测一次情感状态
#    - response_style: str              # 陪伴风格（warm/professional/casual）
#    - encouragement_probability: float # 主动给予鼓励的概率
#
# 4. AgentConfigRegistry — Agent 配置注册表
#    - 以字典形式存储所有 Agent 配置
#    - 提供 get_agent_config(agent_name: str) -> BaseAgentConfig
#    - 提供 register_agent_config(config: BaseAgentConfig) 方法
#    - 支持从 YAML 文件加载自定义配置（覆盖默认值）
#
# 5. 默认配置工厂函数
#    - get_default_simple_agent_config() -> SimpleAgentConfig
#    - get_default_react_agent_config() -> ReActAgentConfig
#    - get_default_reflection_agent_config() -> ReflectionAgentConfig
#    - get_default_plan_and_solve_agent_config() -> PlanAndSolveAgentConfig
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BaseAgentConfig(BaseModel):
    """所有 Agent 的基础配置，【实现字段见上方注释】"""
    pass


class SimpleAgentConfig(BaseAgentConfig):
    """SimpleAgent 专用配置，【实现字段见上方注释】"""
    pass


class ReActAgentConfig(BaseAgentConfig):
    """ReActAgent 专用配置，【实现字段见上方注释】"""
    pass


class ReflectionAgentConfig(BaseAgentConfig):
    """ReflectionAgent 专用配置，【实现字段见上方注释】"""
    pass


class PlanAndSolveAgentConfig(BaseAgentConfig):
    """PlanAndSolveAgent 专用配置，【实现字段见上方注释】"""
    pass


class LiteratureAgentConfig(BaseAgentConfig):
    """文献检索 Agent 配置，【实现字段见上方注释】"""
    pass


class AnalysisAgentConfig(BaseAgentConfig):
    """统计分析 Agent 配置"""
    # 【需要实现】
    # - supported_analysis_types: list[str]  # 支持的分析类型
    # - max_dataset_rows: int                # 最大数据集行数限制
    # - enable_auto_feature_detection: bool  # 自动检测特征类型
    # - output_report_format: str            # 报告输出格式
    pass


class LaTeXAgentConfig(BaseAgentConfig):
    """LaTeX 处理 Agent 配置，【实现字段见上方注释】"""
    pass


class VisualizationAgentConfig(BaseAgentConfig):
    """可视化 Agent 配置，【实现字段见上方注释】"""
    pass


class WritingAgentConfig(BaseAgentConfig):
    """论文写作辅助 Agent 配置"""
    # 【需要实现】
    # - writing_style: str              # 写作风格（formal/concise）
    # - target_sections: list[str]      # 支持的论文章节类型
    # - enable_structure_suggestion: bool
    # - min_outline_depth: int
    pass


class ImageGenAgentConfig(BaseAgentConfig):
    """图像生成 Agent 配置"""
    # 【需要实现】
    # - preferred_backend: str          # 优先使用的后端（dalle/sd）
    # - default_image_size: str         # 默认图像尺寸
    # - max_images_per_request: int
    # - enable_prompt_enhancement: bool # 是否自动增强提示词
    pass


class CompanionAgentConfig(BaseAgentConfig):
    """情感陪伴 Agent 配置，【实现字段见上方注释】"""
    pass


class AgentConfigRegistry:
    """
    Agent 配置注册表，统一管理所有 Agent 的配置。

    【需要实现的方法】
    - __init__: 初始化默认配置字典
    - register(config): 注册或覆盖一个 Agent 配置
    - get(agent_name): 按名称获取配置，找不到则返回默认配置
    - load_from_yaml(path): 从 YAML 文件批量加载配置
    - list_agents(): 返回所有已注册的 Agent 名称列表
    - to_dict(): 将全部配置序列化为字典（用于调试/导出）
    """
    pass


def get_agent_config(agent_name: str) -> BaseAgentConfig:
    """
    获取指定 Agent 的配置。
    【需要实现】访问全局 AgentConfigRegistry 单例并返回对应配置。
    """
    pass
