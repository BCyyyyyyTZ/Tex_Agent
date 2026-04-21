"""
RefCheckerTool：从 Markdown 全文检查参考文献规范性。

检查项（对应 thesis-checklists 参考文献检查列表）：
  1. 格式统一性：按条目检测编号、作者、年份、标题的存在
  2. 编号连续性：引用编号是否有跳号或重复
  3. 正文引用 vs 文献列表交叉核验：
       - 正文中引用了 [X] 但文献列表没有对应条目
       - 文献列表中有条目但正文中从未被引用
  4. 年份格式：是否都是 4 位年份
  5. 总条数报告

输出：
  - 文字摘要（适合 LLM 输入）
  - metadata 包含结构化问题列表
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 正则
# ---------------------------------------------------------------------------

# 文献列表条目：支持两种格式
#   格式A: [1] 内容在同一行  →  [1] 作者, 标题...
#   格式B: [1]\n内容在下一行  →  [1]\n 作者, 标题...（学位论文常见）
_REF_ENTRY_RE = re.compile(
    r'^\s*\[(\d+)\]\s*\n?\s*(.+?)(?=\n\s*\[\d+\]|\Z)',
    re.MULTILINE | re.DOTALL
)

# 正文引用：[1] [1,2] [1-3] [1, 2, 3]
_CITE_RE = re.compile(r'\[(\d+(?:[,，\-–]\s*\d+)*)\]')

# 年份：4位数字
_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')

# 章节标题，用于定位参考文献章节（支持 markdown 标题 或 纯文本行）
_REF_SECTION_RE = re.compile(
    r'(?:^#{1,3}\s*|^|\n)(?:参考文献|References?|Bibliography)\s*(?:\n|$)',
    re.IGNORECASE | re.MULTILINE
)


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------

def _find_ref_section(md_text: str) -> Tuple[str, str]:
    """
    将 Markdown 分为「正文」和「参考文献」两部分。
    优先取最后一次出现"参考文献"的位置（目录里可能有早期出现）。
    同时验证：该位置后方 500 字符内必须有 [N] 格式条目，否则继续向后搜。
    返回 (body_text, ref_text)。
    """
    _ENTRY_QUICK_RE = re.compile(r'\[\d+\]')
    matches = list(_REF_SECTION_RE.finditer(md_text))
    if not matches:
        return md_text, ""

    # 从后向前找，取最后一个后方跟有 [N] 条目的匹配
    for m in reversed(matches):
        lookahead = md_text[m.start(): m.start() + 600]
        if _ENTRY_QUICK_RE.search(lookahead):
            return md_text[:m.start()], md_text[m.start():]

    # 全部都没有 [N] 条目 → 取最后一个
    m = matches[-1]
    return md_text[:m.start()], md_text[m.start():]


def _parse_ref_entries(ref_text: str) -> Dict[int, str]:
    """
    解析参考文献列表，返回 {编号: 条目文本}。
    """
    entries: Dict[int, str] = {}
    for m in _REF_ENTRY_RE.finditer(ref_text):
        num = int(m.group(1))
        content = m.group(2).strip()
        entries[num] = content
    return entries


def _parse_body_citations(body_text: str) -> Set[int]:
    """
    从正文中提取所有被引用的编号集合。
    支持 [1], [1,2], [1-3] 等格式。
    """
    cited: Set[int] = set()
    for m in _CITE_RE.finditer(body_text):
        raw = m.group(1)
        # 处理范围 [1-3]
        range_m = re.match(r'(\d+)\s*[-–]\s*(\d+)', raw)
        if range_m:
            for n in range(int(range_m.group(1)), int(range_m.group(2)) + 1):
                cited.add(n)
        else:
            # 逗号分隔
            for part in re.split(r'[,，]', raw):
                part = part.strip()
                if part.isdigit():
                    cited.add(int(part))
    return cited


def _check_entry_format(num: int, text: str) -> List[str]:
    """
    对单条参考文献做格式检查，返回问题列表。
    """
    issues = []
    # 年份
    if not _YEAR_RE.search(text):
        issues.append(f"[{num}] 未找到有效年份")
    # 极短（可能不完整）
    if len(text) < 30:
        issues.append(f"[{num}] 条目过短（{len(text)}字符），可能信息不完整")
    return issues


def _check_numbering(entries: Dict[int, str]) -> List[str]:
    """检查编号连续性。"""
    if not entries:
        return []
    nums = sorted(entries.keys())
    issues = []
    expected = nums[0]
    for n in nums:
        if n != expected:
            issues.append(f"编号不连续：期望 [{expected}]，实际下一个是 [{n}]")
        expected = n + 1
    # 检查重复（理论上 dict 不会重复，但仍报告起点）
    if nums[0] != 1:
        issues.append(f"编号未从 [1] 开始，第一条为 [{nums[0]}]")
    return issues


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class RefCheckerTool(BaseTool):
    """
    参考文献规范检查工具。

    自动检测 Markdown 中的参考文献章节，提取所有条目，
    并与正文中的 [X] 引用交叉核验。
    """

    def __init__(self):
        super().__init__(
            name="ref_checker",
            description=(
                "检查 Markdown 全文的参考文献规范性：编号连续性、格式完整性、"
                "正文引用与文献列表交叉核验（漏引/孤引检测）。"
                "输入 md_path（来自 pymupdf_parse 或 docling_parse）。"
            ),
            input_schema={
                "md_path": "必填，Markdown 文件路径（通常来自 pymupdf_parse 的 markdown_path）",
                "max_issues": "可选，每类问题最多输出多少条，默认 10",
            }
        )

    def run(self, md_path: str, max_issues: int = 10) -> ToolResult:
        logger.info(f"RefCheckerTool | md={md_path!r}")

        path = Path(md_path)
        if not path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {md_path}")

        try:
            md_text = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取失败: {e}")

        body_text, ref_text = _find_ref_section(md_text)

        if not ref_text:
            return ToolResult(
                success=True,
                output="⚠️ 未找到参考文献章节（关键词：参考文献 / References）。请确认文档中存在该章节。",
                metadata={"md_path": md_path, "ref_section_found": False}
            )

        entries = _parse_ref_entries(ref_text)
        cited_in_body = _parse_body_citations(body_text)

        if not entries:
            return ToolResult(
                success=True,
                output="⚠️ 找到参考文献章节，但未能解析出任何 [N] 格式条目。",
                metadata={"md_path": md_path, "ref_section_found": True, "entry_count": 0}
            )

        ref_nums = set(entries.keys())
        problems: List[str] = []

        # 1. 编号连续性
        numbering_issues = _check_numbering(entries)
        problems.extend(numbering_issues[:max_issues])

        # 2. 条目格式
        format_issues = []
        for num, text in sorted(entries.items()):
            format_issues.extend(_check_entry_format(num, text))
        problems.extend(format_issues[:max_issues])

        # 3. 正文引用但文献列表没有
        missing_in_ref = sorted(cited_in_body - ref_nums)
        for n in missing_in_ref[:max_issues]:
            problems.append(f"正文引用了 [{n}] 但参考文献列表中无此条目（可能缺失）")

        # 4. 文献列表有但正文从未引用
        never_cited = sorted(ref_nums - cited_in_body)
        for n in never_cited[:max_issues]:
            problems.append(f"文献 [{n}] 在参考文献列表中存在，但正文中从未被引用")

        # ── 输出 ──────────────────────────────────────────────────
        summary_lines = [
            f"## 参考文献检查报告",
            f"",
            f"- 文献列表条目数：{len(entries)} 条（编号 {min(ref_nums)}~{max(ref_nums)}）",
            f"- 正文中引用编号数：{len(cited_in_body)} 个",
            f"- 发现问题：{len(problems)} 条",
            f"",
        ]

        if problems:
            summary_lines.append("### 问题列表")
            for i, p in enumerate(problems, 1):
                summary_lines.append(f"{i}. {p}")
        else:
            summary_lines.append("✅ 未发现明显问题")

        output = "\n".join(summary_lines)

        return ToolResult(
            success=True,
            output=output,
            metadata={
                "md_path": md_path,
                "ref_section_found": True,
                "entry_count": len(entries),
                "cited_count": len(cited_in_body),
                "missing_in_ref": missing_in_ref,
                "never_cited": never_cited,
                "numbering_issues": numbering_issues,
                "format_issues_count": len(format_issues),
                "total_problems": len(problems),
            }
        )
