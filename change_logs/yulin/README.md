# qbb 开发日志索引

| 日期 | 内容摘要 |
|---|---|
| 2026-04-09 | planner + workflow 动态规划模块完整实现（AutoAgentsMASPlanner、YAMLWorkflowParser、build_dynamic_graph、make_agent_node） |
| 2026-04-13 | workflow 全动态化与调用链统一（default/task --wf/plan 同构图同执行器），清理旧模块，并修复 generic 节点历史上下文注入与消息回写重复问题 |
| 2026-04-14 | planner 轮次与 Supervisor 1～10 分制及修订边/入口；`parse_llm_json` 鲁棒重构；plan 路径传入 `context_manager`；`planner` 提示与否决逻辑调优；`workflow_parser`/`graph_builder` 小重构与非法边过滤 |
| 2026-04-22 | Checklist 注释质量优化（误报率 40%→7%）；新增4个工具：`pymupdf_parse`/`chapter_index`/`ref_checker`/`figure_ref_checker`，支持 54 页学位论文的解析与专项检查 |
