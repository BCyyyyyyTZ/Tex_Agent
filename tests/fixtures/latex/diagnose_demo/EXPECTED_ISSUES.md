# diagnose_demo 预期问题清单

| # | 位置 | 故意错误 | 理想检测来源 | 严重级别 |
|---|------|----------|--------------|----------|
| 1 | main.tex §2 | 缺少 `\end{equation}` | latexmk / 内置 syntax | error |
| 2 | main.tex §5 | `\textbf{` 未闭合 `}` | latexmk / 内置 syntax | error |
| 3 | main.tex | `\ref{fig:missing-figure}` 无 label | parser | warning |
| 4 | chapters/appendix.tex | `\ref{tab:nonexistent-table}` | parser | warning |
| 5 | main.tex | `\cite{ghost_paper_2099}` 不在 refs.bib | parser/bib（若启用） | warning |
| 6 | main.tex 引言 | 双空格、直引号 `"` | ChkTeX | warning |

**说明**：未安装 `chktex` / `latexmk` 时，工作流 v0/v1 主要依赖 **parser** 检出未定义 `\ref`（warning）。  
`latex_diagnose_v0` 的 slice 节点仅保留 **error** 级别；无 TeX 环境时 error 可能为 0，v1 的 LLM 修复批次也可能为空。
