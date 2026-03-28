# Tex_Agent 论文协作智能体

本项目旨在构建一个基于多智能体架构的论文写作增强系统。项目以四种基础 Agent 为起点，演进为集成了智能动态路由、RAG长期记忆与协同机制的系统。系统覆盖从文献检索、数据可视化到 LaTeX 结构化调优的学术写作全流程，打造兼顾严谨科研辅助与人性化陪伴的智能辅助论文写作工具。

## 更新内容：

## 当前项目架构

目前参考[Tex路径下的架构设计](./Tex/README.md)，如果确认这个架构可以就把整个`Tex/`路径迁移出来，放在这外边然后大家一起写代码

## 一种可能的项目架构（混合框架langraph+autoGen，支持多agent，同时有多种范式实现）
```
Tex_Agent/
│
├── doc/                        # 文档（保持不变，建议增加架构设计文档）
│   └── architecture.md         # 【新增】记录本架构设计，方便组员理解
│
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py                     # 入口（修改为启动 LangGraph）
│
├── config/                     # 全局配置
│   ├── settings.py             # 环境变量、LLM 配置
│   └── prompts.py              # Prompt 模板（各策略共享）
│
├── state/                      # 【新增】LangGraph 状态定义
│   ├── __init__.py
│   └── schema.py               # 定义 PaperState (论文状态、任务队列、上下文引用)
│
├── context/                    # 【升级】原 memory/ 升级为上下文管理
│   ├── __init__.py
│   ├── manager.py              # 上下文管理器（统一入口）
│   ├── storage.py              # 向量库 + 文献数据库管理
│   ├── retriever.py            # 检索逻辑
│   └── compressor.py           # 上下文压缩（防止 Token 超限）
│   ├── literature_db/          # 文献存储（保持不变）
│   └── session_logs/           # 会话日志（保持不变）
│
├── strategies/                 # 【重构】原 agents/，实现不同范式
│   ├── __init__.py
│   ├── base.py                 # 【核心】定义统一接口 execute(state) -> state
│   ├── direct_strategy.py      # 对应原 simple_agent (组员 A)
│   ├── react_strategy.py       # 对应原 react_agent (组员 B)
│   ├── reflection_strategy.py  # 对应原 reflection_agent (组员 C)
│   └── plan_solve_strategy.py  # 对应原 plan_solve_agent (组员 D)
│
├── multi_agent/                # 【新增】混合多智能体支持
│   ├── __init__.py
│   └── review_team.py          # AutoGen 审稿小组 (由 Reflection 策略调用)
│
├── graph/                      # 【新增】LangGraph 编排层
│   ├── __init__.py
│   ├── workflow.py             # 定义主图流程 (边、节点、循环)
│   ├── nodes.py                # 图节点逻辑 (调用 Strategies, 更新 State)
│   └── router.py               # 动态路由 (原 router.py 移入此处)
│
├── tools/                      # 工具集 (保持不变，增强类型提示)
│   ├── __init__.py
│   ├── arxiv_search.py
│   ├── latex_parser.py
│   └── data_analyzer.py
│
├── workspace/                  # 沙箱工作区 (保持不变)
│   └── temp_latex_files/
│
└── tests/                      # 【新增】单元测试
    ├── test_strategies.py
    └── test_workflow.py
```
