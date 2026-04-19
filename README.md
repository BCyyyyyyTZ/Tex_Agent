# TeX_Agent —— 基于多智能体架构的 LaTeX 论文写作增强系统

## 项目简介

TeX_Agent 是一个基于 **LangGraph + 多智能体（Multi-Agent System）** 架构的学术论文写作智能辅助系统。
系统覆盖从文献检索、LaTeX 结构优化、写作思路整理到数据可视化的学术写作全流程，
并为情感陪伴、多分支上下文管理（类 Git Branch）和自适应路由等高级功能预留了完备的扩展接口。

---

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/BCyyyyyyTZ/Tex_Agent.git
cd TeX_Agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY 等

# 4. 运行 MVP 基础链路
python main.py
```
---

## 在现有架构基础上进行修改的说明

**注意：当前版本已统一为动态工作流链路。默认、自定义、plan 都走同一套动态构图与执行器。**

### 统一工作流设计（推荐按此理解与修改）

**现在 `task` 与 `plan` 的底层执行方式一致，差异只在前置步骤（是否先规划）。**

#### 入口调用链

`task`：`main.py` -> `core/agent_cli.py` `run_task()` -> `_execute_with_app()`  
`plan`：`main.py` -> `core/agent_cli.py` `run_plan_task()` -> `_execute_with_app()`

#### 核心代码

##### 1. workflow/graph_builder.py 动态配置装配

- `build_app_from_workflow(workflow_name, ...)`：统一构建入口
- `load_workflow_graph_config(workflow_name)`：从 `workflow_registry` 读取配置
- `build_dynamic_graph(nodes, edges, ...)`：根据配置构图并执行

当前不再维护硬编码 `design/think/execute` 构图逻辑，默认工作流也走配置文件驱动：
- `config/workflow_registry.json` 中的 `default`
- 对应配置文件 `config/workflow_default_dynamic.json`

##### 2. workflow/workflow_registry.py 工作流注册

- `workflows.<name>` 支持 `file` 类型配置
- `task --wf <name> ...` 即按名称加载对应配置

##### 3. workflow/nodes.py 节点执行逻辑

当前动态节点统一使用 `make_agent_node()`：
- 从节点配置读取 `system_prompt/subtask/depends_on`
- 统一注入 JSON 输出约束
- 解析结构化输出并写入 `state["metadata"]`
- 支持将结果写入共享记忆

##### 4. config/agent_config.py 的角色

`agent_config.py` 仍可作为提示词模板来源，但当前默认执行路径优先读取  
`config/workflow_default_dynamic.json` 中的节点配置。建议以 workflow 配置为准进行维护。

#### 修改时应遵守的规约

+ 不要破坏状态契约：core/state.py 的 WorkflowState 字段名保持兼容（messages/current_node/input/output/error/metadata）。
+ 所有 workflow 修改都以配置为主（registry + workflow json/yaml），避免再引入硬编码图路径。
+ 节点返回格式统一：每个节点返回 dict，至少保证 current_node、error 语义一致；messages 继续走可合并列表。
+ Agent 接口不改签名：遵守 BaseAgent 的 run/reset/ainvoke 约束，避免影响其他实现。
+ 目前RAG开发不太成熟，请忽略RAG相关的接口和内容

### 动态planner

**plan 命令当前会先执行规划，然后复用与 task 相同的底层执行器。**

这部分是让planner agent自动生成流程的路线，目前不太能支持亲自设计图结构和agent的要求，相关说明后续补充

---

## 项目目录树结构与文件说明

```
TeX_Agent/
├── main.py                      # 程序主入口，支持 task / task --wf / plan
├── requirements.txt             # 项目依赖（langgraph, langchain, chromadb, arxiv 等）
├── .env.example                 # 环境变量示例（OPENAI_API_KEY 等，复制为 .env 使用）
├── README.md                    # 本文件
├── Framework.md                 # 框架拓展路线图
│
├── doc/                         # 相关说明文件
├── change_logs/                 # 变更记录（各成员子目录）
│
├── config/                      # 统一配置层（开发者只需关注此目录即可完成大部分配置）
│   ├── settings.py              # 全局配置：LLM 模型、API Key、RAG 分块参数、超时、重试
│   ├── agent_config.py          # 各 Agent 的 system prompt、temperature 等行为参数
│   ├── workflow_registry.json   # 工作流注册表（name -> file path）
│   ├── workflow_default_dynamic.json     # 默认工作流动态配置
│   ├── workflow_five_nodes_example.json  # 5 节点示例工作流配置
│   ├── planner_config.py        # 动态规划：温度、轮数、JSON 输出约束、parse_llm_json 等
│   └── logging_config.py        # 日志级别、格式、输出目标配置
│
├── core/                        # 核心基础层：全项目共用的数据结构与协议
│   ├── state.py                 # WorkflowState（TypedDict）：消息历史、retrieved_context 等
│   ├── message.py               # AgentMessage（Pydantic）：Agent 间标准通信载体
│   ├── exceptions.py            # 自定义异常：AgentError、ToolError、WorkflowError 等
│   └── agent_cli.py             # TeXAgentCLI：分支上下文、统一执行器、run_task/run_plan_task
│
├── context/                     # 上下文管理
│   ├── base.py
│   └── context_manager.py
├── agents/                      # 智能体模块
│   ├── base_agent.py            # BaseAgent（ABC）：定义 run/ainvoke/reset 标准接口
│   ├── simple_agent.py          # ✅ SimpleAgent：接收输入→调用 LLM→返回结果（可运行）
│   ├── react_agent.py           # [扩展] ReActAgent：Reason+Act 循环推理接口占位
│   ├── reflection_agent.py      # [扩展] ReflectionAgent：自我反思迭代接口占位
│   └── plan_and_solve_agent.py  # [扩展] PlanAndSolveAgent：任务分解执行接口占位
│
├── workflow/                     # 工作流编排模块（LangGraph）
│   ├── graph_builder.py         # ✅ 统一动态构图入口（registry -> nodes/edges -> build_dynamic_graph）
│   ├── nodes.py                 # ✅ 通用动态节点工厂 make_agent_node
│   ├── workflow_registry.py     # ✅ 工作流注册加载器
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
│   ├── base_memory.py           # BaseContext（ABC）：save/load/clear 标准接口
│   ├── context_manager.py       # ✅ ContextManager：单次运行周期内的消息记录管理（可运行）
│   ├── branch_context.py        # [扩展] BranchNode + ContextTree：类 Git 多分支上下文数据结构
│   └── factory.py
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

