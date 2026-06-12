# TeX\_Agent 测试报告

## 1. 概述

本报告对应测试计划的一次可复现测试执行。测试代码位于 `qa_tests/`。

## 2. 测试对象与范围

- 项目：TeX\_Agent
- 测试代码位置：`qa_tests/`
- 覆盖模块：
  - Core：`core/message.py`、`core/state.py`（消息/节点输出契约、状态归一化）
  - `check_text.py` 的纯函数工具链（连接失败识别、路径解析、PDF 列表归并、输出文件分配）
  - Workflow：`workflow/condition_evaluator.py`（结构化条件表达式解析与条件路由）
  - Workflow：`workflow/parallel_merger.py`（并行分支结果汇聚策略）
  - Workflow：`workflow/workflow_parser.py`（节点/边解析与校验、由 edges 回填 depends\_on）
  - Workflow：端到端烟测（纯工具节点，无 LLM）
  - RAG：`rag/rag_pipeline.py`（以 MockRetriever 注入方式进行无外部依赖单测）
  - RAG：`rag/document_loader.py`（文本分块、文件加载与元数据生成）
  - RAG：`rag/store_listing.py`（列举分页结果格式化）
  - LaTeX：`latex/project_index.py`（项目扫描与 inputs 提取）
  - LaTeX：`latex/log_parser.py`（latex 日志解析）
  - LaTeX：`latex/apply_edit.py`（Suggestion 应用到文件）
  - LaTeX：`latex/slice.py`（按 DiagnosticIssue 切片逻辑）
  - LaTeX：`latex/paths.py`（跨平台相对路径规范化与 tex 路径解析）
  - LaTeX：`latex/chktex_runner.py`、`latex/latexmk_runner.py`（runner 退化/集成）
  - LaTeX：`latex/watch_service.py`（监视服务：防抖触发诊断与快照更新）
  - LaTeX：`latex/ghost_server.py`（Ghost UI 基础健康检查）
  - Tools：`tools/command_running_tool.py`（使用本机 Python 作为无害命令验证）
  - Security：`security/middleware.py`（数据契约与未实现接口行为）
  - Memory：`memory/factory.py`、`memory/branch_memory.py`（工厂/分支记忆）
  - Agents：`agents/base_agent.py`（LLM 响应解析逻辑的纯单测）
  - Utils：`utils/reply_format.py`（UI 展示前文本归一化）
  - Utils：`utils/run_cancel.py`（协作式取消标记与可打断 sleep）
  - Web：`ui/web/conferences_data.py`（静态日历数据加载、过滤与排序）
  - Web：`ui/web/file_storage.py`（文件名净化、扩展名白名单、目录穿越防护）
  - Web（FastAPI）：`ui/web/server.py` 的 DAG 校验与回复格式化
  - Web（FastAPI）服务健康检查/首页缓存头
  - Overleaf：`ui/overleaf/server.py`（主页可访问性）

## 3. 测试环境

- 操作系统：Windows
- Python：3.13.12
- pytest：9.0.3

## 4. 执行方法

在仓库根目录 `Tex_Agent`：

1. 安装依赖（推荐）

```bash
pip install -r requirements.txt
```

1. 执行测试集（ `qa_tests/`）

```bash
pytest -q qa_tests
```

1. 获取跳过原因摘要

```bash
pytest -q qa_tests -rs
```

说明：若希望 Web/FastAPI 相关测试也实际运行，需要额外确保安装了 `python-multipart`（FastAPI Form 解析所需）：

```bash
pip install python-multipart
```

## 5. 测试结果摘要

本次执行命令：`pytest -q qa_tests`

- 通过（passed）：124
- 跳过（skipped）：0
- 失败（failed）：0
- 错误（error）：0
- 警告（warning）：1（FastAPI TestClient 依赖提示，见“已知问题/警告”）
- 用时：3.67s

## 6. 测试用例与测试计划可追溯性

测试用例与测试计划中测试项的对应关系：

- WF（计划：WF-01 / WF-02 / WF-03 / WF-04）
  - 条件表达式与条件路由：`qa_tests/unit/test_workflow_condition_evaluator_unit.py`
  - 并行汇聚策略：`qa_tests/unit/test_workflow_parallel_merger_unit.py`
  - 解析器节点/边校验与 depends\_on 回填：`qa_tests/unit/test_workflow_parser_unit.py`
