# ============================================================
# rag/knowledge_bases/user_kb.py
# UserKnowledgeBase —— 用户自定义资源知识库
# ============================================================
# UserKnowledgeBase 允许用户上传自己的文档、笔记和参考资料，
# 构建个性化的私有知识库，供 Agent 在任务中引用。
# 每个用户有独立的命名空间，保护数据隐私。
#
# 【需要实现的内容】
#
# 1. UserResource — 用户资源条目
#    字段:
#    - resource_id: str
#    - user_id: str
#    - file_path: str           # 原始文件路径
#    - resource_type: str       # paper/note/dataset/template/reference
#    - title: str               # 用户自定义标题
#    - description: str         # 用户描述
#    - tags: list[str]
#    - created_at: datetime
#    - doc_ids: list[str]       # 对应的向量存储文档 ID 列表
#
# 2. UserKnowledgeBase 类
#
#    核心方法:
#
#    async upload(
#        user_id: str,
#        file_path: str,
#        title: str = "",
#        description: str = "",
#        tags: list = []
#    ) -> UserResource:
#    - 上传并索引用户文档
#    - 使用 LocalRetriever 进行文档处理和索引
#    - 以 user_id 为命名空间隔离不同用户数据
#
#    async search(
#        user_id: str, query: str, k: int = 5
#    ) -> list[dict]:
#    - 在用户私有知识库中检索
#    - 严格按 user_id 过滤，防止跨用户数据泄露
#
#    async delete_resource(
#        user_id: str, resource_id: str
#    ) -> None:
#    - 删除用户资源及其向量索引
#
#    list_resources(user_id: str) -> list[UserResource]:
#    - 列出用户的所有资源
#
#    get_user_collection_name(user_id: str) -> str:
#    - 返回该用户的向量存储集合名（隔离命名空间）
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class UserResource:
    """用户资源条目，【实现字段见上方注释】"""
    resource_id: str = ""
    user_id: str = ""
    file_path: str = ""
    resource_type: str = "paper"
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    doc_ids: List[str] = field(default_factory=list)


class UserKnowledgeBase:
    """
    用户自定义私有知识库。
    每个用户独立命名空间，支持上传、检索和管理私人资源。
    【完整实现规范见上方注释】
    """

    def __init__(self) -> None:
        self._vector_store: Optional[Any] = None
        self._local_retriever: Optional[Any] = None
        self._resources: Dict[str, List[UserResource]] = {}  # user_id -> [resources]

    async def upload(
        self,
        user_id: str,
        file_path: str,
        title: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> UserResource:
        """上传并索引用户文档，【需要实现】"""
        pass

    async def search(
        self, user_id: str, query: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """用户私有知识库检索，【需要实现】"""
        pass

    async def delete_resource(
        self, user_id: str, resource_id: str
    ) -> None:
        """删除用户资源，【需要实现】"""
        pass

    def list_resources(self, user_id: str) -> List[UserResource]:
        """列出用户资源，【需要实现】"""
        pass

    def get_user_collection_name(self, user_id: str) -> str:
        """返回用户的向量存储集合名，【需要实现】"""
        return f"user_{user_id}_kb"
