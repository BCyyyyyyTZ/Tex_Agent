# concept_diagram_tool.py

## 模块说明

概念示意图生成工具（ConceptDiagramTool）。

输入一段概念描述，工具会：
1) 调用 LLM（GeminiClient）生成 Mermaid flowchart 代码
2) 将 Mermaid 代码通过 mermaid.ink 渲染为 PNG
3) 输出图片路径，并在 metadata 中返回 Mermaid 代码等信息，便于复现与调试

适用场景：
- 论文方法/系统架构/流程的概念图快速生成
- 把较长的结构化描述“压缩”为图形化概览

## API 概览

### 类

- `ConceptDiagramTool`：将概念描述转换为 Mermaid 并渲染为图片的工具封装。

### 函数

- `_assert_file_ok(path)`：断言指定路径文件存在且非空（用于自测验证输出）。
- `_run_self_test(output_dir=...)`：运行本工具的最小自测：生成一张概念图并校验输出文件可用。

## 类与方法

### ConceptDiagramTool

将概念描述转换为 Mermaid 并渲染为图片的工具封装。

方法：

- `__init__(self, *, model_name=..., api_key=..., temperature=...)`：初始化概念图工具，并配置模型参数（model_name/api_key/temperature）。
- `_resolve_api_key(self, api_key)`：解析实际可用的 Gemini API Key（优先入参，其次实例字段与环境变量）。
- `_build_prompt(self, user_prompt, title)`：构造用于生成 Mermaid 的提示词（约束输出为 flowchart 代码本体）。
- `_extract_mermaid(self, text)`：从模型输出中提取 Mermaid 代码并清理可能的 Markdown 代码块包裹。
- `_encode_mermaid_ink(self, mermaid_code)`：将 Mermaid 代码按 mermaid.ink 的 pako 压缩+base64url 规则编码为 URL 片段。
- `_render_with_mermaid_ink(self, mermaid_code, output_path)`：调用 mermaid.ink 在线渲染服务，将 Mermaid 代码渲染为 PNG 并写入 output_path。
- `run(self, prompt, output_path, title=...)`：生成概念示意图。

## 函数

### _assert_file_ok(path)

断言指定路径文件存在且非空（用于自测验证输出）。

### _run_self_test(output_dir=...)

运行本工具的最小自测：生成一张概念图并校验输出文件可用。
