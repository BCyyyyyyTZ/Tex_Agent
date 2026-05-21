"""
LatexProjectTool：扫描 LaTeX 项目目录，构建 ProjectIndex（阶段 1）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.message import ToolResult
from latex.constants import METADATA_LATEX_PROJECT
from latex.coerce_payload import coerce_json_payload
from latex.project_index import build_project_index
from latex.serialize import to_dict, to_json
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_tool_input(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("输入为空，需要 JSON，例如 {\"root\": \"/path/to/project\"}")
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON 根类型必须是 object")
        return data
    # 兼容：仅传入目录路径字符串
    return {"root": text}


class LatexProjectTool(BaseTool):
    """
    扫描 LaTeX 项目根目录，返回文件依赖图与 main.tex 候选。

    输入 JSON：
        - root（必填）：项目根目录绝对或相对路径
        - main_tex（可选）：显式指定主文件，相对 root
        - max_depth（可选）：扫描深度，默认 8
    """

    def __init__(self) -> None:
        super().__init__(
            name="latex_project",
            description=(
                "扫描 LaTeX 项目目录，构建文件依赖图、checksum 与 main.tex 候选。"
                "输入 JSON：{\"root\": \"...\", \"main_tex\": \"main.tex\"（可选）}。"
            ),
            input_schema={
                "root": "必填，LaTeX 项目根目录路径",
                "main_tex": "可选，主 tex 文件相对路径",
                "max_depth": "可选，扫描最大目录深度，默认 8",
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
                payload = coerce_json_payload(payload, input=input, **kwargs)
                input = json.dumps(payload, ensure_ascii=False)
            payload = _parse_tool_input(input)
            root = payload.get("root")
            if not root or not str(root).strip():
                return ToolResult(
                    success=False,
                    output="",
                    error="缺少必填字段 root",
                )

            main_tex: Optional[str] = payload.get("main_tex")
            if main_tex is not None:
                main_tex = str(main_tex).strip() or None

            max_depth = payload.get("max_depth", 8)
            try:
                max_depth = int(max_depth)
            except (TypeError, ValueError):
                max_depth = 8

            index = build_project_index(
                Path(str(root)),
                main_tex=main_tex,
                max_depth=max_depth,
            )
            project_dict = to_dict(index)
            return ToolResult(
                success=True,
                output=to_json(index),
                metadata={
                    METADATA_LATEX_PROJECT: project_dict,
                    "main_tex": index.main_tex,
                },
            )
        except FileNotFoundError as e:
            logger.warning("latex_project: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except (json.JSONDecodeError, ValueError, NotADirectoryError, OSError) as e:
            logger.warning("latex_project: %s", e)
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("latex_project 未预期错误")
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")
