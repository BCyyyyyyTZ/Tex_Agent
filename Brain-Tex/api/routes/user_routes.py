# ============================================================
# api/routes/user_routes.py — 用户管理 API 路由
# ============================================================
# 处理用户注册、认证、配置和历史记录：
#
# POST /users/register           — 注册新用户
# POST /users/login              — 登录（返回 API Token）
# GET  /users/profile            — 获取用户档案
# PUT  /users/profile            — 更新用户偏好设置
# GET  /users/sessions           — 历史会话列表
# GET  /users/sessions/{id}      — 获取特定会话详情
# GET  /users/kb/resources       — 用户知识库资源列表
# DELETE /users/kb/{resource_id} — 删除知识库资源
# GET  /users/health-report      — 获取健康状态报告
# ============================================================

from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(tags=["users"])


@router.post("/register")
async def register():
    """用户注册，【需要实现】"""
    pass


@router.post("/login")
async def login():
    """用户登录，返回 API Token，【需要实现】"""
    pass


@router.get("/profile")
async def get_profile():
    """获取用户档案和偏好，【需要实现】"""
    pass


@router.put("/profile")
async def update_profile():
    """更新用户配置，【需要实现】"""
    pass


@router.get("/sessions")
async def list_sessions():
    """历史会话列表，【需要实现】"""
    pass


@router.get("/health-report")
async def get_health_report():
    """获取用户健康状态报告（调用 WellbeingTracker），【需要实现】"""
    pass
