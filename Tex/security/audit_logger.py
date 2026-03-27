# ============================================================
# security/audit_logger.py — 安全审计日志器
# ============================================================
# 记录所有安全相关事件（登录/越权/数据访问/敏感操作），
# 为安全审计和合规性提供可追溯的日志记录。
#
# 核心内容:
# - AuditEvent: 枚举（LOGIN/LOGOUT/ACCESS/PERMISSION_DENIED/DATA_EXPORT/API_CALL）
# - AuditRecord: 审计记录（event_type/user_id/resource/ip/timestamp/outcome/details）
# - AuditLogger:
#   - log(event_type, user_id, resource, outcome, details): 记录事件
#   - query(user_id, start_time, end_time) -> list: 查询审计日志
#   - detect_suspicious(user_id) -> list: 检测可疑行为（频繁失败登录等）
#   - export_report(period) -> str: 导出审计报告
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEvent(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    PERMISSION_DENIED = "permission_denied"
    DATA_EXPORT = "data_export"
    API_CALL = "api_call"
    SUSPICIOUS = "suspicious"


@dataclass
class AuditRecord:
    event_type: AuditEvent = AuditEvent.ACCESS
    user_id: str = ""
    resource: str = ""
    ip_address: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    outcome: str = "success"
    details: Dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """
    安全审计日志器。
    【需要实现 log / query / detect_suspicious / export_report】
    持久化到数据库，支持查询和可疑行为检测。
    """

    def log(
        self,
        event_type: AuditEvent,
        user_id: str,
        resource: str = "",
        outcome: str = "success",
        details: Optional[Dict] = None,
    ) -> None:
        """记录审计事件，【需要实现】"""
        pass

    def query(
        self,
        user_id: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditRecord]:
        """查询审计日志，【需要实现】"""
        pass

    def detect_suspicious(self, user_id: str) -> List[str]:
        """检测可疑行为，【需要实现】"""
        pass
