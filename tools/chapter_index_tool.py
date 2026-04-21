"""
ChapterIndexTool：从 Markdown 文件构建全文章节结构索引。

用途：
  - 为长文档（学位论文）生成精确的章节目录树（含层级、标题、页码估算、字符数）
  - 供 checklist 检查器判断：篇幅是否够、结构是否合理、章节是否孤立
  - 输出两种格式：
      mode="tree"   → 带缩进的可视化树状大纲（适合 LLM 输入）
      mode="json"   → 结构化 JSON 数组（适合工具间传递）

输出 JSON 格式（每个章节）：
  {
    "level":      1-6,
    "title":      "章节标题",
    "number":     "1.2.3"  (若检测到编号则提取),
    "char_count": 1234,    (该节正文字符数，不含子节)
    "sub_count":  3,       (直接子节数)
    "is_isolated": false,  (true = 父节仅有此一个子节)
    "start_line": 42
  }
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)

# 匹配章节编号：1 / 1.2 / 1.2.3 / 第一章 / 第1章 / Chapter 1
_NUMBER_RE = re.compile(
    r'^(?:(?:第\s*[一二三四五六七八九十百\d]+\s*[章节篇])|(?:Chapter\s+\d+)|(?:\d+(?:\.\d+)*))[\s\.\u3002：:。]?',
    re.IGNORECASE
)
_HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)', re.MULTILINE)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def _parse_sections(md_text: str) -> List[Dict]:
    lines = md_text.splitlines()
    sections = []
    current: Optional[Dict] = None
    current_lines: List[str] = []

    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m:
            if current is not None:
                current["content"] = "\n".join(current_lines).strip()
                current["char_count"] = len(current["content"])
                sections.append(current)
            title = m.group(2).strip()
            # 提取编号
            nm = _NUMBER_RE.match(title)
            number = nm.group(0).strip().rstrip(".:：。") if nm else ""
            current = {
                "level": len(m.group(1)),
                "title": title,
                "number": number,
                "content": "",
                "char_count": 0,
                "start_line": i + 1,
                "sub_count": 0,
                "is_isolated": False,
            }
            current_lines = []
        elif current is not None:
            current_lines.append(line)

    if current is not None:
        current["content"] = "\n".join(current_lines).strip()
        current["char_count"] = len(current["content"])
        sections.append(current)

    return sections


def _annotate_structure(sections: List[Dict]) -> List[Dict]:
    """计算每个节的直接子节数，并标注孤立子节。"""
    for i, sec in enumerate(sections):
        child_count = 0
        for j in range(i + 1, len(sections)):
            other = sections[j]
            if other["level"] <= sec["level"]:
                break
            if other["level"] == sec["level"] + 1:
                child_count += 1
        sec["sub_count"] = child_count

    # 标注孤立子节：父节只有1个直接子节
    for i, sec in enumerate(sections):
        if sec["level"] > 1:
            for j in range(i - 1, -1, -1):
                parent = sections[j]
                if parent["level"] == sec["level"] - 1:
                    if parent["sub_count"] == 1:
                        sec["is_isolated"] = True
                    break

    return sections


def _build_tree_text(sections: List[Dict], max_items: int = 200) -> str:
    """生成带缩进的可视化大纲。"""
    lines = []
    for s in sections[:max_items]:
        indent = "  " * (s["level"] - 1)
        hashes = "#" * s["level"]
        char_info = f"（{s['char_count']}字）" if s["char_count"] > 0 else ""
        isolated = " ⚠️孤立" if s["is_isolated"] else ""
        lines.append(f"{indent}{hashes} {s['title']}{char_info}{isolated}")
    return "\n".join(lines)


def _build_stats(sections: List[Dict]) -> Dict:
    """计算文档统计数据。"""
    total_chars = sum(s["char_count"] for s in sections)
    h1_sections = [s for s in sections if s["level"] == 1]
    h2_sections = [s for s in sections if s["level"] == 2]
    isolated = [s for s in sections if s["is_isolated"]]
    single_child_parents = [s for s in sections if s["sub_count"] == 1]

    return {
        "total_sections": len(sections),
        "total_chars": total_chars,
        "h1_count": len(h1_sections),
        "h2_count": len(h2_sections),
        "isolated_sections": len(isolated),
        "single_child_parents": len(single_child_parents),
        "h1_titles": [s["title"] for s in h1_sections],
    }


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class ChapterIndexTool(BaseTool):
    """
    章节结构索引工具。

    从 Markdown 文件构建全文章节树，用于：
      - 检查章节结构合理性（孤立子节、层级跳跃）
      - 检查篇幅（各章字符数）
      - 为后续切片工具提供精确的章节边界
    """

    def __init__(self):
        super().__init__(
            name="chapter_index",
            description=(
                "从 Markdown 文件构建章节结构索引树，输出可视化大纲或结构化 JSON。"
                "mode=tree 返回带缩进的大纲（适合 LLM 阅读）；"
                "mode=json 返回结构化章节数组（适合工具间传递）；"
                "mode=stats 返回统计摘要（章节数、总字符、孤立子节数等）。"
            ),
            input_schema={
                "md_path": "必填，Markdown 文件路径（来自 pymupdf_parse 或 docling_parse 的 markdown_path）",
                "mode": "可选，'tree'（默认）/ 'json' / 'stats'",
                "max_level": "可选，最大标题层级，默认 3（只显示到 H3）",
            }
        )

    def run(self, md_path: str, mode: str = "tree", max_level: int = 3) -> ToolResult:
        logger.info(f"ChapterIndexTool | md={md_path!r} mode={mode!r}")

        path = Path(md_path)
        if not path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {md_path}")

        try:
            md_text = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取失败: {e}")

        sections = _parse_sections(md_text)
        sections = _annotate_structure(sections)
        # 按 max_level 过滤
        filtered = [s for s in sections if s["level"] <= max_level]

        stats = _build_stats(filtered)

        if mode == "stats":
            summary = (
                f"章节统计：共 {stats['total_sections']} 节 | "
                f"一级章节 {stats['h1_count']} 个 | "
                f"二级节 {stats['h2_count']} 个 | "
                f"总正文字符 {stats['total_chars']:,} | "
                f"孤立子节 {stats['isolated_sections']} 个\n"
                f"一级章节：{stats['h1_titles']}"
            )
            return ToolResult(
                success=True, output=summary,
                metadata={"md_path": md_path, "mode": "stats", **stats}
            )

        if mode == "json":
            # 去掉 content 字段（太大），只保留索引信息
            export = []
            for s in filtered:
                export.append({
                    "level": s["level"],
                    "title": s["title"],
                    "number": s["number"],
                    "char_count": s["char_count"],
                    "sub_count": s["sub_count"],
                    "is_isolated": s["is_isolated"],
                    "start_line": s["start_line"],
                })
            json_str = json.dumps(export, ensure_ascii=False, indent=2)
            return ToolResult(
                success=True,
                output=f"[章节索引 JSON - {path.name}]\n\n{json_str}",
                metadata={"md_path": md_path, "mode": "json",
                          "section_count": len(export), **stats}
            )

        # 默认：tree 模式
        tree = _build_tree_text(filtered)
        header = (
            f"[章节结构树 - {path.name}]\n"
            f"共 {stats['total_sections']} 节 | 孤立子节 {stats['isolated_sections']} 个\n\n"
        )
        return ToolResult(
            success=True,
            output=header + tree,
            metadata={"md_path": md_path, "mode": "tree",
                      "section_count": len(filtered), **stats}
        )
