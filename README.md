# Tex_Agent 论文协作智能体

本项目旨在构建一个基于多推理框架的论文写作增强系统，通过集成四种 Agent 架构，解决学术写作中从选题到格式调优的全流程痛点。

## 运行指南

python 版本推荐：3.11

### 1. 安装环境依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量，目前是API

> 目前可以先用我的API，deepseek的还比较便宜

```bash
cp .env.example .env
```

如果不使用我的也需要创建一个.env文件，可以参考.env.example进行创建

### 3. 运行主程序

目前只有一种形式，也没有任何可以自主可选的内容，先验证框架可运行即可：

```bash
python main.py
```

## 项目架构

> 初步的构想，随改随确定

```
Tex_Agent/
│
├── doc/                        # 保存文档（需求分析、API文档、会议记录）
│
├── .env.example                # 环境变量示例文件
│
├── .gitignore                  # Git 忽略文件
│
├── requirements.txt            # 项目依赖包列表
│
├── config/                     # 全局配置中心
│   ├── settings.py             # 读取环境变量、配置全局参数
│   └── prompts.py              # 统一存放各个 Agent 的 Prompt 模板
│
├── tools/                      # 工具函数集（各 Agent 共享）
│   ├── __init__.py
│   ├── arxiv_search.py         # 文献检索与解析 API
│   ├── latex_parser.py         # LaTeX 语法检查
│   └── data_analyzer.py        # 统计分析
│       ... 
│
├── memory/                     # 记忆化存储模块
│   ├── __init__.py
│   ├── context_manager.py      # 处理短期上下文逻辑
│   ├── literature_db/          # 本地存放文献记忆的目录（比如引入轻量级数据库）
│   └── session_logs/           # 存放用户对话历史的 JSON 文件目录 （按时间戳或任务 ID 保存）
│
├── agents/                     # 核心 Agent 架构目录 (四人并行开发)
│   ├── __init__.py
│   ├── base_agent.py           # 定义 Agent 基类，规范输入输出接口
│   ├── simple_agent/           # 组员A 
│   │   ├── __init__.py
│   │   └── core.py
│   ├── react_agent/            # 乔雨霖
│   │   ├── __init__.py
│   │   └── core.py
│   ├── reflection_agent/       # 毛炜翔 
│   │   ├── __init__.py
│   │   └── core.py
│   └── plan_solve_agent/       # 唐骏涛
│       ├── __init__.py
│       └── core.py
│
├── workspace/                  # 临时沙箱工作区
│   └── temp_latex_files/       # Agent 处理复杂 LaTeX 时的临时暂存或备份区
│
├── router.y                    # 四种框架的路由
│
└── main.py                     # 主程序入口
```


## 一种可能的项目架构（混合框架langraph+autoGen，支持多agent，同时有多种范式实现）
'''
paper_writer_agent/
├── .env
├── requirements.txt
├── main.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── state/
│   ├── __init__.py
│   └── schema.py             # 状态定义（包含上下文引用）
├── context/                  # 【新增】上下文管理核心模块
│   ├── __init__.py
│   ├── manager.py            # 上下文管理器（统一入口）
│   ├── storage.py            # 上下文存储（向量库 + 关系图）
│   ├── retriever.py          # 上下文检索（语义 + 规则）
│   ├── compressor.py         # 上下文压缩（摘要 + 摘要树）
│   └── policies.py           # 上下文策略（不同场景的上下文选择规则）
├── tools/
│   ├── __init__.py
│   ├── search.py
│   └── citation.py
├── strategies/
│   ├── __init__.py
│   ├── base.py
│   ├── react_strategy.py
│   ├── plan_solve_strategy.py
│   └── reflection_strategy.py
├── multi_agent/
│   ├── __init__.py
│   └── review_team.py
├── graph/
│   ├── __init__.py
│   ├── nodes.py              # 调用 Context Manager 注入上下文
│   ├── router.py
│   └── workflow.py
├── utils/
│   ├── __init__.py
│   └── logger.py
└── tests/
    └── test_context.py
'''