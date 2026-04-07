# TeX_Agent —— 基于多智能体架构的 LaTeX 论文写作增强系统

## 项目简介

TeX_Agent 是一个基于 **LangGraph + 多智能体（Multi-Agent System）** 架构的学术论文写作智能辅助系统。
系统覆盖从文献检索、LaTeX 结构优化、写作思路整理到数据可视化的学术写作全流程，
并为情感陪伴、多分支上下文管理（类 Git Branch）和自适应路由等高级功能预留了完备的扩展接口。

---

## 架构设计思路

本系统遵循以下核心设计原则：

1. **基于接口编程（面向抽象）**：所有 Agent、Tool、Memory、RAG 管道均依赖抽象基类（ABC）定义的接口进行交互，具体实现彼此解耦，方便 4 位开发者并行开发、Mock 测试。
2. **分层架构**：`core` → `agents/tools/memory/rag` → `workflow` → `router`，层间单向依赖，避免循环引用。
3. **最小可运行 MVP**：未标注 `[扩展]` 的模块实现完整可运行代码，可直接 `python main.py` 跑通 `Design → Think → Execute` 基础链路。
4. **RAG 可选接入**：RAG 模块以插件方式集成，通过 `build_graph(rag_pipeline=pipeline)` 一行代码开启，图结构自动扩展为 `Design → Retrieve → Think → Execute`，不传参则保持原有三节点结构，不破坏现有测试。
5. **[扩展] 接口占位**：标注 `[扩展]` 的模块使用 ABC + `raise NotImplementedError` 占位，并附详细 Docstring，方便后续填充业务逻辑。
6. **统一配置**：所有可调参数集中在 `config/` 目录，使用者只需修改该目录下的文件即可完成配置。
7. **并发友好**：核心异步逻辑封装在 `utils/concurrency.py`，LangGraph 节点支持 `async` 执行。

---

## 项目目录树结构与文件说明

