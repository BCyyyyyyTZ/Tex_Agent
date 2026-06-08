"""
L3 修复 Prompt 组装（阶段 7）：issue + 切片 + 2.5 引用图上下文。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from latex.models import DiagnosticIssue, LabelDef, ProjectIndex, RefEntry
from latex.slice import IssueSlice
from latex.paths import normalize_rel_path, path_from_user_string
from latex.refs_index import iter_main_closure_files
from latex.slice import slice_around_issue

# 关联 \\ref 片段：单 issue 最多附带文件数、每文件最大行数
_MAX_REF_CONTEXT_FILES = 3
_REF_CONTEXT_LINES = 8
_REF_LINE_WINDOW = 25


def build_project_meta(index: Optional[ProjectIndex]) -> Dict[str, Any]:
    """供 Prompt / 工作流使用的项目摘要（含引用图子集）。"""
    if index is None:
        return {}
    closure = iter_main_closure_files(index)
    return {
        "root": index.root,
        "main_tex": index.main_tex,
        "file_count": len(index.files),
        "label_count": len(index.labels),
        "ref_count": len(index.refs),
        "main_closure_files": closure[:30],
        "bibliography_files": list(index.bibliography_files or [])[:10],
    }


def _refs_near_issue(
    index: ProjectIndex,
    issue: DiagnosticIssue,
    *,
    line_window: int = _REF_LINE_WINDOW,
) -> List[RefEntry]:
    """issue 所在文件、行号附近的 \\ref / \\cite 引用。"""
    rel = normalize_rel_path(issue.file)
    center = issue.line
    out: List[RefEntry] = []
    for ref in index.refs:
        if ref.kind != "ref":
            continue
        if normalize_rel_path(ref.file) != rel:
            continue
        if abs(ref.line - center) <= line_window:
            out.append(ref)
    return out


def _read_snippet(
    root: Path,
    rel_path: str,
    center_line: int,
    *,
    context_lines: int = _REF_CONTEXT_LINES,
) -> str:
    rel = normalize_rel_path(rel_path)
    tex_path = root / Path(rel)
    if not tex_path.is_file():
        return ""
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return ""
    center = max(1, min(center_line, len(lines)))
    start = max(1, center - context_lines)
    end = min(len(lines), center + context_lines)
    numbered = [f"{i}: {lines[i - 1]}" for i in range(start, end + 1)]
    return "\n".join(numbered)


def collect_ref_context_snippets(
    issue: DiagnosticIssue,
    index: Optional[ProjectIndex],
    *,
    root: Union[str, Path, None] = None,
    max_files: int = _MAX_REF_CONTEXT_FILES,
) -> List[Dict[str, str]]:
    """
    2.5 引用图：issue 附近 \\ref 所指向 \\label 定义处片段（跨文件脏区级联 MVP）。
    """
    if index is None or not index.labels:
        return []
    root_path = path_from_user_string(str(root or index.root)).resolve()
    near_refs = _refs_near_issue(index, issue)
    seen_keys: set[str] = set()
    snippets: List[Dict[str, str]] = []

    for ref in near_refs:
        if ref.key in seen_keys:
            continue
        label = index.labels.get(ref.key)
        if label is None:
            continue
        seen_keys.add(ref.key)
        rel = normalize_rel_path(label.defined_in)
        body = _read_snippet(root_path, rel, label.line)
        if not body:
            continue
        snippets.append(
            {
                "ref_key": ref.key,
                "defined_in": rel,
                "label_line": str(label.line),
                "snippet": body,
            }
        )
        if len(snippets) >= max_files:
            break
    return snippets


def build_fix_prompt(
    issue: DiagnosticIssue,
    snippet: str,
    project_meta: Optional[Dict[str, Any]] = None,
    *,
    index: Optional[ProjectIndex] = None,
    ref_contexts: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    为单条 error 级 issue 生成 LLM 修复提示（纯文本，由 Agent 消费）。

    project_meta 通常来自 build_project_meta；ref_contexts 可显式传入或由 index 推导。
    """
    meta = project_meta or {}
    if ref_contexts is None and index is not None:
        ref_contexts = collect_ref_context_snippets(
            issue, index, root=meta.get("root") or (index.root if index else None)
        )
    ref_contexts = ref_contexts or []

    lines: List[str] = [
        "你是 LaTeX 编译修复专家。仅针对下方【报错片段】给出可编译的局部修改。",
        "输出将由下游解析为 Suggestion JSON（见任务说明），不要输出 Markdown 代码块包裹。",
        "",
        "【项目】",
        f"- root: {meta.get('root', '')}",
        f"- main_tex: {meta.get('main_tex', '')}",
        f"- 闭包内 tex 数: {meta.get('file_count', '')}",
        "",
        "【报错】",
        f"- issue_id: {issue.id}",
        f"- file: {issue.file}",
        f"- line: {issue.line}, column: {issue.column}",
        f"- source: {issue.source.value}, code: {issue.code}",
        f"- severity: {issue.severity.value}",
        f"- message: {issue.message}",
        "",
        "【片段】（1-based 行号，含上下文）",
        snippet or "（空）",
    ]

    if ref_contexts:
        lines.append("")
        lines.append("【关联引用定义】（修改片段时请保持 label/ref 一致）")
        for ctx in ref_contexts:
            lines.append(
                f"\\ref{{{ctx.get('ref_key', '')}}} 定义于 {ctx.get('defined_in', '')}:"
                f"{ctx.get('label_line', '')}"
            )
            lines.append(ctx.get("snippet", ""))

    lines.extend(
        [
            "",
            "【任务】",
            "返回 1 个 JSON 对象（Suggestion），字段：",
            "file, range.start/end (0-based line/character), replacement, message, rationale_zh, issue_id。",
            "replacement 必须是可替换 range 内内容的合法 LaTeX；不要改写无关章节。",
        ]
    )
    return "\n".join(lines)


def build_fix_prompt_from_slice(
    issue: DiagnosticIssue,
    issue_slice: IssueSlice,
    project_meta: Optional[Dict[str, Any]] = None,
    *,
    index: Optional[ProjectIndex] = None,
) -> str:
    """从 IssueSlice 组装 prompt（snippet 优先用切片内容）。"""
    return build_fix_prompt(
        issue,
        issue_slice.snippet,
        project_meta,
        index=index,
    )


def ensure_slice_for_issue(
    issue: DiagnosticIssue,
    *,
    root: Union[str, Path],
    context_lines: int = 10,
) -> IssueSlice:
    """无现成切片时按 issue 现场切片（测试 / 工具兜底）。"""
    return slice_around_issue(issue, root=root, context_lines=context_lines)
