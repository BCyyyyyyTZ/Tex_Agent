"""
ChkTeXTool：LaTeX 静态诊断 L1（阶段 3）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.chktex_runner import ChkTeXRunResult, resolve_target_files, run_chktex
from latex.constants import METADATA_LATEX_DIAGNOSTICS
from latex.project_index import build_project_index
from latex.serialize import to_dict
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_tool_input(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError('输入为空。示例: {"root": "/path/to/project"}')
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON 根类型必须是 object")
        return data
    return {"root": text}


class ChkTeXTool(BaseTool):
    """
    对 LaTeX 项目运行 ChkTeX，返回 DiagnosticIssue 列表。

    输入 JSON：
        - root（必填）：项目根目录
        - main_tex（可选）：仅检查该文件
        - files（可选）：相对 root 的 tex 列表，优先于 main_tex
        - timeout（可选）：单文件超时秒数，默认 settings.latex_chktex_timeout_sec
    无 chktex 时 success=True，issues=[]，warnings 含 chktex_not_found。
    """

    def __init__(self) -> None:
        super().__init__(
            name="chktex",
            description=(
                "对 LaTeX 项目运行 ChkTeX 静态检查，返回 issues 与环境信息。"
                '输入 JSON：{"root": "...", "main_tex": "main.tex", "files": ["a.tex"]}。'
            ),
            input_schema={
                "root": "必填，项目根目录",
                "main_tex": "可选，仅检查主 tex",
                "files": "可选，待检查 tex 相对路径列表",
                "timeout": "可选，单文件超时（秒）",
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
            root_raw = payload.get("root")
            if not root_raw or not str(root_raw).strip():
                return ToolResult(success=False, output="", error="缺少必填字段 root")

            root = Path(str(root_raw)).expanduser().resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"root 不是有效目录: {root}",
                )

            main_tex: Optional[str] = payload.get("main_tex")
            if main_tex is not None:
                main_tex = str(main_tex).strip() or None

            files_payload = payload.get("files")
            explicit_files: Optional[List[str]] = None
            if files_payload is not None:
                if not isinstance(files_payload, list):
                    raise ValueError("files 必须是字符串数组")
                explicit_files = [str(f) for f in files_payload]

            timeout = payload.get("timeout", settings.latex_chktex_timeout_sec)
            try:
                timeout = int(timeout)
            except (TypeError, ValueError):
                timeout = settings.latex_chktex_timeout_sec

            all_tex: Optional[List[str]] = None
            if not explicit_files and not main_tex:
                index = build_project_index(root, main_tex=main_tex, enrich=False)
                all_tex = list(index.files.keys())

            rel_files = resolve_target_files(
                root,
                files=explicit_files,
                main_tex=main_tex,
                all_project_tex=all_tex,
            )
            if not rel_files:
                return ToolResult(
                    success=False,
                    output="",
                    error="未找到待检查的 .tex 文件",
                )

            result = run_chktex(
                root,
                rel_files,
                timeout_per_file_sec=timeout,
            )
            body = _result_to_json_body(result)
            issues_dicts = [to_dict(i) for i in result.issues]
            meta_warnings = list(result.warnings)
            if "chktex_not_found" in meta_warnings:
                pass
            elif not result.files_checked and not result.issues:
                meta_warnings.append("no_files_checked")

            return ToolResult(
                success=True,
                output=json.dumps(body, ensure_ascii=False, indent=2),
                metadata={
                    METADATA_LATEX_DIAGNOSTICS: issues_dicts,
                    "env": to_dict(result.env),
                    "issue_count": len(result.issues),
                    "files_checked": result.files_checked,
                    "warnings": meta_warnings,
                },
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning("chktex: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("chktex 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")


def _result_to_json_body(result: ChkTeXRunResult) -> Dict[str, Any]:
    from latex.serialize import to_dict as _to_dict

    env_dict = _to_dict(result.env)
    warnings = list(result.warnings)
    if not result.env.chktex and "chktex_not_found" not in warnings:
        warnings.insert(0, "chktex_not_found")
    return {
        "issues": [_to_dict(i) for i in result.issues],
        "env": env_dict,
        "warnings": warnings,
        "files_checked": result.files_checked,
    }
