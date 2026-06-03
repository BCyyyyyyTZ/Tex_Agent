"""
LaTeX 目录监视事件与快照模型（阶段 8）。
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from latex.models import DiagnosticIssue, Suggestion


class WatchSnapshot(BaseModel):
    """监视服务返回的当前状态快照。"""
    watch_id: str
    root: str
    main_tex: Optional[str] = None
    status: str = "running"  # running, stopped, error
    project_version: int = 0
    issues: List[DiagnosticIssue] = Field(default_factory=list)
    suggestions: List[Suggestion] = Field(default_factory=list)
    polish_suggestions: List[Suggestion] = Field(default_factory=list)
    # 当前 error 集合的稳定签名；Ghost UI 可用来判断是否需要重绘卡片。
    error_signature: str = ""
    # 最近一次诊断是否引入了新的 error 集合变化。
    error_changed: bool = False
    last_event_at: float = 0.0
    error_message: str = ""


class WatchEvent(BaseModel):
    """统一事件模型。"""
    event_type: str  # diagnostics_updated, suggestions_updated, polish_suggestions_updated, error
    watch_id: str
    project_version: int
    timestamp: float
    payload: dict = Field(default_factory=dict)
