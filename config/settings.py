"""
全局配置模块。
所有可调参数集中于此，修改此文件或对应的 .env 文件即可完成配置，无需改动业务代码。
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env 文件
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")

def _resolve_rag_persist_dir(raw: str) -> str:
    """将 RAG 持久化目录解析为绝对路径：相对路径相对于项目根（config 上一级）。"""
    text = (raw or "").strip()
    if not text:
        return ""
    p = Path(text)
    if p.is_absolute():
        return str(p.resolve())
    return str((_project_root / p).resolve())


@dataclass
class Settings:
    """
    TeX_Agent 全局配置类。

    优先级：.env 文件 > 环境变量 > 默认值。
    所有字段均可通过对应的环境变量覆盖。
    """

    # ---- LLM 配置 ----
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini")
    )
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_timeout: int = 240
    llm_max_retries: int = 3

    # ---- 日志配置 ----
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # ---- ArXiv 工具配置 ----
    arxiv_max_results: int = 3

    # ---- RAG 配置 ----
    # rag_chunk_size:     文档分块大小（字符数），较大值保留更多上下文，但向量质量下降
    # rag_chunk_overlap:  相邻块重叠字符数，保证块边界处语义连续
    # rag_top_k:          每次检索返回的最大片段数，注入 Prompt 的片段越多 Token 消耗越大
    # rag_persist_directory: 向量库持久化路径，空字符串表示使用内存模式（进程退出后清空）
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5
    rag_persist_directory: str = field(
        default_factory=lambda: _resolve_rag_persist_dir(os.getenv("RAG_PERSIST_DIR", ""))
    )

    def __repr__(self) -> str:
        """遮蔽 API Key，防止其通过日志/调试输出泄露。"""
        masked_key = (
            f"{self.openai_api_key[:6]}***"
            if len(self.openai_api_key) > 6
            else ("***" if self.openai_api_key else "<未配置>")
        )
        return (
            f"Settings("
            f"api_key={masked_key}, "
            f"base_url={self.openai_base_url!r}, "
            f"model={self.llm_model!r}, "
            f"log_level={self.log_level!r}"
            f")"
        )


# 全局单例，其他模块通过 `from config.settings import settings` 使用
settings = Settings()
