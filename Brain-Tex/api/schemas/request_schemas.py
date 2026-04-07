# ============================================================
# api/schemas/request_schemas.py — API 请求体 Schema（Pydantic）
# ============================================================
# 定义所有 API 端点的请求体数据模型，用于参数验证和文档生成。
#
# 核心 Schema:
# - ChatRequest: session_id/message/stream(bool)/branch_id
# - TaskRequest: session_id/task_description/priority/timeout
# - SearchPapersRequest: query/categories/date_range/max_results
# - SemanticSearchRequest: query/sources/top_k/filters
# - UploadDocumentRequest: doc_name/tags（文件通过 multipart 上传）
# - CreateBranchRequest: branch_name/description/from_branch_id
# - MergeBranchRequest: source_branch_id/target_branch_id/strategy
# - UpdateProfileRequest: writing_preferences/research_areas/settings
# ============================================================

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=10000)
    stream: bool = False
    branch_id: Optional[str] = None
    context_override: Optional[Dict] = None


class TaskRequest(BaseModel):
    session_id: str
    task_description: str = Field(..., min_length=10)
    priority: int = Field(default=5, ge=1, le=10)
    timeout_seconds: float = Field(default=300.0, gt=0)
    extra_context: Optional[Dict] = None


class SearchPapersRequest(BaseModel):
    query: str
    categories: List[str] = []
    date_from: Optional[str] = None     # YYYY-MM-DD
    date_to: Optional[str] = None
    max_results: int = Field(default=20, ge=1, le=100)
    semantic: bool = True               # 是否同时做语义搜索


class CreateBranchRequest(BaseModel):
    session_id: str
    branch_name: str
    description: str = ""
    from_branch_id: Optional[str] = None


class MergeBranchRequest(BaseModel):
    session_id: str
    source_branch_id: str
    target_branch_id: Optional[str] = None
    strategy: str = "selective"         # selective/append/summarize
