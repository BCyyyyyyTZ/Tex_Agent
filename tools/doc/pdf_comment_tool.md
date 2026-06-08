# pdf_comment_tool.py

## 模块说明

PDF 批注工具（PdfCommentTool）。

该工具基于 PyMuPDF（fitz）实现对 PDF 的高亮与便签注释：
- run_single: 对单个 (page_idx, text, comment) 执行高亮/注释
- run: 批量处理 question_list，并返回统计信息

实现重点：
- 优先在指定页 search_for 精确定位文本；找不到时可退化到 fuzzy_search 或全文扫描
- 支持 output_path 与 pdf_path 相同的场景：通过临时文件写入，最后 replace 原文件

## API 概览

### 类

- `PdfCommentTool`：pdf 注释工具。

## 类与方法

### PdfCommentTool

pdf 注释工具。

方法：

- `__init__(self)`：初始化 PDF 批注工具，并声明所需输入字段（page_idx/text/comment）。
- `fuzzy_search(self, page, target_text)`：模糊搜索：将页面所有单词提取出来，通过滑动窗口匹配目标文本
- `find_in_document(self, doc, target_text, skip_page_idx=...)`：在全文范围查找目标文本。
- `run_single(self, pdf_path, output_path, page_idx, text, comment, author=...)`：高亮 PDF 中的文本并添加注释
- `run(self, pdf_path, output_path, question_list, author=...)`：批量高亮 PDF 中的文本并添加注释