```
TeX_Agent/
├── main.py                      # 程序主入口，启动 Design→Think→Execute 基础工作流
├── requirements.txt             # 项目依赖（langgraph, langchain, chromadb, arxiv 等）
├── .env.example                 # 环境变量示例（OPENAI_API_KEY 等，复制为 .env 使用）
├── README.md                    # 本文件
│
├── config/                      # 统一配置层（开发者只需关注此目录即可完成大部分配置）
│   ├── settings.py              # 全局配置：LLM 模型、API Key、RAG 分块参数、超时、重试
│   ├── agent_config.py          # 各 Agent 的 system prompt、temperature 等行为参数
│   ├── workflow_config.py       # 工作流节点顺序、边的定义（支持未来扩展为配置文件驱动）
│   └── logging_config.py        # 日志级别、格式、输出目标配置
│
├── core/                        # 核心基础层：全项目共用的数据结构与协议
│   ├── state.py                 # WorkflowState（TypedDict）：消息历史、retrieved_context 等
│   ├── message.py               # AgentMessage（Pydantic）：Agent 间标准通信载体
│   └── exceptions.py            # 自定义异常：AgentError、ToolError、WorkflowError 等
│
├── agents/                      # 智能体模块
│   ├── base_agent.py            # BaseAgent（ABC）：定义 run/ainvoke/reset 标准接口
│   ├── simple_agent.py          # ✅ SimpleAgent：接收输入→调用 LLM→返回结果（可运行）
│   ├── react_agent.py           # [扩展] ReActAgent：Reason+Act 循环推理接口占位
│   ├── reflection_agent.py      # [扩展] ReflectionAgent：自我反思迭代接口占位
│   └── plan_and_solve_agent.py  # [扩展] PlanAndSolveAgent：任务分解执行接口占位
│
├── workflow/                     # 工作流编排模块（LangGraph）
│   ├── graph_builder.py         # ✅ 构建并编译 LangGraph StateGraph；支持可选 RAG 注入
│   ├── nodes.py                 # ✅ design/think/execute/retrieve 节点工厂函数
│   ├── edges.py                 # ✅ 基础线性边定义；[扩展] 条件边路由接口占位
│   └── workflow_parser.py       # [扩展] 解析用户 YAML/JSON 配置，动态组装 Graph 节点
│
├── rag/                          # ✅ RAG 检索增强生成模块（可运行）
│   ├── __init__.py              # 模块公共导出：BaseRetriever、BaseRAGPipeline、RAGPipeline
│   ├── base_retriever.py        # ✅ BaseRetriever + BaseRAGPipeline（ABC）：检索器抽象接口
│   ├── document_loader.py       # ✅ 文档加载与分块：chunk_text / load_and_chunk
│   ├── vector_store.py          # ✅ ChromaRetriever：基于 ChromaDB 的本地向量检索实现
│   └── rag_pipeline.py          # ✅ RAGPipeline：index_text / index_file / retrieve 管道
│
├── tools/                        # 工具与技能模块（可插拔）
│   ├── base_tool.py             # ✅ BaseTool（ABC）：name/description/run/arun 标准接口
│   ├── arxiv_tool.py            # ✅ ArxivSearchTool：调用 arXiv API 检索文献（可运行）
│   ├── latex_parser.py          # [扩展] LaTeXParserTool：语法检查、AST 解析接口占位
│   ├── visualization_tool.py    # [扩展] VisualizationTool：Matplotlib/Seaborn 接口占位
│   └── image_gen_tool.py        # [扩展] ImageGenTool：DALL-E / SD API 接口占位
│
├── memory/                       # 记忆与知识增强模块
│   ├── base_memory.py           # BaseMemory（ABC）：save/load/clear 标准接口
│   ├── context_manager.py       # ✅ ContextManager：单次运行周期内的消息记录管理（可运行）
│   ├── branch_context.py        # [扩展] BranchNode + ContextTree：类 Git 多分支上下文数据结构
│   └── vector_store.py          # [扩展] VectorStoreBase：向量库（RAG）读写接口占位
│
├── router/                       # 路由与控制模块
│   ├── base_router.py           # [扩展] BaseRouter（ABC）：根据任务复杂度动态分配 Agent 接口
│   └── planner.py               # [扩展] MASPlanner（ABC）：任务分解、子任务验证接口
│
├── security/                     # 安全与权限模块
│   └── middleware.py            # [扩展] SecurityMiddleware（ABC）：权限拦截器、数据脱敏接口
│
├── utils/                        # 通用工具层
│   ├── logger.py                # 统一日志封装，基于 logging_config 初始化 Logger
│   └── concurrency.py           # asyncio 并发工具：run_async、gather_with_timeout 等封装
│
└── tests/                        # 测试模块
    ├── conftest.py              # pytest fixtures：Mock BaseAgent、MockTool、初始化 State
    ├── test_agents/
    │   └── test_simple_agent.py # SimpleAgent 单元测试
    ├── test_tools/
    │   └── test_arxiv_tool.py   # ArxivSearchTool 单元测试
    ├── test_workflow/
    │   └── test_graph_builder.py # 工作流完整链路集成测试
    ├── test_memory/
    │   └── test_context_manager.py # ContextManager 单元测试
    └── test_rag/
        └── test_rag_pipeline.py  # ✅ RAGPipeline / ChromaRetriever / retrieve_node 单元测试
```

---

## 数据流说明

### 标准模式（不启用 RAG）

```
用户输入
   │
   ▼
main.py  →  build_graph(context_manager=ctx)
               │
               ▼
          WorkflowState
          └─ retrieved_context = ""  （始终为空）
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
design_node  think_node  execute_node
    │          │          │
    └──────────┴──────────┘
               │
    SimpleAgent.run()  →  LLM  →  AgentMessage
               │
    ContextManager.save()
               │
          最终输出结果
```

