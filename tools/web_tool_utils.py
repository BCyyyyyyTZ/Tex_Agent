"""Web 独立工具箱：输出目录与文件名工具。"""
from __future__ import annotations

import uuid
from pathlib import Path


def web_tool_output_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    d = root / "outputs" / "web_tool_outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def unique_output_path(prefix: str, ext: str = ".png") -> Path:
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    name = f"{prefix}_{uuid.uuid4().hex[:12]}{safe_ext}"
    return web_tool_output_dir() / name