## 架构设计思路

本系统遵循以下核心设计原则：

1. **基于接口编程（面向抽象）**：所有 Agent、Tool、Memory、RAG 管道均依赖抽象基类（ABC）定义的接口进行交互，具体实现彼此解耦，方便 4 位开发者并行开发、Mock 测试。
2. **分层架构**：`core` → `agents/tools/memory/rag` → `workflow` → `router`，层间单向依赖，避免循环引用。
3. **最小可运行 MVP**：未标注 `[扩展]` 的模块实现完整可运行代码，可直接 `python main.py` 通过动态配置跑通 default workflow。
4. **统一动态工作流**：default / 自定义 workflow / plan 统一走配置图与 `build_dynamic_graph`，减少双轨维护成本。
5. **[扩展] 接口占位**：标注 `[扩展]` 的模块使用 ABC + `raise NotImplementedError` 占位，并附详细 Docstring，方便后续填充业务逻辑。
6. **统一配置**：所有可调参数集中在 `config/` 目录，使用者只需修改该目录下的文件即可完成配置。
7. **并发友好**：核心异步逻辑封装在 `utils/concurrency.py`，LangGraph 节点支持 `async` 执行。

---

## 数据流说明

### 标准模式（不启用 RAG）

```
用户输入
   │
   ▼
main.py  →  TeXAgentCLI.run_task / run_plan_task
               │
               ▼
          WorkflowState
          └─ retrieved_context = ""  （始终为空）
               │
      build_app_from_workflow(default)
               │
               ▼
       build_dynamic_graph(nodes, edges)
               │
        make_agent_node()
               │
    SimpleAgent.run()  →  LLM  →  AgentMessage
               │
    ContextManager.save()
               │
          最终输出结果
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


## 旧版本内容

+ 上一个复杂的框架在 [Brain-Tex/](./Brain-Tex/README.md)
+ 最早的简洁版本在 [Simple-Tex](./Simple-Tex/README.md)
+ 另一个可运行的版本暂时没有拷贝过来