### RAG 增强模式

```
用户输入
   │
   ▼
main.py  →  build_graph(context_manager=ctx, rag_pipeline=pipeline)
               │
               ▼
          WorkflowState
               │
    ┌──────────┼──────────┬──────────────┐
    ▼          ▼          ▼              ▼
design_node  retrieve_node  think_node  execute_node
    │             │           │              │
    │         RAGPipeline     │ ←── retrieved_context 注入 Prompt
    │         .retrieve()     │
    │             │           │
    └─────────────┴───────────┘
               │
    SimpleAgent.run()  →  LLM（结合知识库内容）
               │
          最终输出结果
```

---

## RAG 快速使用指南

### 安装 RAG 依赖

```bash
pip install chromadb>=0.5.0
```

> 首次运行时 ChromaDB 会自动下载约 40MB 的 ONNX Embedding 模型（需联网），此后完全离线运行，无需 API Key。

### 代码示例

```python
from rag.rag_pipeline import RAGPipeline
from workflow.graph_builder import build_graph
from memory.context_manager import ContextManager

# 1. 创建 RAG 管道并索引文档
pipeline = RAGPipeline()                          # 内存模式（进程退出后清空）
pipeline.index_file("papers/survey.md")           # 索引 Markdown 文件
pipeline.index_text("Transformer 使用多头注意力机制...", source="note.txt")

# 2. 构建启用 RAG 的工作流图
ctx = ContextManager()
app = build_graph(context_manager=ctx, rag_pipeline=pipeline)

# 3. 执行工作流
result = app.invoke({
    "messages": [],
    "current_node": "",
    "input": "帮我检索关于注意力机制的研究现状",
    "output": "",
    "error": None,
    "metadata": {},
    "retrieved_context": "",   # retrieve_node 会自动填充此字段
})
print(result["output"])

# 4. 持久化模式（重启后知识库保留）
pipeline_persistent = RAGPipeline(persist_directory="./knowledge_base")
```

### 配置 RAG 参数（`config/settings.py` 或 `.env`）

| 配置项                  | 默认值 | 说明                               |
|------------------------|--------|----------------------------------|
| `rag_chunk_size`       | 500    | 文档分块大小（字符数）              |
| `rag_chunk_overlap`    | 50     | 相邻块重叠字符数                   |
| `rag_top_k`            | 5      | 每次检索返回的最大片段数            |
| `RAG_PERSIST_DIR`      | 空     | 向量库持久化路径（空=内存模式）     |

---

## 团队协作分工建议

> 4 位开发者可以基于以下分工**完全并行开发**，各模块仅通过 `core/` 层的抽象接口交互，互不依赖具体实现。
> 每个步骤均附有**独立可运行的测试命令**，开发者无需等待其他人完成即可验证自己的工作。

### 跨开发者依赖总览

```
core/ (AgentMessage, WorkflowState)   ← 所有人共同依赖，禁止随意修改字段
       │
  ┌────┴─────────────────────────────┐
  │                                  │
开发者B (BaseAgent 接口)         开发者D (BaseMemory / BaseRAGPipeline 接口)
  │                                  │
  └────────────┬─────────────────────┘
               │
          开发者A (workflow/ 编排层，消费上述接口)
               │
          开发者C (tools/ 独立模块，最终由开发者B集成)
```

> **接口变更约定**：`AgentMessage` 和 `WorkflowState` 字段只增不删不改名；
> 修改 `BaseAgent.run()` / `BaseMemory.save()` 等核心接口签名前必须提前通知全组。

---

### 开发者 A —— 工作流与编排（Workflow Engineer）

**负责目录**：`workflow/`、`core/`、`main.py`、`tests/test_workflow/`

#### ✅ 已完成（可直接运行）

