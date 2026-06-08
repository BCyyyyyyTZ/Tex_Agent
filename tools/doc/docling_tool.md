# docling_tool.py

## 模块说明

DoclingParseTool：使用 Docling 将文档（PDF/DOCX 等）解析为 Markdown + JSON。

支持缓存：若 redo=False（默认），会先在 PARSED_DOC_DIR 下查找已存在的解析结果（按文件名 stem 匹配），
存在有效结果则直接复用，避免重复解析。

## API 概览

### 类

- `DoclingParseTool`：Docling 文档解析工具。

### 函数

- `_sanitize_stem(stem)`：与 docling_parse.py 保持一致的 stem 清理逻辑。
- `_find_existing_parse(root, source_stem)`：在 parsed_doc_dir 下查找与输入文件名 stem 匹配的最新解析目录。

## 类与方法

### DoclingParseTool

Docling 文档解析工具。

方法：

- `__init__(self)`：初始化 Docling 解析工具，并声明输入 schema（doc_path/redo）。
- `run(self, doc_path, redo=...)`：执行文档解析。
- `__repr__(self)`：返回工具的稳定字符串表示（便于日志与调试）。

## 函数

### _sanitize_stem(stem)

与 docling_parse.py 保持一致的 stem 清理逻辑。

### _find_existing_parse(root, source_stem)

在 parsed_doc_dir 下查找与输入文件名 stem 匹配的最新解析目录。
