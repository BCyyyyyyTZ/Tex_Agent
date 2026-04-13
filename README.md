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

**注意：硬编码的固定工作流设计 与 动态planner 的链路在当前框架下时完全分开处理的**

### 硬编码的固定工作流设计

**这是task命令走的固定工作流图结构，当前流程是：Design -> Think -> Execute**

#### 入口调用链

main.py -> core/agent_cli.py 的 run_task() -> workflow/graph_builder.py 的 build_graph()

#### 核心代码

##### 1. workflow/graph_builder.py 固定图结构与专家agent实例化

这里是硬编码图结构和“节点绑定哪个 agent”的第一现场，可以修改：**节点的集合（新增或替换）、边的关系（目前暂时只支持线性边）**

目前这里定义了design_agent、think_agent、execute_agent（*代码~103行*），**如何实例化一个agent的示例如下：**

```Python
design_agent = SimpleAgent(
    name=DESIGN_AGENT_CONFIG["name"],
    system_prompt=DESIGN_AGENT_CONFIG["system_prompt"],
    temperature=DESIGN_AGENT_CONFIG.get("temperature"),
)
```

+ 目前主要支持`SimpleAgent`，其他agent基础类型有待后续开发
+ 需要包含`name`、`system_prompt`、`temperature`三个字段
+ 可以参考下面的说明（**请参考本章节的第3小节**），在`config/agent_config.py`中添加相关配置，也可以直接在这里硬编码写死prompt、名称等信息

**创建节点函数**（*代码~124行*），*关于节点函数的具体内容见下面的介绍(**请参考本章节的第2小节**)*：

```Python
design_fn = make_design_node(
        design_agent, 
        ctx, 
        memory=design_memory or shared_memory  # 优先用专属记忆，否则用共享记忆
    )
```

然后**在图结构中添加节点node**（*代码~144行*）：

```Python
graph.add_node("design", design_fn)
```

目前暂时不支持RAG，所以将边添加在`if rag_enabled`的else分支中：

```Python
if rag_enabled:
    ...
else:
    # 目前修改图结构加在这个分支中
    graph.add_edge(START, ENTRY_NODE)
    add_linear_edges(graph)
```

+ 以上示例展示的是：**添加线性边**，对于目前已有的框架，就是Design → Think → Execute
+ 目前提供的方法`add_linear_edges()`具体信息见下方的说明，目前是一个硬编码写死的逻辑，如果需要自定义添加边，**请参考本章节的第4小节**

##### 2. workflow/nodes.py 每个节点的任务提示词与行为

这里主要是节点函数，图节点这里定义输入读取、Prompt 组装、Agent 调用、上下文/记忆写入和状态回传的相关设置

可以在这里**定义新的节点函数**（*代码~80行*）：

```Python
def make_design_node(
    agent: BaseAgent,
    ctx: BaseContext,
    memory: Optional["BaseMemory"] = None,
) -> Callable[[WorkflowState], dict]:
    def design_node(state: WorkflowState) -> dict:
        # 1. 安全获取任务输入
        raw_input = state.get('input', '')
        if hasattr(raw_input, 'content'):
            input_str = str(raw_input.content)
        elif isinstance(raw_input, str):
            input_str = raw_input
        else:
            input_str = str(raw_input)

        # 2. 构造用户消息
        user_msg = AgentMessage(
            role="user",
            content=f"请分析任务并制定设计方案：\n\n{input_str}",
            agent_name="user"
        )
        ctx.save(user_msg)

        # 3. GSSC 上下文构建
        context = ctx.build(state, memory=memory, config={
            "conv_limit": 10, "mem_limit": 3, "max_tokens": 6000, "format": "plain"
        })

        # 4. 生成 Prompt 并调用 Agent
        prompt = f"<system>你是论文架构师。请基于上下文制定结构化设计方案。</system>\n\n{context}\n\n<task>{input_str}</task>"

        try:
            raw_resp = agent.run(prompt)
            resp = _ensure_agent_message(raw_resp, "assistant", "design")
        except Exception as e:
            ...

        # 5. 保存响应到上下文
        ctx.save(resp)
        
        # 保存到长期记忆
        if memory:
            ...

        return {
            "messages": state["messages"] + [_safe_to_dict(user_msg), _safe_to_dict(resp)],
            "current_node": "design",
            "error": None,
        }
    return design_node
```

