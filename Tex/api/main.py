# ============================================================
# api/main.py — FastAPI 应用主入口
# ============================================================
# NeuroTeX API 服务的启动入口，配置 FastAPI 应用实例，
# 挂载所有路由、中间件，以及生命周期事件处理。
#
# 核心内容:
# - create_app(): 工厂函数，返回配置好的 FastAPI 实例
#   - 挂载 CORS 中间件（跨域支持）
#   - 挂载认证中间件
#   - 挂载请求日志中间件
#   - 挂载限流中间件
#   - 注册所有路由（agent/document/search/user）
#   - 注册全局异常处理器（NeuroTeXError -> HTTP 响应）
#   - lifespan: 启动时初始化 DB/向量库，关闭时清理资源
#
# 启动方式：uvicorn api.main:app --host 0.0.0.0 --port 8000
# ============================================================

from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动初始化 / 关闭清理，【需要实现】"""
    # 启动时：初始化数据库、向量存储、Agent 注册表、消息总线
    yield
    # 关闭时：保存状态、关闭连接


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。
    【需要实现】挂载路由、中间件、异常处理器。
    """
    app = FastAPI(
        title="NeuroTeX API",
        description="神经网络启发的多智能体论文写作协作系统",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 挂载 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 【需要实现】挂载自定义中间件和路由
    # from api.middleware.auth_middleware import AuthMiddleware
    # from api.routes import agent_routes, document_routes, search_routes, user_routes
    # app.include_router(agent_routes.router, prefix="/api/v1/agents")
    # ...

    @app.get("/health")
    async def health_check():
        """系统健康检查端点，【需要实现具体检查逻辑】"""
        return {"status": "healthy", "version": "1.0.0"}

    return app


app = create_app()
