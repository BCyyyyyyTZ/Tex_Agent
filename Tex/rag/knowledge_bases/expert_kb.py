# ============================================================
# rag/knowledge_bases/expert_kb.py
# ExpertKnowledgeBase —— 专家经验知识库
# ============================================================
# ExpertKnowledgeBase 存储领域专家的经验性知识，
# 包括：最佳实践、常见陷阱、写作技巧、评审标准等。
# 这类知识通常不在学术论文中直接出现，需要手工整理或从
# 大量实践经验中提炼。
#
# 【知识来源】
# 1. 预置的写作指南（LaTeX 技巧、学术写作规范）
# 2. 顶级会议（NeurIPS/ICML/CVPR 等）的 reviewer guideline
# 3. 领域专家 blog 和 tutorial 文章
# 4. 用户上传的私人笔记和经验总结
#
# 【需要实现的内容】
#
# 1. ExpertKnowledge — 专家知识条目
#    字段:
#    - knowledge_id: str
#    - category: str            # writing/review/methodology/tools
#    - domain: str              # 适用的研究领域
#    - title: str               # 知识条目标题
#    - content: str             # 知识内容（可以是 Markdown 格式）
#    - source: str              # 来源（URL/书名/专家名）
#    - reliability: float       # 可靠性评分（0-1）
#    - tags: list[str]
#
# 2. ExpertKnowledgeBase 类
#
#    核心方法:
#
#    async add_knowledge(knowledge: ExpertKnowledge) -> str
#    async search(query, category=None, domain=None, k=5) -> list[dict]
#    async get_writing_tips(section_type: str) -> list[str]
#    async get_review_criteria(venue: str) -> dict
#    async load_builtin_knowledge() -> None:
#    - 加载预置的写作指南、LaTeX 技巧等内容
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExpertKnowledge:
    """专家知识条目，【实现字段见上方注释】"""
    knowledge_id: str = ""
    category: str = "writing"
    domain: str = "general"
    title: str = ""
    content: str = ""
    source: str = ""
    reliability: float = 0.8
    tags: List[str] = field(default_factory=list)


class ExpertKnowledgeBase:
    """
    专家经验知识库。
    存储写作技巧、评审标准等经验性知识，弥补论文检索的盲区。
    【完整实现规范见上方注释】
    """

    def __init__(self) -> None:
        self._vector_store: Optional[Any] = None
        self._knowledge_items: Dict[str, ExpertKnowledge] = {}

    async def add_knowledge(self, knowledge: ExpertKnowledge) -> str:
        """添加专家知识条目，【需要实现】"""
        pass

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        domain: Optional[str] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索专家知识，【需要实现】"""
        pass

    async def get_writing_tips(self, section_type: str) -> List[str]:
        """获取特定章节的写作技巧，【需要实现】"""
        pass

    async def get_review_criteria(self, venue: str) -> Dict[str, Any]:
        """获取会议评审标准，【需要实现】"""
        pass

    async def load_builtin_knowledge(self) -> None:
        """加载预置专家知识，【需要实现】"""
        pass
