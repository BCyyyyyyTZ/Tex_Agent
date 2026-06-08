# specified_agents/paper_check_agent.py

## 模块说明

论文检查专用 Agent（PaperCheckAgent）。

该 Agent 以“论文要求（Markdown/文本）”为检查标准，驱动 LLM 从 PDF 论文中找出所有不符合项：
1) 读取 rules_path 作为检查规则注入到 system prompt
2) LLM 输出 BEGIN ... END 包裹的 JSON 问题列表（页码/原文片段/问题原因）
3) 调用 PdfCommentTool 在 PDF 上批注，输出带批注的 PDF（由 tool_args 指定路径）

注意：
- 页码规则以 PDF 的第一页为 1（在提示词中强调），但 PdfCommentTool 内部使用 0-based 索引；
  这里的转换由工具内部处理/或由 LLM 输出规范控制。

## API 概览

### 类

- `PaperCheckAgent`：面向 PDF 论文的“规则驱动检查 + 自动批注”Agent。

## 类与方法

### PaperCheckAgent

面向 PDF 论文的“规则驱动检查 + 自动批注”Agent。

方法：

- `__init__(self, name, rules_path, model_name=..., api_key=..., temperature=..., max_history=...)`：读取论文要求规则文件并构建仅包含 PdfCommentTool 的检查型 Agent。
- `paper_check(self, message)`：执行论文检查并生成批注结果。
