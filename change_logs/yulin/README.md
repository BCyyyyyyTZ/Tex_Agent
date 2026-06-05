# qbb 开发日志索引

| 日期 | 内容摘要 |
|---|---|
| 2026-04-09 | planner + workflow 动态规划模块完整实现（AutoAgentsMASPlanner、YAMLWorkflowParser、build_dynamic_graph、make_agent_node） |
| 2026-04-13 | workflow 全动态化与调用链统一（default/task --wf/plan 同构图同执行器），清理旧模块，并修复 generic 节点历史上下文注入与消息回写重复问题 |
| 2026-04-14 | planner 轮次与 Supervisor 1～10 分制及修订边/入口；`parse_llm_json` 鲁棒重构；plan 路径传入 `context_manager`；`planner` 提示与否决逻辑调优；`workflow_parser`/`graph_builder` 小重构与非法边过滤 |
| 2026-04-22 | Checklist 注释质量优化（误报率 40%→7%）；新增4个工具：`pymupdf_parse`/`chapter_index`/`ref_checker`/`figure_ref_checker`，支持 54 页学位论文的解析与专项检查 |
| 2026-05-31 | 上下文策略配置化（`context_config.json` + `context_settings.py`）；新增 Web/CLI `auto` 模式；Plan/Task/Legacy 路由与画像/记忆权重分离；见 `2026-05-31.md` |
| 2026-06-01 | arxiv_search 重写 + 上下文 profile 化与 run_cancel/safe_print 等关键路径修复；见 `2026-06-01.md` |
| 2026-06-02 | Web UI 顶会投稿日历功能：静态数据源、AoE 倒计时、多入口与主题适配；见 `2026-06-02.md` |
| 2026-06-05 | Web UI 独立绘图工具（统计图表 + 概念示意图），顶栏「工具」弹窗入口，以及顶会日历/RAG 图标微调；见 `2026-06-05.md` |
