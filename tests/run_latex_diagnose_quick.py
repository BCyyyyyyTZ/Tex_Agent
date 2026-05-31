#!/usr/bin/env python3
"""快速跑 v0 工具链（不经过 CLI 打印，避免 Windows 控制台编码问题）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "latex" / "diagnose_demo"
OUT = FIXTURE / "diagnose_results.json"


def main() -> None:
    sys.path.insert(0, str(ROOT))
    payload = json.dumps(
        {"root": str(FIXTURE.resolve()).replace("\\", "/"), "main_tex": "main.tex"},
        ensure_ascii=False,
    )

    from latex.syntax_check import check_syntax
    from latex.tex_source import read_tex_file
    from latex.tex_env import probe_tex_env
    from tools.latex_project_tool import LatexProjectTool
    from tools.chktex_tool import ChkTeXTool
    from tools.latexmk_tool import LatexmkTool
    from tools.latex_merge_tool import LatexMergeTool
    from tools.latex_slice_tool import LatexSliceTool
    from tools.latex_report_tool import LatexReportTool

    env = probe_tex_env()
    syntax = []
    for rel in ("main.tex", "chapters/appendix.tex"):
        for raw in check_syntax(read_tex_file(FIXTURE / rel)):
            syntax.append(
                {
                    "file": rel,
                    "line": raw.line,
                    "severity": raw.severity,
                    "message": raw.message,
                }
            )

    p = LatexProjectTool().run(payload)
    c = ChkTeXTool().run(payload)
    m = LatexmkTool().run(payload)
    merge = LatexMergeTool().run(
        user_input=payload,
        chktex_output=c.output,
        latexmk_output=m.output,
        project_output=p.output,
    )
    sl = LatexSliceTool().run(
        user_input=payload, merge_output=merge.output, severity="error"
    )
    rep = LatexReportTool().run(
        user_input=payload,
        project_output=p.output,
        merge_output=merge.output,
        slice_output=sl.output,
        workflow="latex_diagnose_v0",
    )
    report_v0 = json.loads(rep.output)

    result = {
        "tex_env": {
            "chktex": env.chktex,
            "latexmk": env.latexmk,
            "pdflatex": env.pdflatex,
        },
        "syntax_ground_truth": syntax,
        "v0_report": report_v0,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(
        f"v0: {report_v0['summary']['error']} errors, "
        f"{report_v0['summary']['warning']} warnings"
    )


if __name__ == "__main__":
    main()
