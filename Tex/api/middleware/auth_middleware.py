# ============================================================
# api/middleware/auth_middleware.py — 认证中间件
# ============================================================
# FastAPI 中间件，拦截所有请求并验证认证信息。
# 支持 Bearer Token 和 X-API-Key 两种认证头格式。
# 白名单路由（/health, /docs, /openapi.json）跳过认证。
#
# 核心逻辑:
# - 从 Authorization 或 X-API-Key 头提取令牌
# - 调用 AuthManager.verify_token() 验证
# - 将 user_id 和 scopes 注入 request.state
# - 认证失败返回 401 JSON 响应
# ============================================================

from __future__ import annotations
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

WHITELIST_PATHS = ["/health", "/docs", "/openapi.json", "/api/v1/users/login",
                   "/api/v1/users/register"]


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件。
    【需要实现 dispatch 方法】
    验证令牌，注入用户信息到 request.state.user。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """拦截请求进行认证验证，【需要实现】"""
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)
        # 【需要实现验证逻辑】
        return await call_next(request)
