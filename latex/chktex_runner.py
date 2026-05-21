"""
ChkTeX 子进程封装（阶段 3）：参数列表调用、超时、路径安全。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from latex.chktex_parser import parse_chktex_output
from latex.models import DiagnosticIssue
from latex.paths import normalize_rel_path
from latex.tex_env import TexEnvStatus, probe_tex_env


@dataclass
class ChkTeXRunResult:
    issues: List[DiagnosticIssue] = field(default_factory=list)
    env: TexEnvStatus = field(default_factory=probe_tex_env)
    warnings: List[str] = field(default_factory=list)
    files_checked: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


def resolve_target_files(
    root: Path,
    *,
    files: Optional[Sequence[str]] = None,
    main_tex: Optional[str] = None,
    all_project_tex: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    决定待检查的相对 tex 路径列表（POSIX）。

    优先级：显式 files[] > main_tex 单文件 > 项目全部 tex。
    """
    if files:
        out: List[str] = []
        for f in files:
            norm = normalize_rel_path(str(f))
            if norm and norm not in out:
                out.append(norm)
        return out

    if main_tex:
        norm = normalize_rel_path(str(main_tex))
        return [norm] if norm else []

    if all_project_tex:
        return sorted({normalize_rel_path(str(f)) for f in all_project_tex if f})

    return []


def run_chktex(
    root: Path,
    rel_files: Sequence[str],
    *,
    chktex_path: Optional[str] = None,
    timeout_per_file_sec: int = 30,
    env: Optional[TexEnvStatus] = None,
) -> ChkTeXRunResult:
    """
    对 root 下每个相对 tex 运行 chktex（-q -v0，便于解析）。

    无 chktex 时返回 success 语义的空 issues + warning chktex_not_found。
    """
    root = root.expanduser().resolve()
    status = env or probe_tex_env()
    exe = chktex_path or status.paths.get("chktex")
    if not exe:
        return ChkTeXRunResult(
            env=status,
            warnings=["chktex_not_found"],
        )

    all_issues: List[DiagnosticIssue] = []
    checked: List[str] = []
    stdout_parts: List[str] = []
    stderr_parts: List[str] = []
    run_warnings: List[str] = []

    for rel in rel_files:
        target = root / Path(rel)
        if not target.is_file():
            run_warnings.append(f"skip_missing_file:{rel}")
            continue

        argv = [exe, "-q", "-v0", "-n22", "-n30", rel]
        try:
            proc = subprocess.run(
                argv,
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_per_file_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            run_warnings.append(f"timeout:{rel}")
            continue
        except OSError as e:
            run_warnings.append(f"run_error:{rel}:{e}")
            continue

        checked.append(rel)
        stdout_parts.append(proc.stdout or "")
        stderr_parts.append(proc.stderr or "")
        combined = "\n".join(filter(None, [proc.stdout, proc.stderr]))
        all_issues.extend(
            parse_chktex_output(combined, root=root, default_file=rel)
        )

    return ChkTeXRunResult(
        issues=all_issues,
        env=status,
        warnings=run_warnings,
        files_checked=checked,
        stdout="\n".join(stdout_parts),
        stderr="\n".join(stderr_parts),
    )
