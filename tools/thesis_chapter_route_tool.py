"""
ThesisChapterRouteTool：根据 thesis_outline_extract 的 outline 结果生成六路章节选择器。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OutlineNode:
    title: str
    number: str
    depth: int
    page_start: int
    page_end_exclusive: int


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower())


def _is_ref(title: str) -> bool:
    t = _normalize(title)
    return any(k in t for k in ("参考文献", "references", "bibliography"))


def _is_abstract(title: str) -> bool:
    t = _normalize(title)
    return "摘要" in t or "abstract" in t


def _is_experiment(title: str) -> bool:
    t = _normalize(title)
    return any(
        k in t
        for k in (
            "实验",
            "experiment",
            "evaluation",
            "implement",
            "implementation",
            "benchmark",
            "ablation",
            "结果",
        )
    )


def _is_front_or_back_matter(title: str) -> bool:
    t = _normalize(title)
    return any(
        k in t
        for k in (
            "摘要",
            "abstract",
            "目录",
            "contents",
            "致谢",
            "acknowled",
            "附录",
            "appendix",
            "参考文献",
            "references",
            "bibliography",
        )
    )


def _flatten_tree(tree: List[Dict[str, Any]]) -> List[OutlineNode]:
    out: List[OutlineNode] = []

    def walk(items: List[Dict[str, Any]]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            number = str(item.get("number", "") or "").strip()
            depth = int(item.get("depth", 0) or 0)
            start = int(item.get("page_start", 1) or 1)
            end_ex = int(item.get("page_end_exclusive", start + 1) or (start + 1))
            if end_ex <= start:
                end_ex = start + 1
            out.append(
                OutlineNode(
                    title=title,
                    number=number,
                    depth=depth,
                    page_start=max(1, start),
                    page_end_exclusive=max(start + 1, end_ex),
                )
            )
            children = item.get("children", [])
            if isinstance(children, list):
                walk(children)

    walk(tree)
    return out


def _selector_from_nodes(nodes: List[OutlineNode]) -> str:
    tokens: List[str] = []
    seen = set()
    for n in nodes:
        token = n.number.strip() if n.number.strip() else n.title.strip()
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return ";".join(tokens)


def _representative_page(nodes: List[OutlineNode]) -> int:
    if not nodes:
        return 1
    start = min(n.page_start for n in nodes)
    end_ex = max(n.page_end_exclusive for n in nodes)
    length = max(1, end_ex - start)
    if length < 10:
        return start
    return start + (length // 2)


class ThesisChapterRouteTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="thesis_chapter_route",
            description=(
                "根据 thesis_outline_extract 的 outline 结果，"
                "输出摘要/绪论/背景相关/方法/实验/参考文献六路 chapters 选择器与代表页。"
            ),
            input_schema={
                "outline_path": "可选，outline.json 路径（优先读取）",
                "outline_tree": "可选，目录树对象（若不传 outline_path）",
                "strict": "可选，true 时关键路由缺失则失败（默认 false）",
            },
        )

    def run(
        self,
        outline_path: str = "",
        outline_tree: Optional[List[Dict[str, Any]]] = None,
        strict: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            if kwargs:
                outline_path = str(kwargs.get("outline_path", outline_path) or outline_path)
                strict = bool(kwargs.get("strict", strict))
                if outline_tree is None:
                    candidate = kwargs.get("outline_tree")
                    if isinstance(candidate, list):
                        outline_tree = candidate

            tree: List[Dict[str, Any]] = []
            if str(outline_path or "").strip():
                path = Path(str(outline_path).strip())
                if not path.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"outline_path 不存在：{outline_path}",
                        metadata={"outline_path": outline_path},
                    )
                obj = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(obj, dict) and isinstance(obj.get("tree"), list):
                    tree = obj["tree"]
                elif isinstance(obj, list):
                    tree = obj
            elif isinstance(outline_tree, list):
                tree = outline_tree

            if not tree:
                return ToolResult(success=False, output="", error="未提供可用目录树（tree）", metadata={})

            flat = _flatten_tree(tree)
            if not flat:
                return ToolResult(success=False, output="", error="目录树为空", metadata={})

            root_body = [n for n in flat if n.depth == 0 and not _is_front_or_back_matter(n.title)]

            abstract_nodes = [n for n in flat if _is_abstract(n.title)]
            ref_nodes = [n for n in flat if _is_ref(n.title)]

            intro_nodes: List[OutlineNode] = []
            bg_nodes: List[OutlineNode] = []
            if root_body:
                intro_nodes = [root_body[0]]
                if len(root_body) >= 2:
                    bg_nodes = [root_body[1]]

            if not intro_nodes:
                intro_nodes = [n for n in flat if ("绪论" in n.title or "Introduction" in n.title)]
            if not bg_nodes:
                bg_nodes = [
                    n
                    for n in flat
                    if ("相关工作" in n.title or "背景" in n.title or "related work" in n.title.lower())
                ]

            exp_roots = [n for n in root_body if _is_experiment(n.title)]
            first_exp_idx = root_body.index(exp_roots[0]) if exp_roots else -1

            method_nodes: List[OutlineNode] = []
            if root_body:
                method_start = 2 if len(root_body) > 2 else max(0, len(root_body) - 1)
                method_end = first_exp_idx if first_exp_idx >= 0 else len(root_body)
                if method_start < method_end:
                    method_nodes = root_body[method_start:method_end]

            selectors = {
                "abstract": _selector_from_nodes(abstract_nodes) or "摘要",
                "introduction": _selector_from_nodes(intro_nodes) or "第1章",
                "background_related_work": _selector_from_nodes(bg_nodes) or "第2章",
                "method": _selector_from_nodes(method_nodes) or "第3章",
                "experiment": _selector_from_nodes(exp_roots) or "实验",
                "references": _selector_from_nodes(ref_nodes) or "参考文献",
            }

            representative_pages = {
                "abstract": _representative_page(abstract_nodes),
                "introduction": _representative_page(intro_nodes),
                "background_related_work": _representative_page(bg_nodes),
                "method": _representative_page(method_nodes),
                "experiment": _representative_page(exp_roots),
                "references": _representative_page(ref_nodes),
            }

            matched_nodes = {
                "abstract": [n.__dict__ for n in abstract_nodes],
                "introduction": [n.__dict__ for n in intro_nodes],
                "background_related_work": [n.__dict__ for n in bg_nodes],
                "method": [n.__dict__ for n in method_nodes],
                "experiment": [n.__dict__ for n in exp_roots],
                "references": [n.__dict__ for n in ref_nodes],
            }

            unresolved = [k for k, v in matched_nodes.items() if len(v) == 0]
            if strict and unresolved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"关键章节路由缺失：{', '.join(unresolved)}",
                    metadata={
                        "selectors": selectors,
                        "representative_pages": representative_pages,
                        "matched_nodes": matched_nodes,
                        "unresolved": unresolved,
                    },
                )

            metadata = {
                "selectors": selectors,
                "representative_pages": representative_pages,
                "matched_nodes": matched_nodes,
                "unresolved": unresolved,
            }
            output = json.dumps(
                {
                    "selectors": selectors,
                    "representative_pages": representative_pages,
                    "unresolved": unresolved,
                },
                ensure_ascii=False,
            )
            return ToolResult(success=True, output=output, metadata=metadata)
        except Exception as e:  # noqa: BLE001
            logger.exception("ThesisChapterRouteTool 执行失败")
            return ToolResult(success=False, output="", error=str(e), metadata={})
