# ============================================================
# skills/academic/citation_skill.py — 引用管理技能
# ============================================================
# 处理论文中的引用相关任务：
# - 智能推荐：根据上下文推荐合适的引用文献
# - 格式转换：arXiv/DOI → BibTeX 条目
# - 一致性检查：确保文中所有 \cite 都有对应的 bib 条目
# - 引用修复：为缺少引用支撑的论点自动补充推荐文献
#
# 输入: LaTeX 文本 + 现有 BibTeX 文件
# 输出: 建议新增的引用 + 修复后的 LaTeX 文本
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CitationOutput:
    suggested_citations: List[Dict] = field(default_factory=list)  # [{context, paper_info, bibtex}]
    missing_refs: List[str] = field(default_factory=list)           # 文中引用但 bib 中缺少的键
    unused_refs: List[str] = field(default_factory=list)            # bib 中有但文中未引用的键
    updated_bibtex: str = ""
    fixed_latex: str = ""


class CitationSkill:
    """
    引用管理技能。
    【需要实现】
    - execute(latex_text, bibtex_content) -> CitationOutput
    - _check_consistency(): 检查 cite/bib 一致性
    - _recommend_citations(): 根据上下文推荐文献（调用 PaperKnowledgeBase）
    - _fetch_bibtex(paper_id): 从 arXiv/DOI 获取 BibTeX
    """
    async def execute(
        self, latex_text: str, bibtex_content: str = ""
    ) -> CitationOutput:
        """执行引用管理，【需要实现】"""
        pass
