# thesis_checklist_workflow.py

## 模块说明

（无）

## API 概览

### 类

- `ChecklistSection`：清单分段结构。
- `ThesisChecklistWorkflow`：论文检查工作流封装类。

### 函数

- `split_checklist_by_primary_headings(markdown_text)`：将 Markdown 清单按二级标题（##）切分为多个 ChecklistSection。
- `extract_question_list(llm_text)`：从 LLM 回复中提取问题列表（JSON 数组）。
- `build_section_prompt(section)`：构造单个检查 section 的提示词。

## 类与方法

### ChecklistSection

清单分段结构。

方法：无

### ThesisChecklistWorkflow

论文检查工作流封装类。

方法：

- `__init__(self, *, checklist_path, llm_client=..., pdf_comment_tool=..., model_name=..., api_key=..., base_url=..., temperature=...)`：Args:
- `build(self)`：构建并返回 Workflow 实例（不执行）。
- `run(self, *, pdf_path, output_path)`：执行论文检查工作流。

## 函数

### split_checklist_by_primary_headings(markdown_text)

将 Markdown 清单按二级标题（##）切分为多个 ChecklistSection。

### extract_question_list(llm_text)

从 LLM 回复中提取问题列表（JSON 数组）。

### build_section_prompt(section)

构造单个检查 section 的提示词。
