"""
单次工作流运行的节点 I/O 落盘（便于核对逻辑，非全量审计日志）。
目录由 core.agent_cli 在 invoke 前创建并写入 metadata['__run_output_dir__']。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# 仅用于人工核对，截断避免单文件过大
DEFAULT_INPUT_MAX = 12_000
DEFAULT_OUTPUT_RAW_MAX = 8_000
DEFAULT_STRUCTURED_RESULT_MAX = 6_000


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def create_run_output_dir() -> Path:
    """创建 output/YYYYmmdd_HHMMSS/ 并返回绝对路径。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = project_root() / "output" / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_node_slug(node_id: str) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "_" for c in (node_id or "node"))
    return (s or "node")[:120]


def _trunc(text: str, max_len: int) -> str:
    if max_len <= 0 or len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n... [已截断，原长度 {len(text)} 字符]\n"


def write_node_trace(
    run_dir: Optional[str],
    node_id: str,
    prompt: str,
    *,
    raw_response: Optional[str] = None,
    structured: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    input_max: int = DEFAULT_INPUT_MAX,
    raw_max: int = DEFAULT_OUTPUT_RAW_MAX,
    result_max: int = DEFAULT_STRUCTURED_RESULT_MAX,
) -> None:
    """
    将节点输入 / 输出写入 run_dir（每个节点一对文件，内容已截断）。
    run_dir 为空或路径无效时静默跳过。
    """
    if not run_dir:
        return
    base = Path(run_dir)
    if not base.is_dir():
        return
    slug = _safe_node_slug(node_id)
    try:
        inp_path = base / f"{slug}_input.txt"
        out_path = base / f"{slug}_output.txt"
        inp_path.write_text(_trunc(prompt, input_max), encoding="utf-8")

        parts: list[str] = []
        if error:
            parts.append(f"[error]\n{error}")
        if raw_response is not None:
            parts.append(f"[raw_response]\n{_trunc(raw_response, raw_max)}")
        if structured is not None:
            view = {
                "summary": structured.get("summary"),
                "confidence": structured.get("confidence"),
                "result": _trunc(str(structured.get("result", "")), result_max),
                "metadata": structured.get("metadata"),
            }
            parts.append("[parsed_json_fields]\n" + json.dumps(view, ensure_ascii=False, indent=2))
        body = "\n\n".join(parts) if parts else "(无输出)"
        out_path.write_text(body, encoding="utf-8")
    except OSError as e:
        logger.warning(f"节点 I/O 落盘失败 [{node_id}]: {e}")
