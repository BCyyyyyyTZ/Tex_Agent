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

def _resolve_parsed_doc_dir(raw: str) -> str:
    """解析结果输出根目录：空则默认 storage/documents；相对路径相对于项目根。"""
    text = (raw or "").strip()
    if not text:
        text = "storage/documents"
    p = Path(text)
    if p.is_absolute():
        return str(p.resolve())
    return str((_project_root / p).resolve())


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


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
    llm_max_tokens: int = 8192
    llm_timeout: int = 240
    llm_max_retries: int = 3

    # ---- 日志配置 ----
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # ---- ArXiv 工具配置 ----
    arxiv_max_results: int = 5
    # 默认仅输出标题+链接+摘要（省 token、减轻下游节点负担）；ARXIV_OUTPUT_FULL=1 恢复完整格式
    arxiv_output_full: bool = field(
        default_factory=lambda: os.getenv("ARXIV_OUTPUT_FULL", "").strip().lower()
        in ("1", "true", "yes", "on")
    )
    arxiv_abstract_max_chars: int = field(
        default_factory=lambda: int(os.getenv("ARXIV_ABSTRACT_MAX_CHARS", "360"))
    )

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

    # ---- 文档解析（Docling）导出路径 ----
    parsed_doc_dir: str = field(
        default_factory=lambda: _resolve_parsed_doc_dir(os.getenv("PARSED_DOC_DIR", ""))
    )

    # ---- Docling 大 PDF 旁路（页数阈值与分块参数，见 rag/document_parse.py）----
    # PAGE_THRESHOLD：页数 >= 该值走旁路；目前仅统计 PDF。
    docling_page_threshold: int = field(
        default_factory=lambda: max(1, _env_int("PAGE_THRESHOLD", 30))
    )
    # CHUNK_PAGES / CHUNK_OVERLAP：预留给分块拼接旁路，当前解析逻辑仅记录日志。
    docling_chunk_pages: int = field(
        default_factory=lambda: max(1, _env_int("CHUNK_PAGES", 25))
    )
    docling_chunk_overlap: int = field(
        default_factory=lambda: max(0, _env_int("CHUNK_OVERLAP", 1))
    )
    chunk_parsed_doc_dir: str = field(
        default_factory=lambda: _resolve_parsed_doc_dir(
            os.getenv("CHUNK_PARSED_DOC_DIR", "doc/chunk_parsed_doc")
        )
    )
    docling_merge_similarity_threshold: float = 0.85  # 用于文本去重

    # DOCLING_PDF_DEVICE：PDF 管线加速器。auto=有 CUDA 则用 GPU 线程化管线，否则默认 CPU。
    # 取值：auto | cpu | cuda（大小写不敏感）。
    docling_pdf_device: str = field(
        default_factory=lambda: (os.getenv("DOCLING_PDF_DEVICE", "auto") or "auto").strip().lower()
    )

    # ---- LaTeX 子系统（阶段 3+）----
    latex_chktex_timeout_sec: int = field(
        default_factory=lambda: max(1, _env_int("LATEX_CHKTEX_TIMEOUT_SEC", 30))
    )
    latex_latexmk_fast_timeout_sec: int = field(
        default_factory=lambda: max(1, _env_int("LATEX_LATEXMK_FAST_TIMEOUT_SEC", 120))
    )
    latex_latexmk_full_timeout_sec: int = field(
        default_factory=lambda: max(1, _env_int("LATEX_LATEXMK_FULL_TIMEOUT_SEC", 600))
    )
    latex_llm_max_issues_per_run: int = field(
        default_factory=lambda: max(1, _env_int("LATEX_LLM_MAX_ISSUES_PER_RUN", 5))
    )
    latex_slice_context_lines: int = field(
        default_factory=lambda: max(0, _env_int("LATEX_SLICE_CONTEXT_LINES", 10))
    )

    # ---- LaTeX 监视与润色（阶段 8+）----
    latex_watch_diagnose_debounce_ms: int = field(
        default_factory=lambda: max(100, _env_int("LATEX_WATCH_DIAGNOSE_DEBOUNCE_MS", 500))
    )
    latex_watch_idle_polish_sec: int = field(
        default_factory=lambda: max(1, _env_int("LATEX_WATCH_IDLE_POLISH_SEC", 2))
    )
    latex_watch_enable_latexmk: bool = field(
        default_factory=lambda: _env_bool("LATEX_WATCH_ENABLE_LATEXMK", False)
    )
    latex_ghost_quiet_sec: float = field(
        default_factory=lambda: max(0.1, _env_float("LATEX_GHOST_QUIET_SEC", 1.0))
    )
    latex_ghost_auto_polish: bool = field(
        default_factory=lambda: _env_bool("LATEX_GHOST_AUTO_POLISH", False)
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
