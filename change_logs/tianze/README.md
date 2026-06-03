# 更新索引

#### [2026-04-09~2026-04-11](./2026-04-09.md)

+ 更新README并隐藏RAG部分内容
+ 添加硬编码的workflow讲解

#### [2026-04-13~2026-04-14](./2026-04-13.md)

+ 更新[RAG说明文档](../../doc/RAG说明文档.md)
+ 添加RAG相关单元测试
+ 实现手动注入文件到向量数据库的方法
+ 实现简单的RAG库查看功能


#### [2026-04-18~2026-04-19](./2026-04-18.md)

+ 更新[RAG说明文档](../../doc/RAG说明文档.md)
+ 实现一个初步的pdf解析工具，可以命令行调用也被封装成tools
+ 添加针对docling-tool的单元测试
+ 支持从向量数据库中删除记录

#### [2026-04-22](./2026-04-21.md)

+ 更新[RAG说明文档](../../doc/RAG说明文档.md)
+ RAG库查询封装成tool
+ 在文档解析的工具中，实现了一个基础的大文件拼接的旁路（效果还是不太好，如果有需求需要后续优化）

#### [2026-04-30](./2026-04-30.md)

主要更新了支持文档上传和文档结果下载的工作流，具体实现思路见文档

#### [2026-05-06](./2026-05-06.md)

+ 主要修复了有关路径的bug，现在支持文件输入输出路径带有中文、支持绝对路径输入，默认保存路径改在storage路径下（这样push git的时候就不会上传了）
+ 更新README，如何运行见项目的总README；另外去掉了README中之前版本硬编码工作流的说明，如果后面需要就从[这里](./2026-05-06.md)粘贴出去即可

#### [2026-05-07](./2026-05-07.md)

+ 在web-ui中添加对RAG的支持（包括增加、查询、删除）
+ web-ui支持上传Skill和Checklist
+ 支持选择的文件撤销

#### [2026-05-12](./2026-05-12.md)

+ `preflight_inputs_tool` 支持用户更自由的输入（自然语言 + 路径混写、严格校验、OpenAI 语义抽取等）
+ 新增 `thesis_outline_extract` 工具（按 PDF 目录树抽取指定章节，支持 `outline/extract` 双模式）
+ `preflight_inputs_tool` 增强章节槽位抽取（`chapter_selection`）并支持传递到新工具
+ 建立 checklist 多路并行审查 **v4** 工作流（`checklist_multi_v4`，首节点 preflight）
  新增示例工作流 `thesis_chapter_extract`

#### [2026-05-13 ~ 2026-05-14](./2026-05-14.md)

+ 新增 checklist 文本审查工作流 **v1 / v2**（`workflow_checklist_text_v1/v2`）：v1 参考文献为占位；v2 参考文献走 PDF 切片 + Docling + 实质审查
+ 新增工具 `checklist_prepare`、`thesis_chapter_route`、`references_slice_and_docling`
+ `checklist_prepare`：解析并附加「大模型避免检查的项目」至各审查包；工作流 prompt 要求 LLM 忽略该节问题
+ `thesis_chapter_route`：输出各章 `page_ranges`（闭区间），供 checker 与 `pdf_comment` 按章节范围检索
+ `pdf_comment`（节点 `pdf_annotator`）：页码区间检索 + 单页 ±5 兜底 + 页级词缓存；批注去掉调试话术；兼容 `page_idx` / multi 工作流
+ 工作流 v1/v2：`page_start`/`page_end` 替代代表页；`pdf_annotator` 改读 `annotation_formatter.result`
+ 修复批注链路：`annotation_formatter` 配置 `max_tokens: 65536`；`LlmClient` 可配置输出上限（默认 8192），避免合并列表 JSON 被截断导致 `pdf_annotator` / `offer_download` 失败
+ 新增 `checklist_text_v3` 工作流与 `check_text.py` 批处理脚本：与 v2 审查链路一致，首节点 `preflight_inputs` 设 `use_llm: false`，配合结构化 JSON 路径输入批量生成 `{原名}-checked.pdf`

#### [2026-05-22](./2026-05-22.md)

+ 设计[LaTeX 子系统分阶段路线图](../../doc/TeX_Agent%20LaTeX%20子系统分阶段实现路线图.md)，并实现**阶段 0～6**（契约 → 项目扫描 → 解析/引用/bib/约定 → ChkTeX → latexmk → issue 合并与切片 → 诊断工作流 `latex_diagnose_v0`）
+ 新增 `latex/` 包与 `latex_project` / `latex_parser` / `chktex` / `latexmk` / `latex_slice` / `latex_merge` / `latex_report` 等 Tool；`workflow/nodes.py` 提升 `__latex_project__`、`__latex_diagnostics__` 至顶层 metadata
+ 夹具 `tests/fixtures/latex/`（multifile、cross_ref、with_bib、broken_braces 等）及对应 pytest；详见 [2026-05-22.md](./2026-05-22.md) 验证命令

#### [2026-05-25 ~ 2026-05-26](./2026-05-25.md)

