# ============================================================
# api/routes/search_routes.py — 搜索 API 路由
# ============================================================
# 提供文献搜索和知识库检索接口：
#
# POST /search/papers            — arXiv/Scholar 论文搜索
# POST /search/semantic          — 语义搜索（本地知识库）
# GET  /search/suggest           — 搜索建议（自动补全）
# POST /search/kb/user           — 用户私有知识库搜索
# ============================================================

from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.post("/papers")
async def search_papers():
    """论文搜索（调用 LiteratureAgent），【需要实现】"""
    pass


@router.post("/semantic")
async def semantic_search():
    """语义搜索（调用 SemanticSearchTool），【需要实现】"""
    pass


@router.get("/suggest")
async def get_suggestions(query: str):
    """搜索建议，【需要实现】"""
    pass


@router.post("/kb/user")
async def search_user_kb():
    """用户知识库搜索，【需要实现】"""
    pass
