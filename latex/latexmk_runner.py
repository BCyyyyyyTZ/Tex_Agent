"""
latexmk 子进程封装（阶段 4）。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from latex.log_parser import parse_latex_log, tail_log_text
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path
from latex.tex_env import TexEnvStatus, probe_tex_env


@dataclass
class LatexmkRunResult:
    issues: List[DiagnosticIssue] = field(default_factory=list)
    env: TexEnvStatus = field(default_factory=probe_tex_env)
    success: bool = False
    warnings: List[str] = field(default_factory=list)
    log_path: Optional[str] = None
    log_tail: str = ""
    stdout: str = ""
    stderr: str = ""


def build_latexmk_argv(
    main_tex: str,
    *,
    latexmk_path: str,
    mode: str = "fast",
) -> List[str]:
    """
    构造 latexmk 参数列表（禁止 shell 拼接）。

    fast: -draftmode；full: 完整 PDF（阶段 4 先实现 fast，full 同命令无 draft）。
    """
    argv = [
        latexmk_path,
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
    ]
    if mode != "full":
        argv.append("-draftmode")
    argv.append(main_tex)
    return argv


def resolve_log_path(root: Path, main_tex: str) -> Path:
    """根据 main.tex 推断 .log 路径（与 latexmk 默认 jobname 一致）。"""
    stem = Path(normalize_rel_path(main_tex)).stem
    return root / f"{stem}.log"


def run_latexmk(
    root: Path,
    main_tex: str,
    *,
    mode: str = "fast",
    latexmk_path: Optional[str] = None,
    timeout_sec: int = 120,
    env: Optional[TexEnvStatus] = None,
) -> LatexmkRunResult:
    """
    在 root 下对 main_tex 运行 latexmk，并解析生成的 .log。

    无 latexmk 时：success=True（工具层不失败）、warnings 含 latexmk_not_found。
    """
    root = root.expanduser().resolve()
    main_norm = normalize_rel_path(main_tex)
    if not main_norm:
        raise ValueError("main_tex 为空")

    main_path = root / Path(main_norm)
    if not main_path.is_file():
        raise FileNotFoundError(f"main_tex 不存在: {main_path}")

    status = env or probe_tex_env()
    exe = latexmk_path or status.paths.get("latexmk")
    if not exe:
        return LatexmkRunResult(
            env=status,
            success=True,
            warnings=["latexmk_not_found"],
        )

    argv = build_latexmk_argv(main_norm, latexmk_path=exe, mode=mode)
    run_warnings: List[str] = []
    stdout = ""
    stderr = ""

    try:
        proc = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        compile_ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        return LatexmkRunResult(
            env=status,
            success=False,
            warnings=["timeout"],
            stdout=stdout,
            stderr=stderr,
        )
    except OSError as e:
        return LatexmkRunResult(
            env=status,
            success=False,
            warnings=[f"run_error:{e}"],
            stdout=stdout,
            stderr=stderr,
        )

    log_path = resolve_log_path(root, main_norm)
    log_text = ""
    if log_path.is_file():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            run_warnings.append(f"log_read_error:{e}")
    else:
        run_warnings.append("log_not_found")
        # 部分发行版仅在 stdout 有摘要
        log_text = "\n".join(filter(None, [stdout, stderr]))

    issues = parse_latex_log(
        log_text,
        root=root,
        default_file=main_norm,
    )

    return LatexmkRunResult(
        issues=issues,
        env=status,
        success=compile_ok,
        warnings=run_warnings,
        log_path=log_path.relative_to(root).as_posix() if log_path.is_file() else None,
        log_tail=tail_log_text(log_text),
        stdout=stdout,
        stderr=stderr,
    )
