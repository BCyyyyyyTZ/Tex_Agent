"""
工作流节点间 JSON 解析：从 Tool 输出提取 issues / project。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from latex.models import DiagnosticIssue, ProjectIndex
from latex.serialize import from_dict


def _loads_maybe(text: Any) -> Any:
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    s = str(text).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def issues_from_tool_output(text: Any) -> List[DiagnosticIssue]:
    """从 chktex/latexmk/merge 等 Tool 的 result JSON 提取 issues。"""
    data = _loads_maybe(text)
    if data is None:
        return []
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = data.get("issues", [])
    else:
        return []
    if not isinstance(raw, list):
        return []
    out: List[DiagnosticIssue] = []
    for item in raw:
        if isinstance(item, DiagnosticIssue):
            out.append(item)
        elif isinstance(item, dict):
            out.append(from_dict(DiagnosticIssue, item))
    return out


def project_from_tool_output(text: Any) -> Optional[ProjectIndex]:
    data = _loads_maybe(text)
    if data is None:
        return None
    if isinstance(data, dict):
        if "project" in data and isinstance(data["project"], dict):
            data = data["project"]
        elif "root" not in data and "files" not in data:
            return None
        return from_dict(ProjectIndex, data)
    return None


def extract_root_from_payload(data: Dict[str, Any]) -> str:
    root = data.get("root")
    if root and str(root).strip():
        return str(root).strip()
    user_input = data.get("user_input") or data.get("input")
    from latex.coerce_payload import parse_root_from_user_input

    return parse_root_from_user_input(user_input)
