# ============================================================
# config/settings.py
# 全局系统配置（基于 pydantic-settings）
# ============================================================
# 本文件定义整个 NeuroTeX 系统的全局配置类 Settings。
# 所有配置项均从环境变量或 .env 文件中自动加载。
#
# 【需要实现的内容】
#
# 1. Settings 类（继承 pydantic_settings.BaseSettings）
#    - 定义所有配置字段，附带类型注解和默认值
#    - 配置项分组：LLM配置、向量库配置、API配置、安全配置等
#    - 使用 @validator 对关键字段做校验（如 API Key 格式检查）
#    - 使用 @computed_field 提供派生配置项（如完整数据库 URL）
#
# 2. get_settings() 函数
#    - 使用 @lru_cache 实现单例模式（避免重复读取 .env）
#    - 返回全局唯一 Settings 实例
#
# 3. 各配置分组的嵌套 BaseModel
#    - LLMSettings: 模型名称、API Key、BaseURL、超时、重试次数
#    - VectorStoreSettings: 存储类型、本地路径、集合名、嵌入维度
#    - MemorySettings: 短期记忆窗口大小、最大分支数、快照间隔
#    - RAGSettings: chunk大小、重叠长度、最大检索数、相似度阈值
#    - RouterSettings: 路由策略、复杂度阈值、默认回退模型
#    - SecuritySettings: JWT 密钥、令牌过期时间、允许的 CORS 域
#    - MonitoringSettings: 是否启用指标、采集间隔、导出端口
#
# 【设计注意事项】
# - 敏感配置（API Key 等）使用 SecretStr 类型防止日志泄露
# - 路径类配置统一使用 pathlib.Path 类型
# - 环境变量前缀统一为 "NEUROTEX_"（可选，便于区分）
# - 支持 model_config = SettingsConfigDict(env_file=".env")
# ============================================================

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM 模型相关配置"""
    # 【需要实现】
    # - openai_api_key: SecretStr
    # - openai_base_url: str
    # - anthropic_api_key: SecretStr
    # - default_model: str  # 主力模型，如 gpt-4o
    # - fast_model: str     # 轻量模型，如 gpt-4o-mini
    # - embedding_model: str
    # - max_tokens: int
    # - temperature: float  # 默认温度 0.7
    # - request_timeout: int
    # - max_retries: int
    # - enable_local_llm: bool
    # - local_llm_base_url: str
    # - local_llm_model: str
    pass


class VectorStoreSettings(BaseSettings):
    """向量数据库配置"""
    # 【需要实现】
    # - store_type: Literal["chroma", "faiss", "weaviate"]
    # - chroma_persist_dir: Path
    # - collection_name: str
    # - embedding_dimension: int  # 文本嵌入向量维度
    # - similarity_metric: Literal["cosine", "l2", "ip"]
    pass


class MemorySettings(BaseSettings):
    """记忆系统配置"""
    # 【需要实现】
    # - short_term_window_size: int  # 短期记忆保留的最近 N 条消息
    # - max_branches: int            # 最大上下文分支数
    # - snapshot_interval: int       # 自动快照间隔（对话轮次数）
    # - max_branch_depth: int        # 分支最大深度
    # - enable_auto_summarize: bool  # 超过窗口时是否自动摘要
    # - long_term_top_k: int         # 长期记忆检索 top-k
    pass


class RAGSettings(BaseSettings):
    """RAG 检索配置"""
    # 【需要实现】
    # - chunk_size: int        # 文档切块大小（字符数）
    # - chunk_overlap: int     # 相邻块重叠大小
    # - max_retrieval_k: int   # 每次检索返回最大 k 条
    # - similarity_threshold: float  # 相似度过滤阈值
    # - retrieval_strategy: Literal["similarity", "mmr", "hybrid"]
    # - rerank_enabled: bool   # 是否启用重排序
    pass


class RouterSettings(BaseSettings):
    """路由模块配置"""
    # 【需要实现】
    # - routing_strategy: Literal["rule_based", "ml_based", "adaptive"]
    # - complexity_threshold_simple: float   # 判定为简单任务的阈值
    # - complexity_threshold_complex: float  # 判定为复杂任务的阈值
    # - fallback_model: str    # 路由失败时的回退模型
    # - enable_cost_optimization: bool  # 是否启用成本优化路由
    # - max_route_retries: int
    pass


class SecuritySettings(BaseSettings):
    """安全配置"""
    # 【需要实现】
    # - secret_key: SecretStr         # JWT 签名密钥
    # - algorithm: str                # JWT 算法，如 "HS256"
    # - access_token_expire_minutes: int
    # - refresh_token_expire_days: int
    # - allowed_cors_origins: list[str]
    # - enable_rate_limiting: bool
    # - rate_limit_requests_per_minute: int
    # - enable_input_sanitization: bool  # 是否过滤用户输入中的危险内容
    pass


class Settings(BaseSettings):
    """
    NeuroTeX 全局配置根类。
    所有子模块配置通过嵌套方式组合到此处。

    【需要实现的完整字段列表】
    基础配置:
    - app_name: str = "NeuroTeX"
    - app_version: str = "0.1.0"
    - debug: bool = False
    - data_dir: Path
    - log_level: str
    - log_file: Path

    嵌套配置（将上方各 Settings 类作为字段）:
    - llm: LLMSettings
    - vector_store: VectorStoreSettings
    - memory: MemorySettings
    - rag: RAGSettings
    - router: RouterSettings
    - security: SecuritySettings

    API 服务配置:
    - api_host: str = "0.0.0.0"
    - api_port: int = 8000

    功能开关:
    - enable_emotion_detection: bool = True
    - enable_image_generation: bool = True
    - enable_companion_mode: bool = True
    - max_concurrent_agents: int = 5
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 【在此处添加所有字段定义】


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取全局配置单例。
    使用 lru_cache 确保整个进程中只加载一次配置。

    【需要实现】
    - 实例化 Settings()
    - 捕获 ValidationError，打印友好的错误提示
    - 在 debug 模式下打印所有配置项（注意脱敏处理）
    - 返回配置实例
    """
    pass
