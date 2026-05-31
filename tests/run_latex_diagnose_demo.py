#!/usr/bin/env python3
"""
运行 diagnose_demo 夹具，对比内置语法检查与 latex_diagnose_v0 / v1 工作流输出。

用法（项目根目录）:
  python tests/run_latex_diagnose_demo.py
  python tests/run_latex_diagnose_demo.py --skip-v1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "latex" / "diagnose_demo"
MAIN_TEX = FIXTURE / "main.tex"


def _ground_truth_syntax() -> list[dict]:
    from latex.syntax_check import check_syntax
    from latex.tex_source import read_tex_file

    issues = []
    for rel in ("main.tex", "chapters/appendix.tex"):
        path = FIXTURE / rel
        if path.is_file():
            for raw in check_syntax(read_tex_file(path)):
                issues.append(
                    {
                        "file": rel.replace("\\", "/"),
                        "line": raw.line,
                        "message": raw.message,
                        "severity": raw.severity,
                    }
                )
    return issues


def _run_workflow(name: str) -> dict:
    from core.agent_cli import TeXAgentCLI

    payload = json.dumps(
        {"root": str(FIXTURE.resolve()).replace("\\", "/"), "main_tex": "main.tex"},
        ensure_ascii=False,
    )
    cli = TeXAgentCLI(use_branch=False)
    return cli.run_task(payload, workflow_name=name, use_loading=False)


def _extract_report(result: dict) -> dict | None:
    meta = result.get("metadata") or {}
    for key, val in meta.items():
        if not isinstance(val, dict):
            continue
        if val.get("workflow", "").startswith("latex_diagnose"):
            return val
    output = result.get("output") or ""
    if output.strip().startswith("{"):
        try:
            data = json.loads(output)
            if data.get("workflow", "").startswith("latex_diagnose"):
                return data
        except json.JSONDecodeError:
            pass
    return None


def _print_report(title: str, report: dict | None, *, error: str | None) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    if error:
        print(f"FAIL: {error}")
        return
    if not report:
        print("FAIL: 未解析到 report JSON")
        return
    summary = report.get("summary") or {}
    print(f"workflow: {report.get('workflow')}")
    print(f"root: {report.get('root')}")
    print(
        f"issues: total={summary.get('error', 0)} errors + "
        f"{summary.get('warning', 0)} warnings "
        f"(listed {report.get('diagnostics', {}).get('issue_count', '?')})"
    )
    print(f"by_source: {summary.get('by_source')}")
    slices = report.get("slices") or []
    print(f"slices (error-only): {len(slices)}")
    suggestions = report.get("suggestions") or []
    print(f"suggestions (v1): {len(suggestions)}")
    top = (report.get("diagnostics") or {}).get("issues_top_k") or []
    if top:
        print("\nTop issues:")
        for i, item in enumerate(top[:12], 1):
            print(
                f"  {i}. [{item.get('severity')}] {item.get('file')}:{item.get('line')} "
                f"- {item.get('message')}"
            )
    if suggestions:
        print("\nLLM suggestions:")
        for i, s in enumerate(suggestions[:5], 1):
            print(
                f"  {i}. {s.get('file')} issue_id={s.get('issue_id')} "
                f"replacement={str(s.get('replacement', ''))[:60]!r}..."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-v1", action="store_true", help="跳过需 LLM 的 v1")
    args = parser.parse_args()

    if not MAIN_TEX.is_file():
        print(f"夹具不存在: {MAIN_TEX}", file=sys.stderr)
        return 1

    from latex.tex_env import probe_tex_env

    env = probe_tex_env()
    print(f"Fixture: {FIXTURE}")
    print(f"TeX tools: chktex={env.chktex} latexmk={env.latexmk} pdflatex={env.pdflatex}")

    syntax = _ground_truth_syntax()
    print(f"\n内置语法检查 (ground truth): {len(syntax)} 条")
    for item in syntax:
        print(f"  - [{item['severity']}] {item['file']}:{item['line']} {item['message']}")

    exit_code = 0

    r0 = _run_workflow("latex_diagnose_v0")
    if r0.get("error"):
        exit_code = 1
    _print_report("latex_diagnose_v0", _extract_report(r0), error=r0.get("error"))

    if not args.skip_v1:
        r1 = _run_workflow("latex_diagnose_v1")
        if r1.get("error"):
            exit_code = 1
        _print_report("latex_diagnose_v1", _extract_report(r1), error=r1.get("error"))

    print("\n完成。详见 tests/fixtures/latex/diagnose_demo/EXPECTED_ISSUES.md")
    return exit_code


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
