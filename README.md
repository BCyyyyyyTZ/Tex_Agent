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

# 4. 运行 MVP 基础链路（不启用 RAG）
python main.py

# 5. 运行测试（包含 RAG 测试，无需安装 chromadb）
pytest tests/ -v
```
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
│   ├── base_memory.py           # BaseContext（ABC）：save/load/clear 标准接口
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