- WF（计划：WF-05）
  - 无 LLM 的工具型端到端烟测：`qa_tests/integration/test_workflow_e2e_tool_only_integration.py`
- WEB/WF（计划：WF-02 / WEB-01）
  - DAG 校验：`qa_tests/unit/test_ui_web_workflow_dag_validation_unit.py`
  - Web App 启动健康检查：首页缓存头：`qa_tests/integration/test_web_server_integration.py`
- WEB（计划：WEB-01 辅助）
  - 终局回复拼装与附件链接收集：`qa_tests/unit/test_ui_web_reply_format_unit.py`
- WEB（计划：WEB-05 / WEB-02（存储安全子集））
  - conferences 日历过滤与排序：`qa_tests/unit/test_ui_web_conferences_data_unit.py`
  - 文件存储：文件名净化、扩展白名单、路径安全解析：`qa_tests/unit/test_ui_web_file_storage_unit.py`
- RG（计划：RG-04 pipeline mock 集成）
  - `qa_tests/unit/test_rag_pipeline_mock_unit.py`（MockRetriever 注入，验证 index/retrieve/clear 与格式化输出）
- RG（计划：RG-01 / RG-02）
  - 文档加载与切块：`qa_tests/unit/test_rag_document_loader_unit.py`
- RG（计划：RG-03（列举展示））
  - StoredChunksPage 格式化：`qa_tests/unit/test_rag_store_listing_unit.py`
- RG（计划：RG-05）
  - ChromaRetriever 真集成：`qa_tests/integration/test_rag_chroma_integration.py`
- TX（计划：TX-02）
  - `qa_tests/unit/test_latex_slice_unit.py`（切片边界、负参数、防 IO 与 IO 两条路径）
- TX（计划：TX-03 / TX-04）
  - 日志解析：`qa_tests/unit/test_latex_log_parser_unit.py`
  - 建议应用：`qa_tests/unit/test_latex_apply_edit_unit.py`
- TX（计划：TX-01（路径与解析子集））
  - 路径规范化与 tex 解析：`qa_tests/unit/test_latex_paths_unit.py`
- TX（计划：TX-01（项目索引子集））
  - 项目索引（扫描/inputs 抽取）：`qa_tests/unit/test_latex_project_index_unit.py`
- TX（计划：TX-05 / TX-06）
  - chktex/latexmk runner 退化与（可用时）集成：`qa_tests/integration/test_latex_runners_integration.py`
- TX（计划：TX-07）
  - WatchService 防抖诊断链路：`qa_tests/integration/test_latex_watch_service_integration.py`
- TX（计划：TX-08（基础 API 子集））
  - Ghost server 健康检查：`qa_tests/integration/test_ghost_server_integration.py`
- TL（计划：TL-02）
  - `qa_tests/unit/test_command_running_tool_unit.py`（验证命令执行成功与输出包含关键文本）
- TL（计划：TL-04（Markdown/统计等纯工具））
  - MarkdownSectionTool：`qa_tests/unit/test_tools_markdown_section_tool_unit.py`
  - TextStatsTool：`qa_tests/unit/test_tools_text_stats_tool_unit.py`
- CLI（计划：CLI-02 的“最小可运行子路径”拆解）
  - `qa_tests/unit/test_check_text_utils_unit.py`（对 `check_text.py` 内可独立验证的纯函数做回归）
- CLI（计划：CLI-01）
  - 命令匹配与执行分流：`qa_tests/unit/test_cli_command_registry_unit.py`
- 安全（计划：安全策略与中间件接口）
  - `qa_tests/unit/test_security_middleware_contract_unit.py`（枚举/数据结构契约 + 未实现行为确认）
- AG（计划：AG-01（契约子集））
  - message/node\_output/state 合约：`qa_tests/unit/test_core_message_contract_unit.py`、`qa_tests/unit/test_core_state_reducers_unit.py`
- AG（计划：并发/合并语义支撑）
  - metadata 深合并与 reducer 语义：`qa_tests/unit/test_core_state_merge_metadata_unit.py`
