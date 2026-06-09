"""
tools.latex_autofix_tool 的测试。

覆盖点：
1) 编译错误解析：_extract_first_error 可从典型日志片段提取 message/file/line/context/raw；
2) 规则修复：_escape_underscores_on_line、_deterministic_fix（插入 usepackage、转义下划线）；
3) 多处替换：_apply_llm_edits_to_file 的区间替换与写回行为；
4) 运行入口：run() 在最小 LaTeX 项目上的行为（若环境具备编译器则应成功，否则应给出明确失败原因）。
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.latex_autofix_tool import LatexAutoFixTool, LatexError


def test_extract_first_error_parses_common_patterns() -> None:
    tool = LatexAutoFixTool(use_llm=False)
    log = "\n".join(
        [
            "main.tex:12: Undefined control sequence.",
            "! Undefined control sequence.",
            "l.12 \\includegraphics{a.png}",
            "Some other lines",
        ]
    )
    err = tool._extract_first_error(log)
    assert "Undefined control sequence" in err.message
    assert err.file.endswith("main.tex")
    assert err.line == 12
    assert "\\includegraphics" in err.context
    assert "!" in err.raw


def test_escape_underscores_on_line_respects_known_exclusions() -> None:
    tool = LatexAutoFixTool(use_llm=False)

    changed, out = tool._escape_underscores_on_line("a_b\n")
    assert changed is True
    assert "a\\_b" in out

    changed2, out2 = tool._escape_underscores_on_line("$a_b$\n")
    assert changed2 is False
    assert out2 == "$a_b$\n"

    changed3, out3 = tool._escape_underscores_on_line("\\url{a_b}\n")
    assert changed3 is False
    assert out3 == "\\url{a_b}\n"


def test_deterministic_fix_inserts_package_into_preamble(tmp_path: Path) -> None:
    tool = LatexAutoFixTool(use_llm=False)
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    main = work_dir / "main.tex"
    main.write_text(
        "\n".join(
            [
                "\\documentclass{article}",
                "\\begin{document}",
                "x",
                "\\end{document}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    err = LatexError(
        message="Undefined control sequence",
        file="main.tex",
        line=2,
        context="\\includegraphics{a.png}",
        raw="! Undefined control sequence.\nl.2 \\includegraphics{a.png}",
    )
    state = {"engine": "auto", "shell_escape": False}
    action = tool._deterministic_fix(err=err, work_dir=work_dir, main_tex=main, state=state)
    assert isinstance(action, dict)
    assert action.get("action") == "insert_usepackage"
    assert action.get("package") == "graphicx"

    new_text = main.read_text(encoding="utf-8")
    assert "\\usepackage{graphicx}" in new_text
    assert new_text.index("\\usepackage{graphicx}") < new_text.index("\\begin{document}")


def test_apply_llm_edits_to_file_applies_ranges(tmp_path: Path) -> None:
    tool = LatexAutoFixTool(use_llm=False)
    p = tmp_path / "t.tex"
    p.write_text("a\nb\nc\nd\n", encoding="utf-8")
    edits = [
        {"start_line": 2, "end_line": 3, "replacement": "B\nC\n", "reason": "r"},
    ]
    action = tool._apply_llm_edits_to_file(p, edits, raw="{}")
    assert isinstance(action, dict)
    assert action.get("action") == "llm_edits"
    assert "edits" in action and len(action["edits"]) == 1

    text = p.read_text(encoding="utf-8")
    assert text == "a\nB\nC\nd\n"


def test_run_minimal_project_behaviour(tmp_path: Path) -> None:
    """
    该用例在不同环境下行为一致：
    - 若存在 LaTeX 编译器：最小工程应能在 1 轮内编译成功；
    - 若不存在 LaTeX 编译器：应返回明确失败原因（未找到编译器）。
    """
    project = tmp_path / "proj"
    project.mkdir(parents=True, exist_ok=True)
    (project / "main.tex").write_text(
        "\n".join(
            [
                "\\documentclass{article}",
                "\\begin{document}",
                "Hello",
                "\\end{document}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tool = LatexAutoFixTool(use_llm=False)
    out_dir = tmp_path / "out"
    r = tool.run(project_dir=str(project), tex_file="main.tex", output_dir=str(out_dir), max_iters=1, engine="auto", use_llm=False)

    if tool._has_any_latex_engine():
        assert r.success is True, r.error
        assert r.metadata and r.metadata.get("status") == "success"
        pdf_path = str(r.metadata.get("pdf_path") or "")
        assert pdf_path
        assert Path(pdf_path).exists()
        assert Path(pdf_path).stat().st_size > 0
    else:
        assert r.success is False
        assert r.metadata and r.metadata.get("status") == "failed"
        assert "编译器" in (r.error or "") or "LaTeX" in (r.error or "")