+ 继续实现**阶段 7**：`prompt_builder` / `suggestion` / `fix_batch`、`latex_fix_prepare` / `latex_collect_suggestions`、工作流 `latex_diagnose_v1`（L3 SimpleAgent 修复 + `__latex_suggestions__`）；`latex_diagnose_v0` 保持无 LLM
+ 重新设计阶段8及以后的[规划](../../doc/TeX_Agent%20LaTeX%20子系统分阶段实现路线图.md)
+ 实现**阶段 8**：目录监视与实时诊断/建议服务（后台服务）。新增 `WatchService` 结合 `watchdog` 监听文件修改，支持防抖增量诊断和空闲润色触发。

#### [2026-05-27](./2026-05-27.md)

+ 实现**阶段 9**：Web-UI / CLI 集成与展示。新增 `latex/watch_cli.py` 命令行工具，支持启动监视并输出人读视图；更新 `latex_report_tool` 增加 `summary` 和 `issues_top_k`；在 `ui/web/server.py` 中新增了启动、停止和轮询 LaTeX 监视状态的 FastAPI 接口。
+ 更新项目 `README.md`，添加了“LaTeX 辅助写作功能的说明”。

#### [2026-06-02](./2026-06-02.md)

+ 实现**阶段 10（独立 Ghost UI）**：新增 `latex/ghost_cli.py`、`latex/ghost_server.py`、`latex/apply_edit.py` 与 `ui/ghost/*`，支持在浏览器行间显示纠错/润色建议卡片（可拖动、可缩放、可忽略、可应用到目标 `.tex`）。
+ 阶段 10 测试补齐：新增/增强 `tests/test_latex/test_apply_edit.py`、`tests/test_latex/test_ghost_server.py`、`tests/test_latex/test_ghost_cli.py`，覆盖偏移映射、文件写回、Ghost API 关键路径与 CLI 参数透传。
+ 重新设计并更新[LaTeX 子系统分阶段路线图](../../doc/TeX_Agent%20LaTeX%20子系统分阶段实现路线图.md)：将“独立幽灵窗口”前置为阶段 10（先可用），VS Code/Cursor 扩展迁移为阶段 11（后迁入），明确 9→10→11 的演进关系。

#### [2026-06-03](./2026-06-03.md)

+ 实现路线图 **PR-10a** 的核心代码：新增 `GhostWatchPolicy`（`latex/ghost_watch_policy.py`），用于 Ghost 场景的 1 秒静默重检策略，并默认关闭自动润色。
+ Ghost 服务切换到策略化监视：`latex/ghost_server.py` 改为默认使用 `GhostWatchPolicy`，并透出 `quiet`/`auto_polish` 运行参数；`latex/ghost_cli.py` 增加 `--quiet-sec` 与 `--enable-auto-polish` 参数。
+ 增强 Ghost 刷新稳定性：`watch snapshot` 新增 `error_signature` / `error_changed`，前端 `ui/ghost/ghost.js` 改为“仅在 error 签名变化时重置卡片忽略态”，避免无新 error 时幽灵卡被反复刷新。
+ 测试补齐并通过：新增 `tests/test_latex/test_ghost_watch_policy.py`，并更新 `test_ghost_cli.py`、`test_ghost_server.py`；验证静默窗口、防抖触发、默认禁用自动润色、同 error 不重复触发 LLM。
+ 继续实现路线图 **PR-10b**：补充 `Suggestion` 纠错字段（`cause_zh` / `advice_zh`）并在 Ghost 卡片展示“报错信息/定位/原因分析/改正方案”；warning 默认不再在源码行内高亮，保持与纠错链路分离。
+ 修复 `apply_edit` 已知风险：新增 range 越界校验（超出文件行号直接拒绝应用）及 replacement 的 BOM/空字符清理，避免异常建议导致文件末尾误插入与乱码前缀。
+ PR-10b 测试补齐并通过：新增/增强 `tests/test_latex/test_apply_edit.py`、`tests/test_latex/test_ghost_watch_policy.py`、`tests/test_latex/test_ghost_server.py`，覆盖越界拒绝、BOM 清洗、warning-only 不触发 LLM、Ghost API 越界返回 400。
+ 继续实现路线图 **PR-10c**：新增 `latex/apply_compare.py` 与 `/api/apply` 的 `mode=compare`，支持“对比”模式把原文改为注释并插入建议正文；Ghost 卡片新增“对比”按钮。
+ 完成 PR-10c 前端交互：`ui/ghost/ghost.js` 增加建议范围红高亮（基于活跃纠错卡）、`应用/对比/忽略` 操作后即时清除卡片与高亮，避免残留干扰。
+ PR-10c 测试补齐并通过：新增 `tests/test_latex/test_apply_compare.py`，并增强 `tests/test_latex/test_ghost_server.py` 覆盖 compare 模式 API；相关回归共 19 项通过。
+ 实现路线图 **PR-10d**：新增主动润色后端能力（`POST /api/ghost/polish`）与 `latex/ghost_polish_prompt.py`，支持 `query + target_file + context_file` 驱动 LLM 生成润色建议并写入 `polish_suggestions`。
+ 完成 PR-10d 前端交互：`ui/ghost/index.html` 新增“主动润色”面板（目标文件选择 + 需求输入 + 触发按钮），`ui/ghost/ghost.js` 接入调用并在当前文件行内以绿色高亮展示润色建议范围。
+ PR-10d 测试补齐并通过：增强 `tests/test_latex/test_ghost_server.py`，新增主动润色成功/文件不存在用例；Ghost 相关回归共 21 项通过。