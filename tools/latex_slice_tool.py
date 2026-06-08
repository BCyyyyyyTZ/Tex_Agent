"""
LatexSliceTool：按 DiagnosticIssue 读取源码片段（阶段 5）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import METADATA_LATEX_DIRTY
from latex.diagnose_io import extract_root_from_payload, issues_from_tool_output
from latex.dirty import compute_file_dirty
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path
from latex.project_index import build_project_index
from latex.serialize import from_dict, to_dict
from latex.slice import slice_issues
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_tool_input(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError(
            '输入为空。示例: {"root": "...", "issues": [...]} 或 {"root": "...", "issue_ids": ["..."]}'
        )
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON 根类型必须是 object")
        return data
    return {"root": text}


def _issues_from_payload(payload: Dict[str, Any]) -> List[DiagnosticIssue]:
    raw = payload.get("issues")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("issues 必须是数组")
    return [from_dict(DiagnosticIssue, item) if isinstance(item, dict) else item for item in raw]


class LatexSliceTool(BaseTool):
    """
    为诊断 issue 提取源码上下文片段。

    输入 JSON：
        - root（必填）
        - issues（可选）：DiagnosticIssue 对象列表
        - issue_ids（可选）：仅切片这些 id（需同时提供 issues）
        - context_lines（可选）：默认 settings.latex_slice_context_lines
        - severity（可选）：仅处理该级别，如 "error"
        - baseline_checksums（可选）：file->checksum，与当前项目对比产出 dirty
        - main_tex（可选）：无 baseline 且需 dirty 时用于 build_project_index
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_slice",
            description=(
                "按 DiagnosticIssue 读取报错行附近源码片段。"
                '输入 JSON：{"root": "...", "issues": [...], "issue_ids": ["..."], "context_lines": 10}。'
            ),
            input_schema={
                "root": "必填，项目根目录",
                "issues": "可选，DiagnosticIssue 列表",
                "issue_ids": "可选，仅切片指定 id",
                "context_lines": "可选，上下文行数",
                "severity": "可选，过滤 severity",
                "baseline_checksums": "可选，用于文件级 dirty 检测",
            },
        )

    def run(
        self,
        input: str = "",
        payload: Any = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            if kwargs or isinstance(payload, dict):
                merged = coerce_json_payload(payload, input=input, **kwargs)
                input = json.dumps(merged, ensure_ascii=False)
            payload = _parse_tool_input(input)

            if not payload.get("issues") and payload.get("merge_output"):
                payload["issues"] = [
                    i.model_dump(mode="json")
                    for i in issues_from_tool_output(payload.get("merge_output"))
                ]
            root_raw = payload.get("root") or extract_root_from_payload(payload)
            if root_raw:
                payload["root"] = root_raw
            if not root_raw or not str(root_raw).strip():
                return ToolResult(success=False, output="", error="缺少必填字段 root")

            root = Path(str(root_raw)).expanduser().resolve()
            if not root.is_dir():
                return ToolResult(success=False, output="", error=f"root 不是有效目录: {root}")

            issues = _issues_from_payload(payload)
            severity_filter = payload.get("severity")
            if severity_filter:
                sev = str(severity_filter).strip().lower()
                issues = [i for i in issues if i.severity.value == sev]

            issue_ids = payload.get("issue_ids")
            if issue_ids is not None:
                if not isinstance(issue_ids, list):
                    raise ValueError("issue_ids 必须是字符串数组")
                issue_ids = [str(x) for x in issue_ids]

            context_lines = payload.get("context_lines", settings.latex_slice_context_lines)
            try:
                context_lines = int(context_lines)
            except (TypeError, ValueError):
                context_lines = settings.latex_slice_context_lines

            if not issues:
                body = {"slices": [], "slice_count": 0}
                metadata: Dict[str, Any] = {}
                dirty_meta = _maybe_dirty(root, payload, metadata)
                if dirty_meta:
                    body["dirty"] = dirty_meta
                return ToolResult(
                    success=True,
                    output=json.dumps(body, ensure_ascii=False, indent=2),
                    metadata=metadata,
                )

            slices = slice_issues(
                issues,
                root=root,
                context_lines=context_lines,
                issue_ids=issue_ids,
            )
            slice_dicts = [to_dict(s) for s in slices]
            body: Dict[str, Any] = {
                "slices": slice_dicts,
                "slice_count": len(slice_dicts),
            }
            metadata = {"slice_count": len(slice_dicts)}
            dirty_meta = _maybe_dirty(root, payload, metadata)
            if dirty_meta:
                body["dirty"] = dirty_meta

            return ToolResult(
                success=True,
                output=json.dumps(body, ensure_ascii=False, indent=2),
                metadata=metadata,
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning("latex_slice: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_slice 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")


def _maybe_dirty(
    root: Path,
    payload: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Optional[Dict[str, List[List[int]]]]:
    baseline = payload.get("baseline_checksums")
    if baseline is None:
        return None
    if not isinstance(baseline, dict):
        raise ValueError("baseline_checksums 必须是 object")

    main_tex = payload.get("main_tex")
    if main_tex is not None:
        main_tex = str(main_tex).strip() or None

    index = build_project_index(root, main_tex=main_tex, enrich=False)
    dirty = compute_file_dirty(index, {normalize_rel_path(k): str(v) for k, v in baseline.items()})
    serializable = {k: [list(r) for r in ranges] for k, ranges in dirty.items()}
    metadata[METADATA_LATEX_DIRTY] = serializable
    return serializable
