# ============================================================
# api/schemas/response_schemas.py — API 响应体 Schema（Pydantic）
# ============================================================
# 定义所有 API 端点的响应数据模型，确保统一的 API 响应格式。
#
# 统一响应格式: {"code": 0, "message": "ok", "data": {...}}
#
# 核心 Schema:
# - BaseResponse: code/message/data 基础响应
# - ChatResponse: agent_message/session_id/branch_id/token_usage/latency_ms
# - TaskResponse: task_id/status/result/artifacts/progress
# - AgentListResponse: agents[{agent_id/type/status/capabilities}]
# - BranchListResponse: branches[{branch_id/name/message_count/created_at}]
# - SearchResponse: results[{paper_info/score}]/total_count
# - DocumentParseResponse: sections/structure/issues/metadata
# ============================================================

from __future__ import annotations
from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class BaseResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[Any] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "ok") -> "BaseResponse":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str) -> "BaseResponse":
        return cls(code=code, message=message, data=None)


class ChatResponse(BaseModel):
    agent_message: str = ""
    session_id: str = ""
    branch_id: str = ""
    agent_type: str = ""
    token_usage: Dict[str, int] = {}
    latency_ms: int = 0
    artifacts: List[Dict[str, Any]] = []


class TaskResponse(BaseModel):
    task_id: str = ""
    status: str = "pending"     # pending/running/completed/failed
    result: Optional[str] = None
    artifacts: List[Dict[str, Any]] = []
    progress: float = 0.0       # 0-1
    error_message: str = ""
