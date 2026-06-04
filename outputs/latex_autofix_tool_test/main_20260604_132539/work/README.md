这是一个用于测试 `latex_autofix` 的 LLM 修复场景工程。

`main.tex` 故意包含两类问题：
- 可由规则修复：文本下划线 `_`、未引入 xcolor/booktabs/url 却使用 `\textcolor/\toprule/\url`
- 需要 LLM 修复：
  - `align` 环境缺失（通常补 amsmath）
  - 自定义命令 `\unknowncmd` 未定义（不在内置宏包映射中）
  - 花括号缺失导致的语法错误
- 其它覆盖：包含 emoji 的 Unicode 字符，触发引擎切换到 xelatex 的规则路径
