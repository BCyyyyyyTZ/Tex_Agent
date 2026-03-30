# ============================================================
# monitoring/dashboard.py — 监控仪表盘数据聚合
# ============================================================
# 聚合 MetricsCollector + PerformanceTracker + AgentMonitor 的数据，
# 提供给前端仪表盘（Grafana 兼容）或内置 API 端点使用。
#
# 核心内容:
# - DashboardData: 仪表盘快照数据（系统概览/Agent状态/性能/费用）
# - MonitoringDashboard:
#   - get_snapshot() -> DashboardData: 获取当前系统全景快照
#   - get_realtime_metrics() -> dict: 实时指标（适合 WebSocket 推送）
#   - get_historical_metrics(metric, start, end) -> list: 历史趋势数据
#   - generate_daily_report() -> str: 生成每日运行报告（Markdown）
#   - export_grafana_dashboard() -> dict: 导出 Grafana Dashboard JSON 配置
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DashboardData:
    snapshot_time: datetime = field(default_factory=datetime.now)
    # 系统概览
    total_sessions_today: int = 0
    total_tasks_today: int = 0
    total_tokens_today: int = 0
    total_cost_today_usd: float = 0.0
    # Agent 状态
    agent_health_summary: Dict[str, int] = field(default_factory=dict)  # {status: count}
    # 性能
    avg_response_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    # 路由分布
    agent_type_distribution: Dict[str, int] = field(default_factory=dict)


class MonitoringDashboard:
    """
    监控仪表盘数据聚合器。
    【需要实现】
    - get_snapshot(): 聚合三个监控组件的当前状态
    - get_realtime_metrics(): 适合 WebSocket 1秒推送的轻量数据
    - get_historical_metrics(metric, start, end): 历史数据查询（时序DB）
    - generate_daily_report(): 调用 LLM 生成运营洞察报告
    - export_grafana_dashboard(): 返回 Grafana JSON 配置（可直接导入）
    """

    def __init__(self) -> None:
        self._metrics_collector: Optional[Any] = None
        self._performance_tracker: Optional[Any] = None
        self._agent_monitor: Optional[Any] = None

    def get_snapshot(self) -> DashboardData:
        """获取系统全景快照，【需要实现】"""
        pass

    def get_realtime_metrics(self) -> Dict[str, Any]:
        """获取实时轻量指标（WebSocket 推送用），【需要实现】"""
        pass

    def get_historical_metrics(
        self,
        metric_name: str,
        start: datetime,
        end: datetime,
        granularity: str = "1m",
    ) -> List[Dict[str, Any]]:
        """查询历史指标趋势，【需要实现】"""
        pass

    async def generate_daily_report(self) -> str:
        """生成每日运营报告（Markdown），【需要实现】"""
        pass

    def export_grafana_dashboard(self) -> Dict[str, Any]:
        """导出 Grafana Dashboard JSON 配置，【需要实现】"""
        pass
