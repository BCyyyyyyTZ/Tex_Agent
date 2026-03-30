# ============================================================
# api/middleware/rate_limiter.py — API 限流中间件
# ============================================================
# 防止 API 滥用，按用户/IP 限制请求频率。
# 使用滑动窗口算法实现，支持不同路由设置不同限速策略。
#
# 默认策略:
# - 普通用户: 60 次/分钟
# - 高级用户: 300 次/分钟
# - 未认证: 10 次/分钟
# - /agents/chat: 额外限制 20 次/分钟（LLM 调用较贵）
#
# 核心逻辑（使用 Redis 或内存计数器实现滑动窗口）:
# - increment_counter(key) -> int: 增加计数
# - check_limit(key, limit) -> bool: 检查是否超限
# - 超限返回 429 Too Many Requests，带 Retry-After 头
# ============================================================

from __future__ import annotations
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    API 限流中间件（滑动窗口算法）。
    【需要实现 dispatch / _get_limit / _check_and_increment】
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """限流检查，【需要实现】"""
        return await call_next(request)

    def _get_limit_for_user(self, user_role: str, path: str) -> int:
        """获取该用户/路由的限速配置，【需要实现】"""
        pass

    async def _check_and_increment(
        self, key: str, limit: int, window_seconds: int = 60
    ) -> tuple:
        """检查并增加计数，【需要实现】返回 (allowed, remaining, reset_at)"""
        pass
