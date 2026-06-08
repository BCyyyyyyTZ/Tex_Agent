"""LaTeX 表格生成：纯模板拼接，不调用 LLM。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


def _escape_latex(s: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = str(s)
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def _is_numeric_cell(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    return bool(re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?$", t))


def _guess_alignment(headers: list[str], rows: list[list[str]]) -> str:
    """首列左对齐，数值列居中，其余居中。"""
    ncol = len(headers)
    aligns = ["l"] * ncol
    for j in range(ncol):
        col_vals = [r[j] for r in rows if j < len(r)]
        if j == 0:
            aligns[j] = "l"
        elif col_vals and all(_is_numeric_cell(v) for v in col_vals):
            aligns[j] = "c"
        else:
            aligns[j] = "c"
    return "".join(aligns)


class LatexTableTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="latex_table",
            description="将表格数据转为 LaTeX tabular 代码（模板生成，无需 LLM）。",
            input_schema={
                "headers": "表头",
                "rows": "数据行",
                "caption": "表标题",
                "label": "label",
                "alignment": "列对齐",
                "highlight_best": "是否高亮每列最优数值（粗体）",
            },
        )

    def _parse_rows(self, rows: Any) -> list[list[str]]:
        if isinstance(rows, str):
            text = rows.strip()
            if not text:
                return []
            try:
                loaded = json.loads(text)
                if isinstance(loaded, list):
                    return [[str(c) for c in row] for row in loaded]
            except json.JSONDecodeError:
                pass
            out: list[list[str]] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [c.strip() for c in re.split(r"\t(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)|,(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", line)]
                parts = [p.strip('"') for p in parts if p.strip()]
                if parts:
                    out.append(parts)
            return out
        if isinstance(rows, list):
            return [[str(c) for c in row] for row in rows]
        return []

    def _best_indices(self, rows: list[list[str]], ncol: int) -> dict[int, int]:
        """每列找最大值行索引（跳过首列）。"""
        best: dict[int, int] = {}
        for j in range(1, ncol):
            vals: list[tuple[int, float]] = []
            for i, row in enumerate(rows):
                if j >= len(row):
                    continue
                m = re.match(r"^([-+]?\d*\.?\d+)", row[j].strip().replace("%", ""))
                if m:
                    vals.append((i, float(m.group(1))))
            if vals:
                best[j] = max(vals, key=lambda x: x[1])[0]
        return best

    def run(
        self,
        headers: Any = None,
        rows: Any = None,
        caption: str = "",
        label: str = "",
        alignment: str = "",
        highlight_best: bool = False,
    ) -> ToolResult:
        try:
            hdr = headers or []
            if isinstance(hdr, str):
                hdr = [h.strip().strip('"') for h in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", hdr) if h.strip()]
            hdr = [str(h) for h in hdr]
            body = self._parse_rows(rows)
            if not hdr and body:
                hdr = [f"Col{i + 1}" for i in range(len(body[0]))]
            if not hdr:
                return ToolResult(success=False, output="", error="表头或数据不能为空")

            ncol = len(hdr)
            for i, row in enumerate(body):
                if len(row) != ncol:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"第 {i + 1} 行列数为 {len(row)}，与表头列数 {ncol} 不一致",
                    )

            align = (alignment or _guess_alignment(hdr, body)).strip()
            if len(align) != ncol:
                align = "l" + "c" * (ncol - 1) if ncol > 1 else "c"

            best_map = self._best_indices(body, ncol) if highlight_best else {}

            lines = [
                "% 需要导言区: \\usepackage{booktabs}",
                r"\begin{table}[htbp]",
                r"  \centering",
            ]
            if caption:
                lines.append(f"  \\caption{{{_escape_latex(caption)}}}")
            if label:
                lab = label if label.startswith("tab:") else f"tab:{label}"
                lines.append(f"  \\label{{{lab}}}")
            lines.append(f"  \\begin{{tabular}}{{{align}}}")
            lines.append(r"    \toprule")
            lines.append("    " + " & ".join(f"\\textbf{{{_escape_latex(h)}}}" for h in hdr) + r" \\")
            lines.append(r"    \midrule")
            for ri, row in enumerate(body):
                cells = []
                for j, c in enumerate(row):
                    cell = _escape_latex(c)
                    if highlight_best and best_map.get(j) == ri:
                        cell = f"\\textbf{{{cell}}}"
                    cells.append(cell)
                lines.append("    " + " & ".join(cells) + r" \\")
            lines.append(r"    \bottomrule")
            lines.append(r"  \end{tabular}")
            lines.append(r"\end{table}")
            latex = "\n".join(lines)
            return ToolResult(
                success=True,
                output=latex,
                metadata={"columns": ncol, "rows": len(body), "alignment": align, "mode": "template"},
            )
        except Exception as e:
            logger.error(f"LaTeX 表格生成失败: {e}")
            return ToolResult(success=False, output="", error=f"LaTeX 表格生成失败: {e}")