- `graph_builder.py`：构建 Design → Think → Execute 基础图，支持可选 RAG 注入
- `nodes.py`：design / think / execute / retrieve 四个节点工厂函数
- `edges.py`：线性边 `add_linear_edges()`，条件边接口占位
- `workflow_parser.py`：`NodeConfig` / `EdgeConfig` 数据结构 + `WorkflowParser` ABC，含 `from_task_plan()` 接口占位

#### Step A-1：实现条件边路由函数

**目标文件**：`workflow/edges.py`
**任务**：实现 `make_conditional_router()`，支持根据 `state["error"]` 或自定义字段决定下一个节点。

```python
# edges.py 中 make_conditional_router 的期望行为：
def make_conditional_router(routing_map: dict):
    def router(state: WorkflowState) -> str:
        if state.get("error"):
            return routing_map.get("error", END)
        return routing_map.get("default", END)
    return router
```

**测试**：

```bash
pytest tests/test_workflow/test_edges.py -v
# 验证：error=None 时走 default 分支，error 非空时走 error 分支
```

---

#### Step A-2：实现 YAML/JSON 工作流配置解析器

**目标文件**：`workflow/workflow_parser.py`（实现 `WorkflowParser` 子类 `YAMLWorkflowParser`）
**任务**：读取 YAML 配置文件，生成 `NodeConfig` / `EdgeConfig` 列表，调用 `build_graph()` 组装图。

**示例 YAML**（`config/workflows/basic.yaml`）：

```yaml
nodes:
  - id: design
    type: agent
    agent: DesignAgent
  - id: execute
    type: agent
    agent: ExecuteAgent
edges:
  - from: design
    to: execute
entry: design
```

**测试**：

```bash
pytest tests/test_workflow/test_workflow_parser.py -v
# 验证：YAML 解析后节点/边数量正确，build_graph 返回可 invoke 的图
```

---

#### Step A-3：实现 `from_task_plan()` 翻译逻辑

**目标文件**：`workflow/workflow_parser.py`（在 `YAMLWorkflowParser` 中重写 `from_task_plan()`）
**任务**：将 `MASPlanner` 输出的 `TaskPlan` 翻译为 `NodeConfig` + `EdgeConfig`，接入 `build_graph()`。
**前置条件**：等待开发者 D 完成 Step D-3（MASPlanner 可输出真实 TaskPlan）；在此之前用 Mock TaskPlan 开发测试。

```python
# conftest.py 中可用的 Mock TaskPlan（无需等待开发者D）
mock_plan = TaskPlan(
    plan_id="test-001",
    original_task="写论文引言",
    subtasks=["规划结构", "检索文献", "撰写草稿"],
    assigned_agents={0: "DesignAgent", 1: "ArxivTool", 2: "ExecuteAgent"},
)
```

**测试**：

```bash
pytest tests/test_workflow/test_workflow_parser.py::test_from_task_plan -v
# 验证：TaskPlan 正确翻译为 3 个节点 + 2 条串行边
```

---

#### Step A-4：用动态图替换硬编码 `graph_builder.py`

**目标文件**：`workflow/graph_builder.py`
**任务**：将 `build_graph()` 改为调用 `WorkflowParser.from_task_plan()` 或 `YAMLWorkflowParser.load_config()`，移除硬编码的 `SimpleAgent` 实例化。
**前置条件**：Step A-2、A-3、D-3 全部完成。

**测试**：

```bash
pytest tests/test_workflow/test_graph_builder.py -v
# 验证：动态图与原硬编码图在相同输入下输出一致
```

---

### 开发者 B —— 智能体模块（Agent Engineer）

**负责目录**：`agents/`、`config/agent_config.py`、`tests/test_agents/`

#### ✅ 已完成（可直接运行）

- `base_agent.py`：`BaseAgent` ABC，定义 `run` / `ainvoke` / `reset` / `get_history` 接口
- `simple_agent.py`：`SimpleAgent`，接入 LangChain + DeepSeek/OpenAI，有界历史管理

#### Step B-1：实现 `ReflectionAgent`

