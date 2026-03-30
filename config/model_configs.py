# ============================================================
# config/model_configs.py
# LLM 模型能力描述与路由决策元数据
# ============================================================
# 本文件定义各 LLM 模型的"能力画像"，供 Router 模块在路由
# 决策时参考，实现"按任务复杂度和类型选择最优模型"。
#
# 【核心设计思想】
# 每个模型不只是一个名称，而是一个拥有多维度能力描述的配置对象，
# Router 可据此做出成本与质量的最优权衡。
#
# 【需要实现的内容】
#
# 1. ModelCapability — 枚举类，描述模型能力类型
#    值包括:
#    - REASONING        # 逻辑推理能力
#    - CODING           # 代码生成能力
#    - LONG_CONTEXT     # 长文本处理能力
#    - MATH             # 数学/公式推导能力
#    - CREATIVITY       # 创意写作能力
#    - INSTRUCTION      # 指令遵循能力
#    - FAST_RESPONSE    # 快速响应（适合简单任务）
#    - MULTIMODAL       # 多模态（图像理解）
#
# 2. ModelTier — 枚举类，模型等级
#    - PREMIUM   # 顶级模型（高能力高成本）
#    - STANDARD  # 标准模型（性价比高）
#    - FAST      # 快速模型（低延迟低成本）
#    - LOCAL     # 本地模型（无成本但能力弱）
#
# 3. ModelConfig — 单个模型的完整配置
#    字段:
#    - model_id: str                          # 模型唯一标识（API 调用名）
#    - display_name: str                      # 展示名称
#    - provider: str                          # 提供商（openai/anthropic/local）
#    - tier: ModelTier                        # 模型等级
#    - capabilities: list[ModelCapability]    # 能力标签列表
#    - context_window: int                    # 最大上下文窗口（tokens）
#    - max_output_tokens: int                 # 最大输出 tokens
#    - cost_per_1k_input_tokens: float        # 输入每千 token 成本（美元）
#    - cost_per_1k_output_tokens: float       # 输出每千 token 成本
#    - avg_latency_ms: int                    # 平均响应延迟（毫秒）
#    - supports_function_calling: bool        # 是否支持函数调用
#    - supports_json_mode: bool               # 是否支持 JSON 模式输出
#    - supports_streaming: bool               # 是否支持流式输出
#    - recommended_temperature: float         # 推荐温度
#    - notes: str                             # 备注（使用建议等）
#
# 4. 预置模型配置（MODEL_REGISTRY 字典）
#    包含以下模型的配置:
#    - gpt-4o                  # OpenAI 旗舰多模态模型
#    - gpt-4o-mini             # OpenAI 轻量快速模型
#    - gpt-4-turbo             # OpenAI 长上下文推理模型
#    - claude-3-5-sonnet       # Anthropic 高性能模型
#    - claude-3-haiku          # Anthropic 快速模型
#    - llama3.1:8b             # 本地 Ollama 模型（轻量）
#    - llama3.1:70b            # 本地 Ollama 模型（强力）
#
# 5. 模型选择辅助函数
#
#    get_model_for_task(task_type, budget_tier) -> ModelConfig:
#    - 根据任务类型和预算等级返回最优模型
#    - task_type: "reasoning"|"writing"|"coding"|"analysis"|"quick"
#    - budget_tier: "premium"|"standard"|"economy"
#
#    get_models_by_capability(capability) -> list[ModelConfig]:
#    - 返回具备某种能力的所有模型，按能力评分排序
#
#    estimate_cost(model_id, input_tokens, output_tokens) -> float:
#    - 估算调用某模型处理特定 token 量的费用
#
#    compare_models(model_ids) -> dict:
#    - 对比多个模型的能力雷达图数据（供 UI 展示用）
#
# 6. ModelConfig 获取函数
#    get_model_config(model_id: str) -> ModelConfig
#    - 从 MODEL_REGISTRY 获取模型配置，找不到抛 ModelNotFoundError
# ============================================================

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    """模型能力类型枚举，【实现见上方注释】"""
    pass


class ModelTier(str, Enum):
    """模型等级枚举，【实现见上方注释】"""
    pass


class ModelConfig(BaseModel):
    """单个 LLM 模型的完整能力配置，【实现字段见上方注释】"""
    pass


# 全局模型注册表
# 【需要实现】: 以 model_id 为键，填入各模型的 ModelConfig 实例
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # "gpt-4o": ModelConfig(...),
    # "gpt-4o-mini": ModelConfig(...),
    # ...
}


def get_model_config(model_id: str) -> ModelConfig:
    """
    获取指定模型的配置。
    【需要实现】从 MODEL_REGISTRY 查找，找不到抛出 ModelNotFoundError。
    """
    pass


def get_model_for_task(
    task_type: str,
    budget_tier: str = "standard",
) -> ModelConfig:
    """
    按任务类型和预算等级推荐最优模型。
    【需要实现】
    - 构建 task_type -> required_capabilities 的映射表
    - 从 MODEL_REGISTRY 中筛选满足能力要求且符合预算的模型
    - 多个候选时选择综合评分最高的
    - 无合适模型时回退到默认配置
    """
    pass


def get_models_by_capability(capability: ModelCapability) -> List[ModelConfig]:
    """
    获取具备指定能力的所有模型列表。
    【需要实现】遍历 MODEL_REGISTRY，按能力评分降序排列。
    """
    pass


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    估算调用费用（美元）。
    【需要实现】从配置读取 cost_per_1k 参数，计算总费用。
    """
    pass
