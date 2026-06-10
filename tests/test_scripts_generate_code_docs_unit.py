"""
scripts.generate_code_docs 的单元测试。

目标：
1) 验证 AST 解析与文档渲染的关键行为（签名格式化、docstring 摘要）；
2) 验证“按相同目录结构输出 md”的映射规则；
3) 不修改真实仓库内容，全部在 tmp_path 中构造最小样例工程。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from importlib.util import module_from_spec, spec_from_file_location
import sys


def _load_generate_code_docs_module():
    """
    通过文件路径加载 scripts/generate_code_docs.py（scripts 目录不要求是 Python 包）。
    """
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "scripts" / "generate_code_docs.py"
    spec = spec_from_file_location("_tex_agent_generate_code_docs", str(path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


gen = _load_generate_code_docs_module()


def test_format_signature_handles_common_forms() -> None:
    """
    _format_signature 是文档可读性的关键：
    - 支持 posonly / defaults / *args / kwonly / **kwargs；
    - 默认值使用 ... 占位，避免把复杂对象写入文档。
    """
    # 这里用尽量短且“语法稳定”的源码片段，避免转义引入解析歧义。
    src = (
        "def f(a, b=1, *args, c, d=2, **kwargs):\n"
        "    return a\n"
    )
    mod = __import__("ast").parse(src)
    fn = next(n for n in mod.body if isinstance(n, __import__("ast").FunctionDef))
    sig = gen._format_signature(fn)
    assert sig.startswith("(") and sig.endswith(")")
    assert "b=..." in sig
    assert "*args" in sig
    assert "d=..." in sig
    assert "**kwargs" in sig


def test_collect_module_doc_and_render_markdown(tmp_path: Path) -> None:
    """
    从一个最小 py 文件生成 ModuleDoc，并渲染 Markdown：
    - 包含模块说明；
    - 包含类与方法概览；
    - 包含顶层函数概览。
    """
    py = tmp_path / "m.py"
    py.write_text(
        '"""module doc\n\nmore\n"""\n\n'
        "def f(x):\n"
        '    """func doc."""\n'
        "    return x\n\n"
        "class C:\n"
        '    """class doc."""\n'
        "    def m(self, y):\n"
        '        """method doc."""\n'
        "        return y\n",
        encoding="utf-8",
    )
    doc = gen._collect_module_doc(py)
    md = gen._render_markdown("m.py", doc)
    assert "## 模块说明" in md
    assert "module doc" in md
    assert "### 类" in md and "`C`" in md
    assert "### 函数" in md and "`f(" in md
    assert "method doc" in md


def test_generate_docs_for_dir_keeps_structure(tmp_path: Path) -> None:
    """
    端到端验证（在临时目录中）：
    - src_rel 目录下的子路径应在 doc/ 下镜像；
    - 每个 py 对应一个 md；
    - 写出文件为 UTF-8。
    """
    repo = tmp_path / "repo"
    src = repo / "agents"
    (src / "specified_agents").mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text('"""pkg"""', encoding="utf-8")
    (src / "specified_agents" / "a.py").write_text('"""m"""\n\nclass A: ...\n', encoding="utf-8")

    n_py, n_written = gen.generate_docs_for_dir(repo_root=repo, src_rel="agents")
    assert n_py == 2
    assert n_written == 2

    # 镜像结构：agents/doc/specified_agents/a.md
    md = repo / "agents" / "doc" / "specified_agents" / "a.md"
    assert md.exists()
    assert "a.py" in md.read_text(encoding="utf-8")
