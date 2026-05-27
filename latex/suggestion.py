"""
LLM 修复建议解析与归一化（阶段 7）。
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Union

from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue, Position, Suggestion, TextRange
from latex.paths import normalize_rel_path

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _coerce_severity(raw: Any) -> Severity:
    if isinstance(raw, Severity):
        return raw
    if raw is None:
        return Severity.INFO
    text = str(raw).strip().lower()
    for sev in Severity:
        if sev.value == text:
            return sev
    return Severity.INFO


def _coerce_source(raw: Any) -> IssueSource:
    if isinstance(raw, IssueSource):
        return raw
    text = str(raw or IssueSource.LLM_FIX.value).strip().lower()
    for src in IssueSource:
        if src.value == text:
            return src
    return IssueSource.LLM_FIX


def _parse_position(raw: Any, *, default_line: int = 0) -> Position:
    if isinstance(raw, Position):
        return raw
    if isinstance(raw, dict):
        line = int(raw.get("line", default_line))
        char = int(raw.get("character", raw.get("char", 0)))
        return Position(line=max(0, line), character=max(0, char))
    return Position(line=max(0, default_line), character=0)


def _parse_range(
    raw: Any,
    *,
    issue: Optional[DiagnosticIssue] = None,
) -> TextRange:
    """解析 range；缺省时由 issue 的 1-based 行推导 0-based range。"""
    if isinstance(raw, TextRange):
        return raw
    if isinstance(raw, dict) and ("start" in raw or "end" in raw):
        start = _parse_position(raw.get("start"), default_line=0)
        end = _parse_position(raw.get("end"), default_line=start.line)
        return TextRange(start=start, end=end)

    if issue is not None:
        line0 = max(0, issue.line - 1)
        col0 = max(0, issue.column)
        end_line = issue.end_line if issue.end_line is not None else issue.line
        end_col = issue.end_column if issue.end_column is not None else col0 + 1
        return TextRange(
            start=Position(line=line0, character=col0),
            end=Position(line=max(line0, end_line - 1), character=max(0, end_col)),
        )
    return TextRange(start=Position(line=0, character=0), end=Position(line=0, character=0))


def parse_llm_suggestion_json(
    text: Union[str, Dict[str, Any], None],
    *,
    issue: Optional[DiagnosticIssue] = None,
    default_file: Optional[str] = None,
) -> Optional[Suggestion]:
    """
    容错解析单条 Suggestion。

    接受：dict、JSON 字符串、或带 ```json 代码块的文本。
    """
    if text is None:
        return None
    data: Any = text
    if isinstance(text, str):
        stripped = text.strip()
        if not stripped:
            return None
        for candidate in (stripped, *_extract_json_candidates(stripped)):
            try:
                data = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        else:
            return None

    if not isinstance(data, dict):
        return None

    file_raw = data.get("file") or default_file or (issue.file if issue else "")
    file_norm = normalize_rel_path(str(file_raw)) if file_raw else ""
    if not file_norm:
        return None

    replacement = str(data.get("replacement", "") or "").strip()
    rationale_zh = str(data.get("rationale_zh", data.get("rationale", "")) or "").strip()
    if not replacement:
        return None

    issue_id = data.get("issue_id")
    if issue_id is None and issue is not None:
        issue_id = issue.id

    rng = _parse_range(data.get("range"), issue=issue)

    return Suggestion(
        request_id=str(data.get("request_id") or uuid.uuid4()),
        document_version=int(data.get("document_version") or 0),
        file=file_norm,
        range=rng,
        severity=_coerce_severity(data.get("severity")),
        source=_coerce_source(data.get("source")),
        message=str(data.get("message", "") or ""),
        replacement=replacement,
        confidence=_parse_confidence(data.get("confidence")),
        rationale_zh=str(data.get("rationale_zh", data.get("rationale", "")) or ""),
        issue_id=str(issue_id) if issue_id else None,
    )


def parse_polish_suggestion_json(
    text: Union[str, Dict[str, Any], None],
    *,
    default_file: Optional[str] = None,
) -> Optional[Suggestion]:
    """
    解析润色建议：允许 replacement 为空，只要有 rationale_zh 即可展示。
    """
    if text is None:
        return None
    data: Any = text
    if isinstance(text, str):
        stripped = text.strip()
        if not stripped:
            return None
        for candidate in (stripped, *_extract_json_candidates(stripped)):
            try:
                data = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        else:
            # 润色场景允许纯文本返回：将整段文本作为说明保存。
            file_norm = normalize_rel_path(str(default_file)) if default_file else ""
            if not file_norm:
                return None
            return Suggestion(
                file=file_norm,
                range=TextRange(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=0),
                ),
                severity=Severity.INFO,
                source=IssueSource.LLM_POLISH,
                message="",
                replacement="",
                rationale_zh=stripped,
                issue_id=None,
            )

    if not isinstance(data, dict):
        return None

    file_raw = data.get("file") or default_file
    file_norm = normalize_rel_path(str(file_raw)) if file_raw else ""
    if not file_norm:
        return None

    replacement = str(data.get("replacement", "") or "").strip()
    rationale_zh = str(data.get("rationale_zh", data.get("rationale", "")) or "").strip()
    if not replacement and not rationale_zh:
        return None

    rng = _parse_range(data.get("range"))

    return Suggestion(
        request_id=str(data.get("request_id") or uuid.uuid4()),
        document_version=int(data.get("document_version") or 0),
        file=file_norm,
        range=rng,
        severity=Severity.INFO,
        source=IssueSource.LLM_POLISH,
        message=str(data.get("message", "") or ""),
        replacement=replacement,
        confidence=_parse_confidence(data.get("confidence")),
        rationale_zh=rationale_zh,
        issue_id=None,
    )


def _parse_confidence(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        val = float(raw)
        if 0.0 <= val <= 1.0:
            return val
    except (TypeError, ValueError):
        pass
    return None


def _extract_json_candidates(text: str) -> List[str]:
    out: List[str] = []
    for m in _JSON_BLOCK_RE.finditer(text):
        block = m.group(1).strip()
        if block:
            out.append(block)
    # 第一个平衡 {...}
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    out.append(text[start : i + 1])
                    break
    return out


def parse_llm_suggestions_from_agent_result(
    raw: Any,
    *,
    issues_by_id: Optional[Dict[str, DiagnosticIssue]] = None,
) -> List[Suggestion]:
    """
    从 Agent 节点 result（字符串 / dict / 数组）提取 Suggestion 列表。
    """
    issues_by_id = issues_by_id or {}
    payloads = _unwrap_agent_payloads(raw)
    out: List[Suggestion] = []
    seen_issue: set[str] = set()

    for item in payloads:
        issue = None
        if isinstance(item, dict):
            iid = item.get("issue_id")
            if iid and str(iid) in issues_by_id:
                issue = issues_by_id[str(iid)]
        sug = parse_llm_suggestion_json(item, issue=issue)
        if sug is None:
            continue
        key = sug.issue_id or f"{sug.file}:{sug.range.start.line}"
        if key in seen_issue:
            continue
        seen_issue.add(key)
        out.append(sug)
    return out


def _unwrap_agent_payloads(raw: Any) -> List[Any]:
    """展开 Agent 标准包装 {result: ...} 或裸数组。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)

    if isinstance(raw, dict):
        if "result" in raw:
            return _unwrap_agent_payloads(raw.get("result"))
        return [raw]

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            return _unwrap_agent_payloads(parsed)
        except json.JSONDecodeError:
            one = parse_llm_suggestion_json(text)
            return [one.model_dump(mode="json")] if one else []

    return []


def suggestions_to_metadata(suggestions: List[Suggestion]) -> List[Dict[str, Any]]:
    from latex.serialize import to_dict

    return [to_dict(s) for s in suggestions]
