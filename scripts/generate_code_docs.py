from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionDoc:
    name: str
    signature: str
    doc: str


@dataclass(frozen=True)
class ClassDoc:
    name: str
    doc: str
    methods: list[FunctionDoc]


@dataclass(frozen=True)
class ModuleDoc:
    module_doc: str
    classes: list[ClassDoc]
    functions: list[FunctionDoc]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="utf-8", errors="replace")


def _one_line(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    return t.splitlines()[0].strip()


def _format_signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "()"

    a = node.args
    parts: list[str] = []

    def _fmt_arg(arg: ast.arg) -> str:
        return arg.arg

    posonly = [_fmt_arg(x) for x in getattr(a, "posonlyargs", [])]
    args = [_fmt_arg(x) for x in a.args]
    kwonly = [_fmt_arg(x) for x in a.kwonlyargs]

    defaults_count = len(a.defaults)
    if defaults_count:
        for i in range(1, defaults_count + 1):
            idx = len(args) - i
            if 0 <= idx < len(args):
                args[idx] = args[idx] + "=..."

    if posonly:
        parts.extend(posonly)
        parts.append("/")
    parts.extend(args)

    if a.vararg is not None:
        parts.append("*" + _fmt_arg(a.vararg))
    elif kwonly:
        parts.append("*")

    kw_defaults_count = len(a.kw_defaults)
    if kwonly:
        for i, n in enumerate(kwonly):
            if i < kw_defaults_count and a.kw_defaults[i] is not None:
                kwonly[i] = n + "=..."
        parts.extend(kwonly)

    if a.kwarg is not None:
        parts.append("**" + _fmt_arg(a.kwarg))

    return "(" + ", ".join(parts) + ")"


def _collect_module_doc(py_path: Path) -> ModuleDoc:
    src = _read_text(py_path)
    mod = ast.parse(src, filename=str(py_path))

    module_doc = ast.get_docstring(mod) or ""
    classes: list[ClassDoc] = []
    functions: list[FunctionDoc] = []

    for item in mod.body:
        if isinstance(item, ast.ClassDef):
            c_doc = ast.get_docstring(item) or ""
            methods: list[FunctionDoc] = []
            for c_item in item.body:
                if isinstance(c_item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = _format_signature(c_item)
                    methods.append(
                        FunctionDoc(
                            name=c_item.name,
                            signature=sig,
                            doc=ast.get_docstring(c_item) or "",
                        )
                    )
            classes.append(ClassDoc(name=item.name, doc=c_doc, methods=methods))
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _format_signature(item)
            functions.append(FunctionDoc(name=item.name, signature=sig, doc=ast.get_docstring(item) or ""))

    return ModuleDoc(module_doc=module_doc, classes=classes, functions=functions)


def _render_markdown(rel_py: str, doc: ModuleDoc) -> str:
    lines: list[str] = []
    lines.append(f"# {rel_py}")
    lines.append("")

    lines.append("## 模块说明")
    lines.append("")
    lines.append((doc.module_doc or "").strip() or "（无）")
    lines.append("")

    lines.append("## API 概览")
    lines.append("")

    if not doc.classes and not doc.functions:
        lines.append("（无公开类/函数）")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    if doc.classes:
        lines.append("### 类")
        lines.append("")
        for c in doc.classes:
            lines.append(f"- `{c.name}`：{_one_line(c.doc) or '（无）'}")
        lines.append("")

    if doc.functions:
        lines.append("### 函数")
        lines.append("")
        for f in doc.functions:
            lines.append(f"- `{f.name}{f.signature}`：{_one_line(f.doc) or '（无）'}")
        lines.append("")

    if doc.classes:
        lines.append("## 类与方法")
        lines.append("")
        for c in doc.classes:
            lines.append(f"### {c.name}")
            lines.append("")
            lines.append((_one_line(c.doc) or "（无）").strip())
            lines.append("")
            if c.methods:
                lines.append("方法：")
                lines.append("")
                for m in c.methods:
                    lines.append(f"- `{m.name}{m.signature}`：{_one_line(m.doc) or '（无）'}")
                lines.append("")
            else:
                lines.append("方法：无")
                lines.append("")

    if doc.functions:
        lines.append("## 函数")
        lines.append("")
        for f in doc.functions:
            lines.append(f"### {f.name}{f.signature}")
            lines.append("")
            lines.append((_one_line(f.doc) or "（无）").strip())
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _iter_py_files(src_dir: Path) -> list[Path]:
    out: list[Path] = []
    for p in src_dir.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if "doc" in p.parts and p.parent.name == "doc":
            continue
        out.append(p)
    return sorted(out)


def generate_docs_for_dir(repo_root: Path, src_rel: str) -> tuple[int, int]:
    src_dir = (repo_root / src_rel).resolve()
    doc_dir = (src_dir / "doc").resolve()
    doc_dir.mkdir(parents=True, exist_ok=True)

    py_files = _iter_py_files(src_dir)
    written = 0
    for py in py_files:
        rel_py = py.relative_to(src_dir).as_posix()
        rel_md = str(Path(rel_py).with_suffix(".md"))
        md_path = (doc_dir / rel_md).resolve()
        md_path.parent.mkdir(parents=True, exist_ok=True)

        module_doc = _collect_module_doc(py)
        md = _render_markdown(rel_py, module_doc)
        md_path.write_text(md, encoding="utf-8")
        written += 1

    return len(py_files), written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate code docs for agents/tools/workflow_engine.")
    parser.add_argument("--repo", type=str, default=str(Path(__file__).resolve().parents[1]), help="Repo root path")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    targets = ["agents", "tools", "workflow_engine"]

    total_py = 0
    total_written = 0
    for t in targets:
        n_py, n_written = generate_docs_for_dir(repo_root, t)
        total_py += n_py
        total_written += n_written

    print(f"generated_docs: {total_written} (source_py: {total_py})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

