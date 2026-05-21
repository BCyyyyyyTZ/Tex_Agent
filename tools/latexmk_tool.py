"""
LatexmkTool：试编译 + log 诊断 L2（阶段 4）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from core.message import ToolResult
from latex.coerce_payload import coerce_json_payload
from latex.constants import METADATA_LATEX_DIAGNOSTICS
from latex.latexmk_runner import LatexmkRunResult, run_latexmk
from latex.paths import normalize_rel_path
from latex.project_index import build_project_index
from latex.serialize import to_dict
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_tool_input(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError(
            '输入为空。示例: {"root": "/path/to/project", "main_tex": "main.tex"}'
        )
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON 根类型必须是 object")
        return data
    return {"root": text}


class LatexmkTool(BaseTool):
    """
    使用 latexmk 试编译 LaTeX 项目并解析 .log 为 DiagnosticIssue。

    输入 JSON：
        - root（必填）
        - main_tex（必填，相对 root）
        - mode（可选）：fast | full，默认 fast
        - timeout（可选）：秒，默认 settings.latex_latexmk_fast_timeout_sec
    无 latexmk 时 success=True，issues=[]，warnings 含 latexmk_not_found。
    """

    def __init__(self) -> None:
        super().__init__(
            name="latexmk",
            description=(
                "latexmk 试编译并解析 log，返回编译错误与未定义引用/文献警告。"
                '输入 JSON：{"root": "...", "main_tex": "main.tex", "mode": "fast"}。'
            ),
            input_schema={
                "root": "必填，项目根目录",
                "main_tex": "必填，主 tex 相对路径",
                "mode": "可选，fast 或 full",
                "timeout": "可选，超时秒数",
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

            main_tex = payload.get("main_tex")
            if not main_tex or not str(main_tex).strip():
                # 尝试从项目索引推断唯一 main
                index = build_project_index(root, enrich=False)
                if index.main_tex:
                    main_tex = index.main_tex
                else:
                    return ToolResult(
                        success=False,
                        output="",
                        error="缺少 main_tex，且无法从项目启发式推断",
                    )
            main_tex = normalize_rel_path(str(main_tex))

            mode = str(payload.get("mode") or "fast").strip().lower()
            if mode not in ("fast", "full"):
                mode = "fast"

            if mode == "full":
                default_timeout = settings.latex_latexmk_full_timeout_sec
            else:
                default_timeout = settings.latex_latexmk_fast_timeout_sec
            timeout = payload.get("timeout", default_timeout)
            try:
                timeout = int(timeout)
            except (TypeError, ValueError):
                timeout = default_timeout

            result = run_latexmk(
                root,
                main_tex,
                mode=mode,
                timeout_sec=timeout,
            )
            body = _result_to_json_body(result)
            issues_dicts = [to_dict(i) for i in result.issues]

            return ToolResult(
                success=True,
                output=json.dumps(body, ensure_ascii=False, indent=2),
                metadata={
                    METADATA_LATEX_DIAGNOSTICS: issues_dicts,
                    "env": to_dict(result.env),
                    "compile_success": result.success,
                    "issue_count": len(result.issues),
                    "log_path": result.log_path,
                    "warnings": list(result.warnings),
                },
            )
        except (json.JSONDecodeError, ValueError, FileNotFoundError, OSError) as e:
            logger.warning("latexmk: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latexmk 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")


def _result_to_json_body(result: LatexmkRunResult) -> Dict[str, Any]:
    warnings = list(result.warnings)
    if not result.env.latexmk and "latexmk_not_found" not in warnings:
        warnings.insert(0, "latexmk_not_found")
    return {
        "issues": [to_dict(i) for i in result.issues],
        "success": result.success,
        "log_tail": result.log_tail,
        "log_path": result.log_path,
        "env": to_dict(result.env),
        "warnings": warnings,
    }