+ 可以使用`logger.info()`打印输出调试日志信息
+ 节点函数主要的流程是：**输入规范化 → 上下文构建 → `<system>/<task>` Prompt 注入 → `agent.run()` 执行 → `_ensure_agent_message()` 统一返回类型 → `_safe_to_dict()` 回写 `state["messages"]` → 返回 `current_node/error/output`**，修改或加入新的节点函数时也建议保存这个结构

##### 3. config/agent_config.py 固定的专家agent配置

这里可以**声明图节点所需的名称和系统提示词**（*代码~6行*）：

```Python
DESIGN_AGENT_CONFIG = {
    "name": "DesignAgent",
    "system_prompt": (
        ...
    ),
    "temperature": 0.5,
}
```

##### 4. config/workflow_config.py + workflow/edges.py 边的相关配置

**注意：改动图结构时，两个地方要一起改，保持一致**

**在config/workflow_config.py定义边结构的配置**，目前的示例如下：

```Python
# 节点执行顺序列表
WORKFLOW_NODES: List[str] = ["design", "think", "execute"]
# 线性边定义：(起始节点, 目标节点)
WORKFLOW_EDGES: List[Tuple[str, str]] = [
    ("design", "think"),
    ("think", "execute"),
]
# 工作流入口节点
ENTRY_NODE: str = "design"
# 工作流终止节点
FINISH_NODE: str = "execute"
```

+ 可以按照新建节点的名称和结构修改对应的线性边结构
+ **注意应该包含工作流的入口和终止节点**：ENTRY_NODE、FINISH_NODE

在workflow/edges.py中给出添加边的具体方法（*代码~16行*）：

```Python
def add_linear_edges(graph: StateGraph) -> None:
    """
    读取 config/workflow_config.py 中定义的 WORKFLOW_EDGES，
    依次为每对节点添加有向边，并将终止节点连接到 END。
    """
    for from_node, to_node in WORKFLOW_EDGES:
        graph.add_edge(from_node, to_node)

    graph.add_edge(FINISH_NODE, END) # 添加终止边
```

#### 修改时应遵守的规约

+ 不要破坏状态契约：core/state.py 的 WorkflowState 字段名保持兼容（messages/current_node/input/output/error/metadata）。
+ 固定链路与动态链路隔离：只改 build_graph() 相关路径，不改 build_dynamic_graph() / YAMLWorkflowParser / planner。
+ 节点返回格式统一：每个节点返回 dict，至少保证 current_node、error 语义一致；messages 继续走可合并列表。
+ Agent 接口不改签名：遵守 BaseAgent 的 run/reset/ainvoke 约束，避免影响其他实现。
+ 目前RAG开发不太成熟，请忽略RAG相关的接口和内容

### 动态planner

**这是plan命令走的planner设计路线**

这部分是让planner agent自动生成流程的路线，目前不太能支持亲自设计图结构和agent的要求，相关说明后续补充

---

## 项目目录树结构与文件说明

```
TeX_Agent/
├── main.py                      # 程序主入口，启动 Design→Think→Execute 基础工作流
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
│   ├── workflow_config.py       # 工作流节点顺序、边的定义（支持未来扩展为配置文件驱动）
│   ├── planner_config.py        # 动态规划：温度、轮数、JSON 输出约束、parse_llm_json 等
│   └── logging_config.py        # 日志级别、格式、输出目标配置
│
├── core/                        # 核心基础层：全项目共用的数据结构与协议
│   ├── state.py                 # WorkflowState（TypedDict）：消息历史、retrieved_context 等
│   ├── message.py               # AgentMessage（Pydantic）：Agent 间标准通信载体
│   ├── exceptions.py            # 自定义异常：AgentError、ToolError、WorkflowError 等
│   └── agent_cli.py             # TeXAgentCLI：记忆、上下文、build_graph、分支与 run_task
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
3. **最小可运行 MVP**：未标注 `[扩展]` 的模块实现完整可运行代码，可直接 `python main.py` 跑通 `Design → Think → Execute` 基础链路。
4. **RAG 可选接入**：RAG 模块以插件方式集成，通过 `build_graph(rag_pipeline=pipeline)` 一行代码开启，图结构自动扩展为 `Design → Retrieve → Think → Execute`，不传参则保持原有三节点结构，不破坏现有测试。
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