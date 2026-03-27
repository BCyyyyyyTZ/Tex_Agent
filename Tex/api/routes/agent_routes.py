# ============================================================
# api/routes/agent_routes.py — Agent 相关 API 路由
# ============================================================
# 提供与 Agent 交互的 RESTful API 端点：
#
# POST /agents/chat              — 发送消息（支持流式 SSE 响应）
# POST /agents/task              — 提交复杂任务（异步执行）
# GET  /agents/task/{task_id}    — 查询任务执行状态
# GET  /agents/list              — 列出所有可用 Agent
# POST /agents/branch/create     — 创建新的对话分支
# GET  /agents/branch/list       — 列出当前会话的所有分支
# POST /agents/branch/checkout   — 切换对话分支
# POST /agents/branch/merge      — 合并对话分支
# DELETE /agents/session         — 结束当前会话
# ============================================================

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["agents"])


@router.post("/chat")
async def chat(
    # request: ChatRequest,
    # auth: AuthToken = Depends(get_current_user)
):
    """
    发送消息给 Agent（支持 SSE 流式响应）。
    【需要实现】
    - 从请求提取 session_id / message / stream 参数
    - 调用 AdaptiveRouter 路由到合适的 Agent
    - 如 stream=True，返回 StreamingResponse（SSE 格式）
    - 如 stream=False，等待完成后返回 JSON
    """
    pass


@router.post("/task")
async def submit_task():
    """
    提交复杂任务（异步，返回 task_id）。
    【需要实现】
    - 创建任务记录并入库
    - 调用 PlannerAgent 分解任务
    - 后台异步执行
    - 返回 task_id 供后续轮询
    """
    pass


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务执行状态，【需要实现】"""
    pass


@router.get("/list")
async def list_agents():
    """列出所有可用 Agent，【需要实现】"""
    pass


@router.post("/branch/create")
async def create_branch():
    """创建对话分支，【需要实现】"""
    pass


@router.get("/branch/list")
async def list_branches():
    """列出对话分支，【需要实现】"""
    pass


@router.post("/branch/checkout")
async def checkout_branch():
    """切换对话分支，【需要实现】"""
    pass


@router.post("/branch/merge")
async def merge_branches():
    """合并对话分支，【需要实现】"""
    pass