**目标文件**：`agents/reflection_agent.py`
**任务**：实现"生成 → 自我批评 → 改进"的迭代推理循环，默认最多 2 轮反思。

```python
# 期望接口（继承 BaseAgent，run 方法内部循环）：
class ReflectionAgent(BaseAgent):
    def run(self, message: AgentMessage) -> AgentMessage:
        draft = self._generate(message)
        critique = self._reflect(draft)
        if self._is_satisfactory(critique):
            return draft
        return self._improve(draft, critique)
```

**测试**：

```bash
pytest tests/test_agents/test_reflection_agent.py -v
# Mock LLM：第1次返回草稿，第2次返回改进版，验证 run() 返回改进版
```

---

#### Step B-2：实现 `ReActAgent`

**目标文件**：`agents/react_agent.py`
**任务**：实现 Reason + Act 循环，每轮判断是否需要调用工具，最多循环 N 次后输出最终答案。
**前置条件**：开发者 C 的 Step C-1 完成（`ArxivSearchTool` 可运行），在此之前用 `MockTool` 开发。

```bash
pytest tests/test_agents/test_react_agent.py -v
# 验证：任务需要工具时，工具被调用 1 次；不需要工具时，直接返回答案
```

---

#### Step B-3：实现 `PlanAndSolveAgent`

**目标文件**：`agents/plan_and_solve_agent.py`
**任务**：实现 plan() → 拆分子任务列表，solve() → 逐步执行子任务，aggregate() → 汇总最终结果。

```bash
pytest tests/test_agents/test_plan_and_solve_agent.py -v
# 验证：给定复杂任务，plan 阶段返回 ≥2 个子任务；solve 阶段对每个子任务独立生成结果
```

---

#### Step B-4：为 `SimpleAgent.run()` 接入工具调用

**目标文件**：`agents/simple_agent.py`（填充 TODO 注释处）
**任务**：在 LLM 返回后检测工具调用意图，执行工具，将结果二次传入 LLM 生成最终回答。
**前置条件**：Step B-2 完成（已有工具调用逻辑可参考）。

```bash
pytest tests/test_agents/test_simple_agent.py::test_tool_calling -v
# 验证：LLM 指定调用 ArxivSearchTool 时，工具被实际执行，最终输出包含工具结果
```

---

### 开发者 C —— 工具与技能模块（Tools Engineer）

**负责目录**：`tools/`、`tests/test_tools/`

#### ✅ 已完成（可直接运行）

- `base_tool.py`：`BaseTool` ABC，定义 `run` / `arun` 标准接口
- `arxiv_tool.py`：`ArxivSearchTool`，调用 arXiv API 检索文献

#### Step C-1：补全 `ArxivSearchTool` 测试与集成验证

**目标文件**：`tests/test_tools/test_arxiv_tool.py`
**任务**：补充网络异常时返回 `ToolResult(success=False)` 的测试；验证工具可被 `ReActAgent` 正常调用。

```bash
pytest tests/test_tools/test_arxiv_tool.py -v
# 验证：正常检索返回 success=True；网络超时返回 success=False, error 非空
```

---

#### Step C-2：实现 `LaTeXParserTool`

**目标文件**：`tools/latex_parser.py`
**任务**：解析 `.tex` 文件，返回章节结构列表、语法错误列表（可用正则实现 MVP 版）。

```python
# 期望 ToolResult.output 格式（JSON 字符串）：
{
  "sections": ["Abstract", "Introduction", "Method"],
  "errors": ["line 42: unclosed \\begin{equation}"]
}
```

```bash
pytest tests/test_tools/test_latex_parser.py -v
# 验证：标准 .tex 文件正确提取章节；含错误语法的文件返回 errors 非空列表
```

---

#### Step C-3：实现 `VisualizationTool`

**目标文件**：`tools/visualization_tool.py`
**任务**：接收数据字典和图表类型，生成图片文件并返回文件路径。

