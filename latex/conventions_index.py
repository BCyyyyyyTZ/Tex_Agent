"""
项目级 LaTeX 写作约定：导言区宏、版式、算法环境约定（阶段 2.7）。

不展开完整 TeX 宏，只提取「定义 + 用法统计 + 可读语义提示」，供 Agent / 润色理解项目方言。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from latex.models import (
    AlgorithmConvention,
    MacroDef,
    ProjectConventions,
    ProjectIndex,
)
from latex.refs_index import iter_main_closure_files
from latex.tex_source import read_tex_file, strip_inline_comment

_DOCUMENTCLASS_RE = re.compile(
    r"\\documentclass(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_DOCUMENTCLASS_OPT_RE = re.compile(
    r"\\documentclass\[([^\]]*)\]",
    re.IGNORECASE,
)
_USEPACKAGE_RE = re.compile(
    r"\\usepackage(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_NEWCOMMAND_RE = re.compile(
    r"\\newcommand\*?(?:\[[^\]]*\])?\s*\{?\\?([A-Za-z@]+)\}?"
    r"(?:\[[^\]]*\])?\s*(\{)?",
    re.IGNORECASE,
)
_RENEWCOMMAND_BRACED_RE = re.compile(
    r"\\renewcommand\*?(?:\[[^\]]*\])?\s*\{?\\?([A-Za-z@]+)\}?",
    re.IGNORECASE,
)
_RENEWCOMMAND_PLAIN_RE = re.compile(
    r"\\renewcommand\s*\\?([A-Za-z@]+)",
    re.IGNORECASE,
)
_NEWTHEOREM_RE = re.compile(
    r"\\newtheorem\*?\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_DEFINECOLOR_RE = re.compile(
    r"\\definecolor\{([^}]+)\}\s*\{([^}]+)\}\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_CAPTION_SETUP_RE = re.compile(
    r"\\captionsetup\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}",
    re.IGNORECASE,
)

# 常见「缩写宏」的静态语义提示（非 TeX 展开，仅供理解）
_SEMANTIC_HINTS: Dict[str, str] = {
    "name": "项目名 VaLoRA（带 xspace 尾随空格）",
    "ie": "展开为斜体 i.e.,",
    "eg": "展开为斜体 e.g.,",
    "vs": "展开为斜体 v.s.",
    "aka": "展开为斜体 a.k.a.,",
    "etc": "展开为斜体 etc.",
    "presec": "节标题前负向垂直间距",
    "postsec": "节标题后负向垂直间距",
    "ent": "段落间额外垂直间距",
    "tb": "textcolor{black}{...} 强调（保持黑色）",
    "tr": "textcolor{black}{...}",
    "hide": "审稿隐藏：参数被吞掉",
    "mnote": "审稿批注（红色角标）",
    "jnote": "审稿批注（蓝色角标）",
    "wnote": "审稿批注（紫色角标）",
    "snote": "好句标注（红色）",
    "reviewer": "审稿人标签（粉色）",
}


def _active_lines(source: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for line_no, raw in enumerate(source.splitlines(), start=1):
        line = strip_inline_comment(raw).strip()
        if line:
            out.append((line_no, line))
    return out


def _truncate_def(text: str, *, max_len: int = 120) -> str:
    t = " ".join(text.split())
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


def _extract_braced_arg(line: str, command: str) -> str:
    """提取 \\command{...} 的第一层花括号内容（支持一层嵌套）。"""
    m = re.search(
        rf"\\{re.escape(command)}\s*\{{((?:[^{{}}]|\{{[^{{}}]*\}})*)\}}",
        line,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _unwrap_text_formatting(text: str) -> str:
    """去掉 \\textbf{...} 等简单包装，保留可读标签。"""
    inner = text.strip()
    for _ in range(3):
        m = re.match(r"\\textbf\{([^}]*)\}", inner, re.IGNORECASE)
        if not m:
            break
        inner = m.group(1).strip()
    return inner


def _arity_from_optional_arg(line: str, macro: str) -> int:
    """\\newcommand{\\foo}[2] 形式。"""
    m = re.search(
        rf"\\newcommand\*?(?:\[[^\]]*\])?\s*\{{\\?{re.escape(macro)}\}}\s*\[(\d+)\]",
        line,
        re.IGNORECASE,
    )
    if m:
        return int(m.group(1))
    return 0


def _extract_definition_tail(line: str, macro: str) -> str:
    """取宏定义行中命令名后的片段（启发式）。"""
    idx = line.lower().find(macro.lower())
    if idx < 0:
        return _truncate_def(line)
    tail = line[idx + len(macro) :].lstrip("{}[]")
    return _truncate_def(tail) if tail else _truncate_def(line)


def parse_preamble(
    source: str,
    *,
    defined_in: str = "paper.tex",
) -> ProjectConventions:
    """从导言区（\\begin{document} 之前）提取约定。"""
    end = source.find("\\begin{document}")
    preamble = source[:end] if end >= 0 else source

    documentclass = ""
    documentclass_options: List[str] = []
    packages: List[str] = []
    macro_defs: Dict[str, MacroDef] = {}
    colors: Dict[str, str] = {}
    theorem_environments: List[str] = []
    caption_setups: List[str] = []
    algorithm: Optional[AlgorithmConvention] = None

    pkg_seen: Set[str] = set()
    for line_no, line in _active_lines(preamble):
        for m in _DOCUMENTCLASS_RE.finditer(line):
            documentclass = m.group(1).strip()
            opt = _DOCUMENTCLASS_OPT_RE.search(line)
            if opt:
                documentclass_options = [
                    o.strip() for o in opt.group(1).split(",") if o.strip()
                ]

        for m in _USEPACKAGE_RE.finditer(line):
            for token in m.group(1).split(","):
                pkg = token.strip()
                if pkg and pkg not in pkg_seen:
                    pkg_seen.add(pkg)
                    packages.append(pkg)

        for m in _NEWCOMMAND_RE.finditer(line):
            name = m.group(1)
            if not name or name in macro_defs:
                continue
            macro_defs[name] = MacroDef(
                name=name,
                kind="newcommand",
                arity=_arity_from_optional_arg(line, name),
                definition=_extract_definition_tail(line, name),
                expands_to_hint=_SEMANTIC_HINTS.get(name, ""),
                defined_in=defined_in,
                line=line_no,
            )

        for pat, kind in (
            (_RENEWCOMMAND_BRACED_RE, "renewcommand"),
            (_RENEWCOMMAND_PLAIN_RE, "renewcommand"),
        ):
            for m in pat.finditer(line):
                name = m.group(1)
                if not name:
                    continue
                macro_defs[name] = MacroDef(
                    name=name,
                    kind=kind,
                    definition=_extract_definition_tail(line, name),
                    expands_to_hint=_SEMANTIC_HINTS.get(name, ""),
                    defined_in=defined_in,
                    line=line_no,
                )

        for m in _NEWTHEOREM_RE.finditer(line):
            env = m.group(1).strip()
            if env and env not in theorem_environments:
                theorem_environments.append(env)
            macro_defs[env] = MacroDef(
                name=env,
                kind="newtheorem",
                definition=f"\\begin{{{env}}} ... \\end{{{env}}}",
                expands_to_hint=f"定理类环境 {env}",
                defined_in=defined_in,
                line=line_no,
            )

        for m in _DEFINECOLOR_RE.finditer(line):
            colors[m.group(1).strip()] = f"{m.group(2)}:{m.group(3)}"

        cap = _CAPTION_SETUP_RE.search(line)
        if cap:
            caption_setups.append(cap.group(1).strip())

        if "\\algorithmicrequire" in line or "\\algorithmicensure" in line:
            algo = algorithm or AlgorithmConvention()
            if "algorithmicrequire" in line.lower():
                raw = _extract_braced_arg(line, "algorithmicrequire")
                if raw:
                    algo.require_label = _unwrap_text_formatting(raw)
            if "algorithmicensure" in line.lower():
                raw = _extract_braced_arg(line, "algorithmicensure")
                if raw:
                    algo.ensure_label = _unwrap_text_formatting(raw)
            algorithm = algo

    if algorithm is None and any(p in packages for p in ("algorithm", "algpseudocode", "algorithm2e")):
        algorithm = AlgorithmConvention(
            packages=[p for p in ("algorithm", "algpseudocode") if p in packages]
        )

    return ProjectConventions(
        documentclass=documentclass,
        documentclass_options=documentclass_options,
        packages=packages,
        macro_defs=macro_defs,
        colors=colors,
        theorem_environments=theorem_environments,
        caption_setups=caption_setups,
        algorithm=algorithm,
    )


def scan_macro_usage(
    index: ProjectIndex,
    macro_names: Iterable[str],
    *,
    scope: str = "main_closure",
) -> Dict[str, int]:
    """统计项目宏在正文中的出现次数。"""
    root = Path(index.root)
    if scope == "all":
        rel_files = sorted(index.files.keys())
    else:
        rel_files = iter_main_closure_files(index)

    names = sorted({n for n in macro_names if n})
    if not names:
        return {}

    patterns = {
        n: re.compile(rf"\\{re.escape(n)}(?![A-Za-z@])") for n in names
    }
    counts: Dict[str, int] = {n: 0 for n in names}

    for rel in rel_files:
        full = root / rel
        if not full.is_file():
            continue
        try:
            text = read_tex_file(full)
        except OSError:
            continue
        body = text
        doc_start = text.find("\\begin{document}")
        if doc_start >= 0:
            body = text[doc_start:]
        for name, pat in patterns.items():
            counts[name] += len(pat.findall(body))

    return {k: v for k, v in counts.items() if v > 0}


def scan_local_typography(index: ProjectIndex) -> List[Dict[str, object]]:
    """文件内局部版式（如 figure 上的 \\setlength）。"""
    root = Path(index.root)
    entries: List[Dict[str, object]] = []
    pat = re.compile(r"\\setlength\s*\{\\([^}]+)\}\s*\{([^}]+)\}")
    for rel in iter_main_closure_files(index):
        full = root / rel
        if not full.is_file():
            continue
        try:
            text = read_tex_file(full)
        except OSError:
            continue
        for line_no, raw in enumerate(text.splitlines(), start=1):
            line = strip_inline_comment(raw)
            for m in pat.finditer(line):
                entries.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "parameter": m.group(1),
                        "value": m.group(2),
                    }
                )
    return entries


def build_conventions(index: ProjectIndex) -> ProjectConventions:
    """合并导言区定义与正文用法。"""
    root = Path(index.root)
    conv = ProjectConventions()

    if index.main_tex:
        main_path = root / index.main_tex
        if main_path.is_file():
            try:
                conv = parse_preamble(
                    read_tex_file(main_path),
                    defined_in=index.main_tex,
                )
            except OSError:
                pass

    usage_names = [
        n
        for n, m in conv.macro_defs.items()
        if m.kind in ("newcommand", "newtheorem")
    ]
    usage = scan_macro_usage(index, usage_names)
    conv.macro_usage = usage
    conv.local_typography = scan_local_typography(index)
    return conv


def enrich_conventions(index: ProjectIndex) -> ProjectIndex:
    """填充 ProjectIndex.conventions。"""
    return index.model_copy(update={"conventions": build_conventions(index)})
