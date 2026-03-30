# ============================================================
# skills/academic/literature_review_skill.py — 文献综述技能
# ============================================================
# 封装完整的文献综述生成流程：
# 1. 调用 ArXivRetriever + PaperKnowledgeBase 检索相关文献
# 2. 使用 TopicModelingTool 分析研究主题分布
# 3. 调用 LLM 撰写结构化文献综述段落（包含引用）
# 4. 生成参考文献 BibTeX 条目
#
# 输入: 研究主题 + 关键词 + 时间范围 + 目标字数
# 输出: 综述正文（LaTeX格式）+ BibTeX 引用列表
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class LiteratureReviewOutput:
    review_text_latex: str = ""       # 综述正文（LaTeX 格式，含 \cite{}）
    bibtex_entries: List[str] = field(default_factory=list)
    paper_count: int = 0
    topics_covered: List[str] = field(default_factory=list)
    summary: str = ""


class LiteratureReviewSkill:
    """
    文献综述生成技能。
    【需要实现】
    - execute(topic, keywords, max_papers, word_count) -> LiteratureReviewOutput
    - _retrieve_papers(): 检索论文（arXiv + 本地知识库）
    - _analyze_topics(): 提炼主题脉络
    - _write_review(): 调用 LLM 撰写综述
    - _format_bibtex(): 格式化参考文献
    """
    async def execute(
        self,
        topic: str,
        keywords: List[str],
        max_papers: int = 30,
        word_count: int = 800,
    ) -> LiteratureReviewOutput:
        """执行文献综述生成，【需要实现】"""
        pass