```bash
pytest tests/test_tools/test_visualization_tool.py -v
# 验证：传入折线图数据后，输出路径文件存在且为有效图片格式
```

---

#### Step C-4：实现 `ImageGenTool`

**目标文件**：`tools/image_gen_tool.py`
**任务**：接入 DALL-E / Stable Diffusion API，接收 prompt 返回图片 URL 或本地路径。

```bash
pytest tests/test_tools/test_image_gen_tool.py -v
# Mock API 调用，验证返回的 ToolResult.metadata["image_url"] 格式正确
```

---

### 开发者 D —— 记忆、RAG 与基础设施（Memory & Infra Engineer）

**负责目录**：`memory/`、`rag/`、`router/`、`security/`、`utils/`、`config/settings.py`、`tests/test_memory/`、`tests/test_rag/`

#### ✅ 已完成（可直接运行）

- `context_manager.py`：`ContextManager`，基于 `deque` 的有界消息历史管理
- `rag/`：`ChromaRetriever` + `RAGPipeline`，端到端索引与本地向量检索

#### Step D-1：实现 `BranchContext`（多分支上下文）

**目标文件**：`memory/branch_context.py`
**任务**：实现 `ContextTree` 类，支持 `create_branch(name)` / `switch_branch(name)` / `merge_branch(src, dst)` 操作，每个分支维护独立的消息历史。

```bash
pytest tests/test_memory/test_branch_context.py -v
# 验证：branch_a 和 branch_b 的消息历史完全隔离；merge 后 dst 包含 src 的消息
```

---

#### Step D-2：实现 `RuleBasedRouter`（规则路由器）

**目标文件**：`router/rule_based_router.py`（新建）
**任务**：继承 `BaseRouter`，实现基于关键词和任务长度的规则路由：
- 任务 < 50 字 → `"simple"` → `SimpleAgent`
- 含"分析""比较""多篇" → `"medium"` → `ReActAgent`
- 含"完整""规划""系统" → `"complex"` → `PlanAndSolveAgent`

```bash
pytest tests/test_router/test_rule_based_router.py -v
# 验证：三类关键词分别路由到正确的 Agent 类型；置信度在合理范围内
```

---

#### Step D-3：实现 `LLMPlanner`（基于 LLM 的任务分解器）

**目标文件**：`router/llm_planner.py`（新建，继承 `MASPlanner`）
**任务**：实现 `decompose()`（LLM 生成子任务列表）和 `assign()`（调用 `RuleBasedRouter` 为每个子任务选 Agent）。
**前置条件**：Step D-2 完成。

```bash
pytest tests/test_router/test_llm_planner.py -v
# Mock LLM 返回固定子任务列表，验证 assign() 正确填充 assigned_agents 字典
```

---

#### Step D-4：实现 `to_graph_config()` 翻译逻辑

**目标文件**：`router/llm_planner.py`（重写 `MASPlanner.to_graph_config()`）
**任务**：将 `TaskPlan.subtasks` + `assigned_agents` 翻译为 `NodeConfig` + `EdgeConfig` 列表：
- 含 "validate" / "reflect" 子任务 → 生成带条件的 `EdgeConfig`
- 其他子任务 → 生成线性 `EdgeConfig`
**前置条件**：Step D-3 完成；开发者 A 的 Step A-3 完成（`from_task_plan()` 接口可用）。

```bash
pytest tests/test_router/test_llm_planner.py::test_to_graph_config -v
# 验证：4 个子任务生成 4 个 NodeConfig；校验类子任务的 EdgeConfig.condition 非 None
```

---

#### Step D-5：RAG 增强（多类别 / 混合检索 / Reranker）

**目标文件**：`memory/vector_store.py`（实现 `VectorStoreBase`）、`rag/rag_pipeline.py`（扩展）
**任务**：
- 实现 `VectorStoreBase` 支持多类别知识库（论文库 / 专家库 / 用户库分库管理）
- 在 `RAGPipeline` 中添加 BM25 混合检索和 Reranker 支持

