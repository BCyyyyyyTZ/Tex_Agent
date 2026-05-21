"""
TeX 外部工具环境探测（阶段 3）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, Optional

from pydantic import BaseModel, Field


class TexEnvStatus(BaseModel):
    """本机 TeX 相关可执行文件是否可用。"""

    chktex: bool = False
    latexmk: bool = False
    pdflatex: bool = False
    paths: Dict[str, str] = Field(default_factory=dict)


def _which(name: str) -> Optional[str]:
    path = shutil.which(name)
    if path:
        return path
    # Windows 常见 TeX Live 未加入 PATH 时的兜底名
    if os.name == "nt":
        for candidate in (f"{name}.exe", f"{name}.cmd"):
            path = shutil.which(candidate)
            if path:
                return path
    return None


def probe_tex_env() -> TexEnvStatus:
    """
    探测 chktex / latexmk / pdflatex 是否在 PATH 中可用。
    不执行编译，仅解析可执行路径。
    """
    names = ("chktex", "latexmk", "pdflatex")
    paths: Dict[str, str] = {}
    flags: Dict[str, bool] = {}
    for name in names:
        found = _which(name)
        flags[name] = bool(found)
        if found:
            paths[name] = found
    return TexEnvStatus(
        chktex=flags.get("chktex", False),
        latexmk=flags.get("latexmk", False),
        pdflatex=flags.get("pdflatex", False),
        paths=paths,
    )


def run_version_probe(executable: str, *, timeout: float = 5.0) -> str:
    """可选：读取 --version 首行（失败返回空串）。"""
    try:
        proc = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = (proc.stdout or proc.stderr or "").strip()
    return out.splitlines()[0] if out else ""
