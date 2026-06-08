# latex_autofix_tool.py

## 模块说明

LaTeX 自动修复工具（LatexAutoFixTool）。

核心目标：给定一个 LaTeX 项目与入口 .tex 文件，在不修改原工程的前提下自动“编译-定位-修复”循环，
直到成功编译或达到最大轮次，并输出完整的修复历史。

整体策略：
1) 复制项目到工作副本（work_dir），所有修改都发生在副本中
2) 编译入口 tex（支持 latexmk / pdflatex / xelatex / lualatex）
3) 解析日志抽取首个关键错误（尽量提取 file:line 信息）
4) 先走确定性规则修复（例如：下划线转义、需要 shell-escape、Unicode 引擎切换）
5) 规则无法处理时可调用 LLM（Gemini）生成多处行级 edits，并应用到“报错指向的目标 tex 文件”
6) 循环直到编译通过，返回 work_dir、pdf_path 与 history

## API 概览

### 类

- `LatexError`：编译错误的结构化表示。
- `LatexAutoFixTool`：自动修复 LaTeX 编译错误的工具。

### 函数

- `_assert_file_ok(path)`：断言指定路径文件存在且非空（用于自测验证输出）。
- `_run_self_test(output_dir=...)`：运行本工具的实际场景自测：对内置测试工程执行自动修复并输出结果。

## 类与方法

### LatexError

编译错误的结构化表示。

方法：无

### LatexAutoFixTool

自动修复 LaTeX 编译错误的工具。

方法：

- `__init__(self, *, model_name=..., api_key=..., temperature=..., use_llm=...)`：初始化 LaTeX 自动修复工具，并配置 LLM 参数与是否启用 LLM 修复。
- `_resolve_api_key(self, api_key)`：解析实际可用的 Gemini API Key（优先入参，其次实例字段与环境变量）。
- `_load_gemini_client_class(self)`：从项目源码动态加载 GeminiClient 类，避免导入阶段对可选依赖产生硬耦合。
- `_decode_bytes(self, b)`：将 subprocess 输出的 bytes 按常见编码解码为 str（失败则 replace）。
- `_which(self, exe)`：查找可执行文件路径（优先 PATH，Windows 下额外探测常见 MiKTeX 安装目录）。
- `_has_any_latex_engine(self)`：判断当前环境是否存在任一可用的 LaTeX 编译命令。
- `_project_copy(self, src_dir, dst_dir, extra_ignore_top=...)`：复制项目到工作目录，并忽略常见无关目录（如 .git/venv/outputs）。
- `_compile(self, *, work_dir, main_tex, engine, shell_escape, timeout_s)`：在 work_dir 中编译入口 tex，并返回一次编译的结构化结果与关键路径。
- `_extract_first_error(self, text)`：从编译输出中提取首个关键错误（message/file/line/context/raw）。
- `_safe_relpath(self, p, base)`：生成跨平台稳定的相对路径展示（失败则回退为原路径）。
- `_find_target_file(self, work_dir, err_file, fallback)`：根据日志给出的 err_file 在副本项目内定位需要修改的目标文件。
- `_read_lines(self, p)`：按 UTF-8 读取文本为“保留换行符”的行列表（解码失败则 replace）。
- `_write_lines(self, p, lines)`：将行列表写回文件（UTF-8 编码）。
- `_insert_package(self, lines, pkg)`：在导言区 \begin{document} 前插入 \usepackage{pkg}（若已存在则不改）。
- `_escape_underscores_on_line(self, line)`：在疑似文本模式下将未转义的下划线替换为 \_（尽量避免破坏数学与链接命令）。
- `_deterministic_fix(self, *, err, work_dir, main_tex, state)`：对常见报错执行确定性修复（加宏包、转义下划线、切换引擎、开启 shell-escape）。
- `_apply_llm_edits_to_file(self, target, edits, raw)`：校验并应用 LLM 返回的多处行区间替换（从后往前应用以避免行号漂移）。
- `_llm_fix(self, *, err, main_tex, work_dir)`：调用 LLM 生成多处修复建议，并将建议应用到目标 .tex 文件。
- `run(self, latex_path=..., project_dir=..., tex_file=..., output_dir=..., max_iters=..., engine=..., use_llm=...)`：复制工程副本并迭代编译/修复，直到编译通过或达到 max_iters 上限。

## 函数

### _assert_file_ok(path)

断言指定路径文件存在且非空（用于自测验证输出）。

### _run_self_test(output_dir=...)

运行本工具的实际场景自测：对内置测试工程执行自动修复并输出结果。
