# Task / Plan Prompt 注入地图（审计文档）

本文用于说明：`task` 与 `plan` 两条链路中，LLM 最终收到的 prompt 由哪些片段组成、这些片段在哪里注入、改哪里会生效。

## 1. 总览：两条链路的区别

- `task`：读取工作流注册表中的静态配置（默认是 `config/workflow_default_dynamic.json`），直接构图执行。
- `plan`：先由 PlanAgent 生成节点配置（`system_prompt/subtask/depends_on`），再转成动态图执行。
- 共同点：两条链路最终都走 `workflow/nodes.py` 的 `make_generic_agent_node()` 进行统一拼接，因此很多“公共注入”是共享的。

## 2. 入口与构图位置

### 2.1 task 链路

- 入口函数：`core/agent_cli.py` 的 `run_task()`
- 构图入口：`core/agent_cli.py` 的 `_build_app_for_workflow()` -> `workflow/graph_builder.py` 的 `build_app_from_workflow()`
- 默认工作流来源：
  - 注册表：`config/workflow_registry.json`
  - 默认配置文件：`config/workflow_default_dynamic.json`

### 2.2 plan 链路

- 入口函数：`core/agent_cli.py` 的 `run_plan_task()`
- 规划阶段：
  - PlanAgent 生成：`router/planner.py` 的 `_plan_agent_call()`
  - Supervisor 审核：`router/planner.py` 的 `_supervisor_call()`
- 翻译为节点配置：
  - `workflow/workflow_parser.py` 的 `_translate_plan_to_graph_config()`
- 构图执行：
  - `workflow/workflow_parser.py` 的 `build_graph()`
  - 最终进入 `workflow/graph_builder.py` 的 `build_dynamic_graph()`

## 3. 共享注入（task / plan 都会生效）

以下内容由 `workflow/nodes.py` 在每个节点执行时统一拼接：

1. **Persona 注入（system 段头部）**
   - 注入调用：`persona_memory.format_for_prompt()`
   - 代码位置：`workflow/nodes.py`（`persona_head = persona_memory.format_for_prompt()`）
   - 文案来源：`memory/persona_memory.py` 的 `format_for_prompt()`

2. **节点角色提示（system_prompt）**
   - 来源：`node_config["system_prompt"]`
   - task：来自 `config/workflow_default_dynamic.json`
   - plan：来自 PlanAgent 生成并经 `workflow_parser` 翻译后的节点配置

3. **单次流水线契约**
   - 常量：`SINGLE_TURN_NODE_CONTRACT`
   - 定义：`config/planner_config.py`
   - 注入：`workflow/nodes.py`（`+ SINGLE_TURN_NODE_CONTRACT`）

4. **终节点交付判据（仅终节点）**
   - 常量：`FINAL_DELIVERY_SYSTEM_ADDON`
   - 定义：`config/planner_config.py`
   - 注入条件：`is_terminal == True`
   - 注入位置：`workflow/nodes.py`（`terminal_addon`）

5. **强制 JSON 输出格式**
   - 常量：`NODE_OUTPUT_FORMAT_INSTRUCTION`
   - 定义：`config/planner_config.py`
   - 注入：`workflow/nodes.py`（`+ NODE_OUTPUT_FORMAT_INSTRUCTION`）

6. **入口节点 persona 写回约束（仅入口节点）**
   - 常量：`PERSONA_ENTRY_NODE_FORMAT_ADDON`
   - 定义：`config/planner_config.py`
   - 注入条件：`is_entry_node == True`
   - 注入位置：`workflow/nodes.py`（`entry_addon`）

7. **用户任务 + 上下文拼接模板**
   - 拼接位置：`workflow/nodes.py` 中 `prompt = (...)`
   - 拼接段落顺序：
     - `[你的具体任务]`（`subtask`）
     - `full_system_prompt`
     - `[历史上下文]`（`ctx.build(...)`）
     - `[原始任务]`（`state["input"]`）
     - `[上游节点输出]`（依赖节点 `summary/result`）

## 4. 上下文注入（history / metadata_chain / upstream）

### 4.1 历史上下文来源

