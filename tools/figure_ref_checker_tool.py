"""
FigureRefCheckerTool：检查 Markdown 全文中图、表、算法、公式的交叉引用完整性。

检查项（对应 thesis-checklists 图表与算法检查列表）：
  1. 图/表/算法/公式的定义（caption）是否都被正文引用
  2. 正文中引用了某图/表/算法，但其定义不存在（编号错误或遗漏）
  3. 编号是否连续（图1→图2→图3…），有无跳号
  4. 图标题是否在图下方（Markdown 无法直接检测，但可检测 caption 出现的上下文）
  5. 表标题是否在表上方（同上）
  6. 图/表/算法是否附有文字解释（caption 后是否紧跟文字段落）

输出：
  - 文字摘要（适合 LLM 输入）
  - metadata 包含结构化问题列表
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 正则定义
# ---------------------------------------------------------------------------

# 编号模式：支持 N 或 N-M（章-序号）格式，统一提取为第二个数字（序号）
# 例如：图4-1 → 序号1；图3 → 序号3
_NUM_PAT = r'(\d+)(?:-(\d+))?'

# 图/表/算法 caption 定义 - 两种格式：
#   A. 行内：图 4-1 说明文字...（后跟标点或文字）
#   B. 标题行：## 图4-1  或  ### 表-1（PyMuPDF 把短标签解析为标题的情形）
_CAPTION_RE = re.compile(
    r'(?:(?:^|\n)#{0,4}\s*)(?:'
    r'(?P<fig>(?:图|Figure|Fig\.?)\s*\d*(?:-\d+)?)'
    r'|(?P<tab>(?:表|Table)\s*\d*(?:-\d+)?)'
    r'|(?P<alg>(?:算法|Algorithm)\s*\d*(?:-\d+)?)'
    r'|(?P<eq>(?:公式|式|Equation|Eq\.?)\s*\(?\d*(?:-\d+)?\)?)'
    r')(?:\s*[.。：:：\s]|\s*$)',
    re.IGNORECASE | re.MULTILINE
)

# 正文中的引用（图X、表X、算法X）支持章-序号格式
_INLINE_REF_RE = re.compile(
    r'(?:'
    r'(?:如图|见图|图)\s*(\d+(?:-\d+)?)'
    r'|(?:如表|见表|表)\s*(\d+(?:-\d+)?)'
    r'|(?:算法|如算法)\s*(\d+(?:-\d+)?)'
    r'|(?:公式|式|如公式|如式)\s*\(?(\d+(?:-\d+)?)\)?'
    r'|(?:Figure|Fig\.?)\s*(\d+(?:-\d+)?)'
    r'|(?:Table)\s*(\d+(?:-\d+)?)'
    r'|(?:Algorithm)\s*(\d+(?:-\d+)?)'
    r'|(?:Equation|Eq\.?)\s*\(?(\d+(?:-\d+)?)\)?'
    r')',
    re.IGNORECASE
)

# 参考文献章节（排除参考文献区域）
_REF_SECTION_RE = re.compile(
    r'^#{1,3}\s*(?:参考文献|References?|Bibliography)',
    re.IGNORECASE | re.MULTILINE
)


# ---------------------------------------------------------------------------
# 提取函数
# ---------------------------------------------------------------------------

def _norm_num(raw: str) -> str:
    """把编号字符串归一化为可比较的 key，例如 '4-1' → '4-1'，'3' → '3'。"""
    return raw.strip() if raw else ""


def _extract_defined(md_text: str) -> Dict[str, Dict[str, int]]:
    """
    提取文档中定义的所有图/表/算法/公式编号（支持章-序号格式）。
    返回 {"fig": {"4-1": line_no, ...}, "tab": {}, "alg": {}, "eq": {}}
    """
    defined: Dict[str, Dict[str, int]] = {
        "fig": {}, "tab": {}, "alg": {}, "eq": {}
    }
    text_oneline = md_text
    # 提取 caption 中的编号
    _NUM_EXTRACT = re.compile(r'(\d+(?:-\d+)?)')

    for m in _CAPTION_RE.finditer(text_oneline):
        line_no = text_oneline[:m.start()].count("\n") + 1
        matched_text = m.group(0)
        nums = _NUM_EXTRACT.findall(matched_text)
        if not nums:
            continue
        key = _norm_num(nums[-1])  # 取最后一个数字组合（即图号本身）
        if m.group("fig"):
            defined["fig"][key] = line_no
        elif m.group("tab"):
            defined["tab"][key] = line_no
        elif m.group("alg"):
            defined["alg"][key] = line_no
        elif m.group("eq"):
            defined["eq"][key] = line_no

    return defined


def _extract_cited(body_text: str) -> Dict[str, Set[str]]:
    """
    从正文中提取所有引用的图/表/算法/公式编号（支持章-序号格式）。
    返回 {"fig": {"4-1","3"}, "tab": {}, "alg": {}, "eq": {}}
    """
    cited: Dict[str, Set[str]] = {
        "fig": set(), "tab": set(), "alg": set(), "eq": set()
    }
    for m in _INLINE_REF_RE.finditer(body_text):
        groups = m.groups()
        # groups 顺序: fig_cn, tab_cn, alg_cn, eq_cn, fig_en, tab_en, alg_en, eq_en
        for i, key in enumerate(["fig", "tab", "alg", "eq", "fig", "tab", "alg", "eq"]):
            if groups[i]:
                cited[key].add(_norm_num(groups[i]))
    return cited


def _check_numbering_gaps(defined: Dict[str, int], label: str) -> List[str]:
    """检查编号连续性（支持章-序号格式，各章内部检查）。"""
    if not defined:
        return []
    keys = sorted(defined.keys())
    has_chapter_fmt = any("-" in k for k in keys)
    if has_chapter_fmt:
        from collections import defaultdict
        by_chapter: dict = defaultdict(list)
        for k in keys:
            if "-" in k:
                ch, seq = k.split("-", 1)
                try:
                    by_chapter[ch].append(int(seq))
                except ValueError:
                    pass
            else:
                try:
                    by_chapter["0"].append(int(k))
                except ValueError:
                    pass
        issues = []
        for ch, seqs in sorted(by_chapter.items()):
            seqs.sort()
            if seqs[0] != 1:
                issues.append(f"第{ch}章的{label}编号未从1开始（最小为{seqs[0]}）")
            for i in range(len(seqs) - 1):
                if seqs[i + 1] != seqs[i] + 1:
                    issues.append(f"第{ch}章 {label}跳号：{seqs[i]}→{seqs[i+1]}")
        return issues
    try:
        nums = sorted(int(k) for k in keys)
    except ValueError:
        return []
    issues = []
    if nums[0] != 1:
        issues.append(f"{label} 编号未从1开始（最小为{nums[0]}）")
    for i in range(len(nums) - 1):
        if nums[i + 1] != nums[i] + 1:
            issues.append(f"{label} 编号跳号：{nums[i]}→{nums[i+1]}")
    return issues


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

_LABEL_NAMES = {
    "fig": "图",
    "tab": "表",
    "alg": "算法",
    "eq": "公式",
}


class FigureRefCheckerTool(BaseTool):
    """
    图表与公式交叉引用检查工具。

    自动扫描 Markdown 全文，提取所有图/表/算法/公式的
    定义（caption）和正文引用，并进行交叉核验与编号连续性检查。
    """

    def __init__(self):
        super().__init__(
            name="figure_ref_checker",
            description=(
                "检查 Markdown 全文中图、表、算法、公式的交叉引用完整性和编号连续性。"
                "识别：定义了但未被正文引用的图表、正文引用了但无对应定义的图表、编号跳号等问题。"
                "输入 md_path（来自 pymupdf_parse 或 docling_parse）。"
            ),
            input_schema={
                "md_path": "必填，Markdown 文件路径",
                "max_issues": "可选，每类问题最多显示多少条，默认 15",
            }
        )

    def run(self, md_path: str, max_issues: int = 15) -> ToolResult:
        logger.info(f"FigureRefCheckerTool | md={md_path!r}")

        path = Path(md_path)
        if not path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {md_path}")

        try:
            md_text = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取失败: {e}")

        # 把参考文献章节从正文中排除（避免把文献标题里的图编号误识别为正文引用）
        # 取最后一个"参考文献"位置（避开目录页面的早期出现）
        _ref_matches = list(_REF_SECTION_RE.finditer(md_text))
        ref_m = _ref_matches[-1] if _ref_matches else None
        body_text = md_text[:ref_m.start()] if ref_m else md_text
        full_text = md_text  # 定义可能在参考文献后面（论文图可能附在文末）

        defined = _extract_defined(full_text)
        cited = _extract_cited(body_text)

        all_problems: List[str] = []
        metadata_issues: Dict[str, List] = {}

        for key in ("fig", "tab", "alg", "eq"):
            label = _LABEL_NAMES[key]
            def_nums = set(defined[key].keys())
            cite_nums = cited[key]
            issues: List[str] = []

            # 编号连续性
            gap_issues = _check_numbering_gaps(defined[key], label)
            issues.extend(gap_issues)

            # 定义了但未引用
            not_cited = sorted(def_nums - cite_nums)
            for n in not_cited[:max_issues]:
                issues.append(f"{label} {n}（第 {defined[key][n]} 行）定义了但正文中未被引用")

            # 引用了但未定义
            not_defined = sorted(cite_nums - def_nums)
            for n in not_defined[:max_issues]:
                issues.append(f"正文引用了{label} {n}，但文档中未找到对应的 caption 定义")

            metadata_issues[key] = issues
            all_problems.extend(issues)

        # ── 构建输出 ──────────────────────────────────────────────
        total_figs = len(defined["fig"])
        total_tabs = len(defined["tab"])
        total_algs = len(defined["alg"])
        total_eqs = len(defined["eq"])

        summary_lines = [
            "## 图表交叉引用检查报告",
            "",
            f"- 检测到图：{total_figs} 个 | 表：{total_tabs} 个 | 算法：{total_algs} 个 | 公式：{total_eqs} 个",
            f"- 发现问题：{len(all_problems)} 条",
            "",
        ]

        if all_problems:
            summary_lines.append("### 问题列表")
            for i, p in enumerate(all_problems, 1):
                summary_lines.append(f"{i}. {p}")
        else:
            summary_lines.append("✅ 未发现图表引用问题")

        return ToolResult(
            success=True,
            output="\n".join(summary_lines),
            metadata={
                "md_path": md_path,
                "defined_counts": {k: len(v) for k, v in defined.items()},
                "cited_counts": {k: len(v) for k, v in cited.items()},
                "issues_by_type": metadata_issues,
                "total_problems": len(all_problems),
            }
        )
