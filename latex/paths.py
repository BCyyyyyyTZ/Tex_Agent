"""
跨平台路径工具（Windows / Linux 统一使用 pathlib，对外 rel 路径为正斜杠）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


def normalize_rel_path(rel: str) -> str:
    """将用户输入的相对路径规范为 POSIX 风格（用于 ProjectIndex、JSON 输出）。"""
    text = (rel or "").strip().strip('"').strip("'")
    if not text:
        return ""
    normalized = text.replace("\\", "/")
    # 去掉开头的 / 或盘符前导（仅保留相对路径语义）
    while normalized.startswith("/"):
        normalized = normalized[1:]
    if len(normalized) >= 2 and normalized[1] == ":":
        # Windows 绝对路径 C:/foo -> foo（相对 root 时不应带盘符）
        normalized = normalized[2:].lstrip("/")
    parts = [p for p in normalized.split("/") if p and p != "."]
    return "/".join(parts)


def path_from_user_string(raw: str) -> Path:
    """
    将用户/API 传入的路径转为本机 Path（支持 ~/、盘符、UNC、POSIX）。
    """
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise ValueError("路径为空")
    return Path(text).expanduser()


def resolve_tex_file(
    *,
    path: Optional[str] = None,
    root: Optional[str] = None,
    rel_path: Optional[str] = None,
    base_dir: Optional[str | Path] = None,
) -> Tuple[Path, Optional[str]]:
    """
    解析待读取的 .tex 绝对路径，并尽量给出相对 root 的路径。

    优先级：
      1) path：绝对或相对 base_dir / 当前工作目录
      2) root + rel_path：项目根 + 相对 tex

    Returns:
        (absolute_path, rel_path_or_none)
    """
    root_path: Optional[Path] = None
    if root:
        root_path = path_from_user_string(str(root)).resolve()
        if not root_path.is_dir():
            raise NotADirectoryError(f"root 不是有效目录: {root_path}")

    if path:
        p = path_from_user_string(str(path))
        if not p.is_absolute() and base_dir is not None:
            p = Path(base_dir).resolve() / p
        elif not p.is_absolute() and root_path is not None:
            p = root_path / p
        elif not p.is_absolute():
            p = Path.cwd() / p
        resolved = p.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"找不到 tex 文件: {resolved}")
        rel: Optional[str] = None
        if root_path is not None:
            try:
                rel = resolved.relative_to(root_path).as_posix()
            except ValueError:
                pass
        return resolved, rel

    if root_path is not None and rel_path:
        norm = normalize_rel_path(str(rel_path))
        if not norm:
            raise ValueError("rel_path 为空")
        candidate = root_path / Path(norm)
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        resolved = candidate.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"找不到 tex 文件: {resolved}")
        try:
            rel = resolved.relative_to(root_path).as_posix()
        except ValueError:
            rel = norm
        return resolved, rel

    raise ValueError("需要提供 path，或同时提供 root 与 rel_path")