- 注入调用：`workflow/nodes.py` -> `ctx.build(...)`
- 具体实现：`context/context_manager.py` 的 `build()`
- 两种形态：
  - `<context type='history'>`：有 `state.messages` 时使用
  - `<context type='metadata_chain'>`：无窗口消息且 `synthetic_metadata_history=True` 时使用

### 4.2 metadata_chain 截断策略

- 实现：`context/context_manager.py` 的 `format_metadata_chain_for_prompt()`
- 截断参数：`METADATA_CHAIN_RESULT_MAX_CHARS`
- 配置位置：`config/planner_config.py`
- 日志表现：`补充产出(截断): ...`

### 4.3 upstream 注入与去重

- 实现：`workflow/nodes.py` 的 `_upstream_blocks(...)`
- 规则：
  - 默认注入依赖节点 `summary`
  - `result` 使用 `UPSTREAM_RESULT_MAX_CHARS` 截断
  - 若 `metadata_chain` 已覆盖该节点，则上游块仅保留摘要（减重复）
- 参数定义：`config/planner_config.py`

## 5. task 专属注入来源

task 不经过 PlanAgent，节点角色文案主要由以下文件直接决定：

- `config/workflow_default_dynamic.json`
  - 每个节点的 `config.system_prompt`
  - 每个节点的 `config.subtask`
  - `depends_on` 决定上游注入关系

若你要改 task 默认行为，优先改这个文件（再配合公共注入常量）。

## 6. plan 专属注入来源

plan 比 task 多了“规划提示词注入”层：

1. **PlanAgent 提示词**
   - 位置：`router/planner.py` 的 `_plan_agent_call()`
   - 内容包含：规划原则、推荐节点结构、单次流水线契约、输出 schema（`PLAN_OUTPUT_SCHEMA`）

2. **Supervisor 提示词**
   - 位置：`router/planner.py` 的 `_supervisor_call()`
   - 内容包含：拒绝规则、结构合法性、低质量方案修订输出 schema（`SUPERVISOR_OUTPUT_SCHEMA`）

3. **Plan 结果转 NodeConfig**
   - 位置：`workflow/workflow_parser.py` 的 `_translate_plan_to_graph_config()`
   - 作用：把 `plan.assigned_agents[node_id].system_prompt/subtask/depends_on` 变成运行时节点配置

重要：plan 生成出来的节点文案，会再经过第 3 章的共享注入（二次约束）。

## 7. 终节点交付守卫（运行时告警）

- 实现位置：`workflow/nodes.py` 的 `_detect_terminal_delivery_risks()`
- 触发时机：`is_terminal` 节点输出后
- 关键词配置：
  - `FINAL_DELIVERY_GUARD_QUESTION_KEYWORDS`
  - `FINAL_DELIVERY_GUARD_RESTATE_KEYWORDS`
  - 定义于 `config/planner_config.py`
- 行为：只打日志告警，不阻断执行

## 8. 一页式“改哪里会影响什么”

- 想改所有节点统一约束（task+plan）：`config/planner_config.py` + `workflow/nodes.py`
- 想改 task 默认三节点人设：`config/workflow_default_dynamic.json`
- 想改 plan 的节点命名/结构偏好：`router/planner.py` 的 `_plan_agent_call()`
- 想改 plan 审核收敛逻辑：`router/planner.py` 的 `_supervisor_call()` 与本地 reject rules
- 想改历史注入噪声：`context/context_manager.py`（`build/format_metadata_chain_for_prompt`）
- 想改上游注入噪声：`workflow/nodes.py`（`_upstream_blocks`）

## 9. 建议的查验顺序

1. 看生成节点配置来源：
   - task：`config/workflow_default_dynamic.json`
   - plan：`router/planner.py` 日志 + `workflow_parser` 翻译结果
2. 看运行时最终 prompt 结构：`logs/llm_interactions_trace.txt`
3. 看上下文噪声与截断是否符合预期：
   - 搜索 `补充产出(截断)`、`<context type='history'>`、`<context type='metadata_chain'>`
4. 看终节点交付告警：
   - 搜索 `终节点交付告警`

