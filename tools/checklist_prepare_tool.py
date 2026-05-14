"""
ChecklistPrepareTool：将论文 checklist 确定性切分为 6 份审查包。

每份审查包 = 「通用规则」+「章节组织检查列表」+「目标模块检查列表」。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)

_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _normalize_title(title: str) -> str:
    text = str(title or "").strip().lower()
    text = text.replace(" ", "")
    text = text.replace("（", "(").replace("）", ")")
    return text


def _split_h2_sections(md_text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    matches = list(_H2_RE.finditer(md_text))
    if not matches:
        return sections
    for idx, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md_text)
        block = md_text[start:end].strip()
        sections[title] = block
    return sections


def _pick_section(sections: Dict[str, str], aliases: List[str]) -> Tuple[str, str]:
    if not sections:
        return "", ""
    normalized = {_normalize_title(k): k for k in sections.keys()}
    for alias in aliases:
        key = normalized.get(_normalize_title(alias))
        if key:
            return key, sections[key]
    return "", ""


def _compose_package(common_sections: List[str], specific_section: str) -> str:
    parts = [s.strip() for s in common_sections if str(s).strip()]
    if str(specific_section).strip():
        parts.append(specific_section.strip())
    return "\n\n---\n\n".join(parts).strip()


class ChecklistPrepareTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="checklist_prepare",
            description=(
                "将 thesis checklist 确定性切分为六份审查包。"
                "每份包含通用规则、章节组织、以及一个目标章节模块。"
            ),
            input_schema={
                "checklist_text": "可选，checklist 原文文本（优先于 checklist_path）",
                "checklist_path": "可选，checklist 文件路径；当 checklist_text 为空时读取",
                "include_reference_rules": "可选，是否给 references 包拼接参考文献规则（默认 true）",
            },
        )

    def run(
        self,
        checklist_text: str = "",
        checklist_path: str = "",
        include_reference_rules: bool = True,
        **kwargs,
    ) -> ToolResult:
        try:
            if kwargs:
                checklist_text = str(kwargs.get("checklist_text", checklist_text) or checklist_text)
                checklist_path = str(kwargs.get("checklist_path", checklist_path) or checklist_path)
                include_reference_rules = bool(
                    kwargs.get("include_reference_rules", include_reference_rules)
                )

            text = str(checklist_text or "").strip()
            if not text:
                path = Path(str(checklist_path or "").strip())
                if not path.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"checklist 文件不存在：{checklist_path}",
                        metadata={"checklist_path": checklist_path},
                    )
                text = path.read_text(encoding="utf-8")

            sections = _split_h2_sections(text)
            if not sections:
                return ToolResult(
                    success=False,
                    output="",
                    error="未识别到任何二级标题（## ...），无法切分 checklist",
                    metadata={},
                )

            common_title, common_text = _pick_section(sections, ["通用规则"])
            org_title, org_text = _pick_section(sections, ["章节组织检查列表", "章节组织"])

            abstract_title, abstract_text = _pick_section(sections, ["摘要的检查列表", "摘要检查列表"])
            intro_title, intro_text = _pick_section(sections, ["绪论检查列表", "引言检查列表"])
            bg_title, bg_text = _pick_section(
                sections, ["相关工作检查列表", "背景与相关工作检查列表"]
            )
            method_title, method_text = _pick_section(sections, ["方法章节检查列表"])
            exp_title, exp_text = _pick_section(sections, ["实验章节检查列表"])
            ref_title, ref_text = _pick_section(sections, ["参考文献检查列表"])

            common_blocks = [common_text, org_text]
            review_packages = {
                "abstract": _compose_package(common_blocks, abstract_text),
                "introduction": _compose_package(common_blocks, intro_text),
                "background_related_work": _compose_package(common_blocks, bg_text),
                "method": _compose_package(common_blocks, method_text),
                "experiment": _compose_package(common_blocks, exp_text),
                "references": _compose_package(common_blocks, ref_text if include_reference_rules else ""),
            }

            missing: List[str] = []
            if not common_text:
                missing.append("通用规则")
            if not org_text:
                missing.append("章节组织检查列表")
            if not abstract_text:
                missing.append("摘要的检查列表")
            if not intro_text:
                missing.append("绪论检查列表")
            if not bg_text:
                missing.append("相关工作检查列表")
            if not method_text:
                missing.append("方法章节检查列表")
            if not exp_text:
                missing.append("实验章节检查列表")
            if include_reference_rules and not ref_text:
                missing.append("参考文献检查列表")

            module_titles = {
                "common": common_title,
                "section_organization": org_title,
                "abstract": abstract_title,
                "introduction": intro_title,
                "background_related_work": bg_title,
                "method": method_title,
                "experiment": exp_title,
                "references": ref_title,
            }

            metadata = {
                "review_packages": review_packages,
                "module_titles": module_titles,
                "missing_modules": missing,
                "section_count": len(sections),
                "include_reference_rules": bool(include_reference_rules),
            }
            output = json.dumps(
                {
                    "success": True,
                    "review_package_keys": list(review_packages.keys()),
                    "missing_modules": missing,
                    "module_titles": module_titles,
                    "review_packages": review_packages,
                },
                ensure_ascii=False,
            )
            return ToolResult(success=True, output=output, metadata=metadata)
        except Exception as e:  # noqa: BLE001
            logger.exception("ChecklistPrepareTool 执行失败")
            return ToolResult(success=False, output="", error=str(e), metadata={})
