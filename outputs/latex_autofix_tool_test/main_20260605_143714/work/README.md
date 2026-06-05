这是一个用于测试 `latex_autofix` 的 LLM 修复场景工程。

该测试工程包含 `main.tex` 与 `sections/body.tex`（通过 `\input` 引入），用于验证：
- 复制整个项目到副本后再编译入口文件
- 报错指向子文件时能修改子文件
- 缺宏包时能修改入口文件导言区
- 需要 LLM 的语法/未知命令问题能被定位到对应文件并修改

`main.tex` 保留入口文件自身的多种报错（用于验证会修改入口文件并最终编译通过）：
- 可由规则修复：文本下划线 `_`、未引入 xcolor/booktabs/url 却使用 `\textcolor/\toprule/\url`（宏包会被补到入口文件导言区）
- 需要 LLM 修复：`align` 环境缺失（通常补 amsmath）、自定义命令 `\unknowncmdmain` 未定义、花括号缺失导致的语法错误
- 其它覆盖：包含 emoji 的 Unicode 字符，触发引擎切换到 xelatex 的规则路径

`sections/body.tex` 新增子文件报错（用于验证会修改子文件）：
- 可由规则修复：文本下划线 `_`
- 需要 LLM 修复：自定义命令 `\unknowncmdbody` 未定义、花括号缺失导致的语法错误
