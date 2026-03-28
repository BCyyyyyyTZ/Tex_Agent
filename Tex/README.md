# NeuroTeX — 神经网络启发的多智能体论文写作协作系统

## 项目简介

**NeuroTeX** 是一个基于神经科学隐喻设计的多智能体论文写作协作系统，采用"大脑皮层-小脑-海马体-基底节"四层神经网络架构类比构建 Multi-Agent System，专为学术论文（LaTeX）写作场景设计。

本系统创新性地将多智能体协作架构比喻为人脑的神经网络运作方式：
- **前额叶皮层（Orchestrator Layer）**：负责高层次规划与决策
- **小脑（Executor Pool）**：专业化智能体执行具体任务
- **海马体（Memory System）**：实现短期工作记忆与长期知识存储
- **基底节（Router）**：动态路由与习惯化任务分发
- **感觉皮层（Input Processing）**：处理用户输入与 LaTeX 文档解析
- **运动皮层（Output Assembly）**：汇聚结果并生成最终输出

---

## 系统架构总览

```
NeuroTeX Multi-Agent System
│
├── [前额叶皮层] Orchestrator Layer
│   ├── PlannerAgent          — 任务分解与全局规划
│   ├── ExecutorCoordinator   — 多 Agent 并发协调
│   └── ResultAggregator      — 结果聚合与验证
│
├── [基底节] Router Layer
│   ├── TaskClassifier        — 任务意图识别与分类
│   ├── ComplexityEstimator   — 任务复杂度估算
│   ├── ModelSelector         — 最优模型/Agent 选择
│   └── AdaptiveRouter        — 自适应路由策略
│
├── [小脑] Agent Executor Pool
│   ├── Base Agents (4种基础架构)
│   │   ├── SimpleAgent
│   │   ├── ReActAgent
│   │   ├── ReflectionAgent
│   │   └── PlanAndSolveAgent
│   ├── Specialized Agents
│   │   ├── LiteratureAgent   — 文献检索与趋势分析
│   │   ├── AnalysisAgent     — 统计分析
│   │   ├── LaTeXAgent        — LaTeX 处理与优化
│   │   ├── VisualizationAgent— 数据可视化
│   │   ├── WritingAgent      — 论文写作辅助
│   │   ├── ImageGenAgent     — 图像生成
│   │   └── CompanionAgent    — 情感陪伴
│   └── Meta Agents
│       ├── RouterAgent       — 路由决策智能体
│       ├── EvaluatorAgent    — 结果评估智能体
│       └── MonitorAgent      — 系统监控智能体
│
├── [海马体] Memory System
│   ├── ShortTermMemory       — 工作记忆（对话上下文）
│   ├── BranchMemory          — 多分支上下文（类 git）
│   ├── LongTermMemory        — 向量知识库
│   └── EpisodicMemory        — 情节记忆（会话历史）
│
├── [感觉皮层] RAG & Knowledge
│   ├── PaperKnowledgeBase    — 论文检索库
│   ├── ExpertKnowledgeBase   — 专家经验库
│   └── UserKnowledgeBase     — 用户自定义资源库
│
└── [运动皮层] Output Layer
    ├── API Server            — RESTful / WebSocket 接口
    ├── CLI Interface         — 命令行交互
    ├── Web UI                — 轻量级 Web 界面
    └── LaTeX Plugin          — LaTeX 编辑器插件
```

---

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 多智能体框架 | AutoGen + LangGraph |
| LLM 接入 | OpenAI API / Anthropic Claude / 本地模型(Ollama) |
| 向量数据库 | ChromaDB / FAISS / Weaviate |
| 嵌入模型 | OpenAI text-embedding / sentence-transformers |
| 文献检索 | arXiv API / Semantic Scholar API / Google Scholar |
| LaTeX 解析 | pylatexenc / latexwalker |
| 数据分析 | pandas / scipy / scikit-learn |
| 可视化 | matplotlib / seaborn / plotly |
| 图像生成 | DALL-E API / Stable Diffusion |
| API 框架 | FastAPI |
| Web UI | Gradio / Streamlit (轻量级) |
| 任务队列 | Celery + Redis |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 配置管理 | pydantic-settings |
| 日志 | loguru |

---

## 快速开始

### 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd NeuroTeX

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys
```

### 运行系统

```bash
# 初始化知识库
python scripts/setup_kb.py

# 命令行模式
python -m ui.cli.main_cli

# API 服务模式
python -m api.main

# Web UI 模式
python -m ui.web.app
```

---

## 项目结构

```
tex_agent/
├── agents/          — 所有智能体实现
│   ├── base/        — 四种基础 Agent 架构
│   ├── specialized/ — 专业化功能 Agent
│   ├── orchestrator/— 编排层 Agent
│   └── meta/        — 元智能体（路由/评估/监控）
├── api/             — RESTful API 服务
├── companion/       — 情感陪伴模块
├── config/          — 系统配置（模型、提示词、日志等）
├── context/         — 多分支上下文管理
├── core/            — 核心基础设施（消息总线、状态机、注册表）
├── mas/             — 多智能体系统核心逻辑
├── memory/          — 记忆系统（短期/长期/情节/分支）
├── monitoring/      — 系统监控与性能追踪
├── plugins/         — 编辑器插件
├── prompts/         — 存储各模块所需的提示词
├── rag/             — 检索增强生成模块
├── router/          — 智能路由模块
├── scripts/         — 初始化与维护脚本
├── security/        — 安全与权限模块
├── skills/          — 可复用技能库
├── tests/           — 测试套件
├── tools/           — 工具集（LaTeX/搜索/分析/可视化/图像）
├── ui/              — 用户界面（CLI + Web）
├── .env.example   
├── .gitignore
└── requirements.txt
```

---

## 开发阶段规划

- **Phase 1**：四种基础 Agent 原型 + 基础工具链
- **Phase 2**：MAS 集成 + Router + RAG + 多分支上下文
- **Phase 3**：系统优化 + UI 开发 + 技能库扩展
- **Phase 4**：产品化 + LaTeX 插件 + 安全加固

---

## 贡献者

| 成员 | 负责框架 |
|------|---------|
| 于天泽 | SimpleAgent |
| 乔雨霖 | ReActAgent |
| 毛炜翔 | ReflectionAgent |
| 唐骏涛 | PlanAndSolveAgent |

---

## 许可证

MIT License