```bash
pytest tests/test_rag/ -v
# 验证：多类别检索时仅返回指定类别的文档；混合检索结果比纯向量检索相关性更高
```

---

### 各步骤之间的依赖关系与推荐开发顺序

```
第一阶段（完全并行，无跨人依赖）
  开发者A: Step A-1（条件边）
  开发者B: Step B-1（ReflectionAgent）
  开发者C: Step C-1（ArxivSearchTool 测试补全）
  开发者D: Step D-1（BranchContext）+ Step D-2（RuleBasedRouter）

第二阶段（轻度依赖，可并行）
  开发者A: Step A-2（YAML 解析器）         ← 无依赖
  开发者B: Step B-2（ReActAgent）           ← 建议等 C-1 完成
  开发者C: Step C-2（LaTeXParserTool）      ← 无依赖
  开发者D: Step D-3（LLMPlanner）           ← 依赖 D-2

第三阶段（跨人依赖，需协调）
  开发者A: Step A-3（from_task_plan）       ← 依赖 D-3
  开发者B: Step B-3（PlanAndSolveAgent）    ← 无依赖
  开发者C: Step C-3（VisualizationTool）    ← 无依赖
  开发者D: Step D-4（to_graph_config）      ← 依赖 D-3 + A-3

第四阶段（系统集成）
  开发者A: Step A-4（动态图替换）           ← 依赖 A-3 + D-4
  开发者B: Step B-4（工具调用集成）         ← 依赖 B-2 + C-1
  开发者C: Step C-4（ImageGenTool）         ← 无依赖
  开发者D: Step D-5（RAG 增强）             ← 无跨人依赖
```

---

## 快速开始

```bash
# 1. 克隆项目
git clone <repo_url>
cd TeX_Agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY 等

# 4. 运行 MVP 基础链路（不启用 RAG）
python main.py

# 5. 运行测试（包含 RAG 测试，无需安装 chromadb）
pytest tests/ -v
```

---

## 技术栈

| 层次 | 技术选型 |
|------|----------|
| 工作流编排 | LangGraph |
| LLM 调用 | LangChain + OpenAI（兼容 DeepSeek 等） |
| 数据验证 | Pydantic v2 |
| 文献检索 | arxiv Python SDK |
| 向量数据库 | ChromaDB（本地嵌入式，无需独立服务） |
| Embedding | all-MiniLM-L6-v2（ChromaDB 默认，ONNX 本地运行） |
| 异步并发 | asyncio |
| 日志 | Python logging |
| 测试 | pytest + pytest-asyncio |

---

## 扩展路线图

- [x] **RAG 检索增强生成**（ChromaDB + 本地 Embedding）
- [ ] [扩展] ReActAgent / ReflectionAgent / PlanAndSolveAgent
- [ ] [扩展] 条件边与动态路由（add_conditional_edges）
- [ ] [扩展] 多分支上下文（类 Git Branch）
- [ ] [扩展] RAG 多类别知识库（论文库、专家库分库检索）
- [ ] [扩展] RAG 混合检索（向量 + BM25）+ Reranker
- [ ] [扩展] RAG 异步批量索引
- [ ] [扩展] LaTeX 解析与语法检查
- [ ] [扩展] 数据可视化与图像生成
- [ ] [扩展] 自适应路由与 MAS Planner
- [ ] [扩展] 安全与权限中间件
- [ ] [扩展] 用户自定义工作流（YAML/JSON 配置驱动）
- [ ] [扩展] Web UI 界面

## 旧版本内容

+ 上一个复杂的框架在 [Brain-Tex/](./Brain-Tex/README.md)
+ 最早的简洁版本在 [Simple-Tex](./Simple-Tex/README.md)
+ 另一个可运行的版本暂时没有拷贝过来