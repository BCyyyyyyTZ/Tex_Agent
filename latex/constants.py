"""
LaTeX 子系统常量：metadata 键名、枚举值（阶段 0 冻结）。
"""
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueSource(str, Enum):
    CHKTEX = "chktex"
    LATEXMK = "latexmk"
    PARSER = "parser"
    LLM_FIX = "llm_fix"
    LLM_POLISH = "llm_polish"


# WorkflowState.metadata 约定键（只增不改）
METADATA_LATEX_PROJECT = "__latex_project__"
METADATA_LATEX_DIAGNOSTICS = "__latex_diagnostics__"
METADATA_LATEX_DIRTY = "__latex_dirty__"
METADATA_LATEX_SUGGESTIONS = "__latex_suggestions__"
METADATA_LATEX_LAST_GOOD_BUILD = "__latex_last_good_build__"

DEFAULT_MAX_SCAN_DEPTH = 8
IGNORED_DIR_NAMES = frozenset({".git", "__pycache__", "node_modules", "build", "out", ".venv", "venv"})