- AG（计划：AG-03（上下文策略子集））
  - context settings：`qa_tests/unit/test_context_settings_unit.py`
- AG（计划：AG-04）
  - memory factory/branch：`qa_tests/unit/test_memory_factory_branch_memory_unit.py`
- Utils（计划：回归与可维护性要求支撑）
  - 回复展示文本归一化：`qa_tests/unit/test_utils_reply_format_unit.py`
  - 协作式取消与可打断 sleep：`qa_tests/unit/test_utils_run_cancel_unit.py`
- Web（计划：WEB-02（下载令牌安全子集））
  - 一次性 artifact token：`qa_tests/unit/test_utils_web_artifact_registry_unit.py`
- Overleaf（计划：OV-01（静态资源子集））
  - 静态资源存在性：`qa_tests/unit/test_overleaf_static_assets_unit.py`

## 7. 测试代码数量统计

统计范围：`qa_tests/**/*.py`

- Python 文件数：39
- 测试函数数（`test_` 前缀）：114
- 总行数：1417

文件清单：

- `qa_tests/conftest.py`
- `qa_tests/integration/test_ghost_server_integration.py`
- `qa_tests/integration/test_latex_runners_integration.py`
- `qa_tests/integration/test_latex_watch_service_integration.py`
- `qa_tests/integration/test_overleaf_server_integration.py`
- `qa_tests/integration/test_rag_chroma_integration.py`
- `qa_tests/integration/test_web_server_integration.py`
- `qa_tests/integration/test_workflow_e2e_tool_only_integration.py`
- `qa_tests/unit/test_agents_llmclient_parse_unit.py`
- `qa_tests/unit/test_check_text_utils_unit.py`
- `qa_tests/unit/test_cli_command_registry_unit.py`
- `qa_tests/unit/test_command_running_tool_unit.py`
- `qa_tests/unit/test_context_settings_unit.py`
- `qa_tests/unit/test_core_message_contract_unit.py`
- `qa_tests/unit/test_core_state_merge_metadata_unit.py`
- `qa_tests/unit/test_core_state_reducers_unit.py`
- `qa_tests/unit/test_latex_apply_edit_unit.py`
- `qa_tests/unit/test_latex_log_parser_unit.py`
- `qa_tests/unit/test_latex_paths_unit.py`
- `qa_tests/unit/test_latex_project_index_unit.py`
- `qa_tests/unit/test_latex_slice_unit.py`
- `qa_tests/unit/test_memory_factory_branch_memory_unit.py`
- `qa_tests/unit/test_overleaf_static_assets_unit.py`
- `qa_tests/unit/test_rag_document_loader_unit.py`
- `qa_tests/unit/test_rag_pipeline_mock_unit.py`
- `qa_tests/unit/test_rag_store_listing_unit.py`
- `qa_tests/unit/test_security_middleware_contract_unit.py`
- `qa_tests/unit/test_tools_markdown_section_tool_unit.py`
- `qa_tests/unit/test_tools_text_stats_tool_unit.py`
- `qa_tests/unit/test_ui_web_conferences_data_unit.py`
- `qa_tests/unit/test_ui_web_file_storage_unit.py`
- `qa_tests/unit/test_ui_web_reply_format_unit.py`
- `qa_tests/unit/test_ui_web_workflow_dag_validation_unit.py`
- `qa_tests/unit/test_utils_reply_format_unit.py`
- `qa_tests/unit/test_utils_run_cancel_unit.py`
- `qa_tests/unit/test_utils_web_artifact_registry_unit.py`
- `qa_tests/unit/test_workflow_condition_evaluator_unit.py`
- `qa_tests/unit/test_workflow_parallel_merger_unit.py`
- `qa_tests/unit/test_workflow_parser_unit.py`

## 8. 已知问题/警告

### 8.1 FastAPI TestClient 警告

本次运行产生 1 条警告（pytest 输出原文要点）：

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`

该警告不影响本次测试用例通过情况，属于上游依赖提示。

### 8.2 依赖缺失导致的跳过

若 `python-multipart` 未安装，`ui.web.server` 在导入阶段会触发 FastAPI 对 Form 的依赖检查并抛出 RuntimeError；为保证测试集在当前环境可运行，会对 Web 相关测试采用“按依赖条件 skip”的策略。
