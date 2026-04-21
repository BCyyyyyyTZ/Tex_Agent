"""
MarkdownSectionTool：从 Markdown 文件中按章节标题提取指定段落。

用途：
  - 论文检查 workflow 中，为每个检查节点只提供相关章节内容，减少 context 大小
  - 支持按关键词匹配标题（模糊匹配），或按层级（H1/H2/H3）提取
  - 支持提取"结构摘要"：只返回各级标题列表（不含正文），用于结构检查

典型用法：
  abstract_checker  → sections=["abstract", "introduction"]
  experiment_checker → sections=["experiment", "evaluation", "result"]
  figure_checker    → sections=["references", "figure", "table", "caption"]
  structure_checker  → mode="outline"（只要标题大纲）
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Markdown 解析工具函数
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)', re.MULTILINE)


def _parse_sections(md_text: str) -> List[Dict]:
    """
    将 Markdown 文本解析为章节列表。
    每个章节：{"level": int, "title": str, "content": str, "start_line": int}
    """
    lines = md_text.splitlines()
    sections = []
    current: Optional[Dict] = None
    current_lines: List[str] = []

    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m:
            # 保存上一个章节
            if current is not None:
                current["content"] = "\n".join(current_lines).strip()
                sections.append(current)
            # 开启新章节
            current = {
                "level": len(m.group(1)),
                "title": m.group(2).strip(),
                "content": "",
                "start_line": i + 1,
            }
            current_lines = []
        else:
            if current is not None:
                current_lines.append(line)

    # 收尾
    if current is not None:
        current["content"] = "\n".join(current_lines).strip()
        sections.append(current)

    return sections


def _match_sections(sections: List[Dict], keywords: List[str]) -> List[Dict]:
    """
    返回标题中包含任意 keyword 的章节（大小写不敏感）。
    若 keywords 为空，返回全部章节。
    """
    if not keywords:
        return sections
    kws = [k.lower().strip() for k in keywords if k.strip()]
    matched = []
    for s in sections:
        title_lower = s["title"].lower()
        if any(kw in title_lower for kw in kws):
            matched.append(s)
    return matched


def _build_outline(sections: List[Dict], max_items: int = 60) -> str:
    """
    生成只含标题的大纲字符串：
      ## 1 Introduction
      ### 1.1 Background
      ...
    """
    lines = []
    for s in sections[:max_items]:
        indent = "  " * (s["level"] - 1)
        lines.append(f"{indent}{'#' * s['level']} {s['title']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MarkdownSectionTool
# ---------------------------------------------------------------------------

class MarkdownSectionTool(BaseTool):
    """
    从 Markdown 文件中按章节关键词提取段落内容。

    workflow 用法示例：
      # 只提取摘要和引言
      {"tool_input": {"md_path": "...", "section_keywords": ["abstract", "introduction"]}}

      # 只提取大纲（用于结构检查）
      {"tool_input": {"md_path": "...", "mode": "outline"}}

      # 提取实验相关章节
      {"tool_input": {"md_path": "...", "section_keywords": ["experiment", "evaluation", "result", "dataset"]}}
    """

    def __init__(self):
        super().__init__(
            name="markdown_section",
            description=(
                "从 Markdown 文件中按章节关键词提取指定段落（支持模糊标题匹配）。"
                "mode=outline 时只返回标题大纲，适合结构检查节点；"
                "mode=content 时返回匹配章节的完整正文（可配合 max_chars 截断）。"
            ),
            input_schema={
                "md_path": "必填，Markdown 文件路径（通常来自 docling_parse 的 markdown_path 元数据）",
                "section_keywords": (
                    "可选，章节标题关键词列表（字符串列表或 JSON 数组字符串），"
                    "不区分大小写。为空则返回全部章节。"
                    "示例: [\"abstract\", \"introduction\"] 或 [\"实验\", \"结果\"]"
                ),
                "mode": (
                    "可选，提取模式：'content'（默认，返回正文）或 'outline'（只返回标题大纲）"
                ),
                "max_chars": "可选，内容最大字符数，默认 6000；0 表示不截断",
                "include_subsections": (
                    "可选，是否包含匹配章节的子章节，默认 true"
                ),
            }
        )

    def run(
        self,
        md_path: str,
        section_keywords: Any = None,
        mode: str = "content",
        max_chars: int = 6000,
        include_subsections: bool = True,
    ) -> ToolResult:
        """
        提取 Markdown 指定章节。

        Args:
            md_path:             Markdown 文件路径
            section_keywords:    章节标题关键词（列表或 JSON 字符串）
            mode:                'content' 或 'outline'
            max_chars:           最大输出字符数（0=不限）
            include_subsections: 是否包含子章节内容

        Returns:
            ToolResult，output 为提取的文本内容
        """
        logger.info(f"MarkdownSectionTool | path={md_path!r} mode={mode!r} kws={section_keywords!r}")

        # 解析关键词
        kws = _parse_keywords(section_keywords)

        # 读取文件
        path = Path(md_path)
        if not path.exists():
            return ToolResult(
                success=False, output="", error=f"文件不存在: {md_path}",
                metadata={"md_path": md_path},
            )
        try:
            md_text = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"读取失败: {e}",
                metadata={"md_path": md_path},
            )

        sections = _parse_sections(md_text)
        logger.info(f"解析到 {len(sections)} 个章节")

        if mode == "outline":
            outline = _build_outline(sections)
            return ToolResult(
                success=True,
                output=f"[文档大纲 - {path.name}]\n\n{outline}",
                metadata={
                    "md_path": md_path,
                    "mode": "outline",
                    "total_sections": len(sections),
                    "outline_len": len(outline),
                },
            )

        # content 模式：提取匹配章节
        matched = _match_sections(sections, kws)

        if not matched and kws:
            # 关键词无匹配 → 返回所有章节（fallback）
            logger.warning(f"关键词 {kws} 无匹配，返回全文前 {max_chars} 字符")
            content = md_text[:max_chars] if max_chars else md_text
            return ToolResult(
                success=True,
                output=f"[警告：关键词 {kws} 无匹配，返回全文]\n\n{content}",
                metadata={
                    "md_path": md_path,
                    "mode": "content",
                    "matched_sections": 0,
                    "total_sections": len(sections),
                    "keywords": kws,
                    "fallback": True,
                },
            )

        # 构建输出内容
        parts = []
        matched_set = {id(s) for s in matched}

        for s in sections:
            if id(s) not in matched_set:
                # 如果 include_subsections，检查是否是匹配节的子节
                if include_subsections and parts:
                    # 只要前一个 matched 的 level < 当前 level，视为子节
                    pass
                else:
                    continue
            header = "#" * s["level"] + " " + s["title"]
            body = s["content"]
            parts.append(f"{header}\n\n{body}")

        if not parts:
            parts = [f"{s['title']}: {s['content'][:200]}" for s in matched]

        output = "\n\n---\n\n".join(parts)
        if max_chars and len(output) > max_chars:
            output = output[:max_chars] + f"\n\n...[已截断，共 {len(output)} 字符，显示前 {max_chars} 字符]"

        meta_titles = [s["title"] for s in matched]
        return ToolResult(
            success=True,
            output=f"[提取章节: {', '.join(meta_titles[:5])}]\n\n{output}",
            metadata={
                "md_path": md_path,
                "mode": "content",
                "matched_sections": len(matched),
                "matched_titles": meta_titles,
                "total_sections": len(sections),
                "keywords": kws,
                "output_chars": len(output),
            },
        )


# ---------------------------------------------------------------------------
# 辅助：解析 section_keywords
# ---------------------------------------------------------------------------

import json as _json
import ast as _ast


def _parse_keywords(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(k) for k in raw if k]
    if not isinstance(raw, str):
        return [str(raw)]
    text = raw.strip()
    try:
        parsed = _json.loads(text)
        if isinstance(parsed, list):
            return [str(k) for k in parsed if k]
    except Exception:
        pass
    try:
        parsed = _ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(k) for k in parsed if k]
    except Exception:
        pass
    # 逗号分隔字符串
    return [k.strip().strip('"\'') for k in text.split(",") if k.strip()]
