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
```

**启动服务：**

```bash
# 方式 A：模块入口（常用）
python -m ui.web.server

python -m ui.overleaf.server 然后打开http://127.0.0.1:8772/
```

默认监听 **`http://127.0.0.1:8765/`**（可用环境变量 `TEX_AGENT_WEB_HOST`、`TEX_AGENT_WEB_PORT` 修改）。

**页面能力概览：**

| 区域 | 说明 |
|------|------|
| 左侧 | **工作流编排**：节点与有向边，保存到服务端；顶栏选「自定义（左侧编排）」且 `workflow=__web__` 时走该图。保存时有 DAG 校验（唯一入口/唯一汇、无环、无孤立等）。 |
| 中部上 | **分支树**：调用 `GET/POST /api/branches` 等，图上可切换分支、从父节点新建子分支。 |
| 中部 | **PDF 资料**：上传到项目内 **`storage/pdfs/`**（已加入 `.gitignore`，不提交用户文件），列表与下载走 `GET/POST /api/storage/pdfs`。 |
| 底部 | 对话；`task` 时可在顶栏选择注册表工作流或「自定义」。 |

**相关 REST API（便于联调）：**  
`GET/POST /api/branches`、`POST /api/branches/switch`、`GET/PUT /api/workflow/draft`、`GET /api/workflow/registry`、`GET/POST /api/storage/pdfs`、`GET /api/storage/pdfs/{文件名}/raw`。

**启动后打开浏览器：** 默认尝试**系统默认浏览器**（WSL 常见为调 Windows 侧打开，见 `ui/web/browser_open.py`）。可设置 `TEX_AGENT_NO_OPEN_BROWSER=1` 不自动打开；`TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER=1` 在打开系统浏览器后**再**尝试 Simple Browser。详见 `ui/web/ide_launch.py` 与 `scripts/start_texagent_web.py` 文头说明。

## 论文审查功能的使用说明

### 不同方式实现论文审查

#### 直接上传PDF + 多模态大模型理解

对应工作流含“multi”字段，包括：
+ `checklist_multi_v1`：6个审查节点并行工作，略快但可能由于API的原因不够稳定
+ `checklist_multi_v2`：6个审查节点串行工作，更稳定
+ `checklist_multi_v3`：仅包括一个审查LMM节点，更快但效果可能退步
+ `checklist_multi_v4`：效果同v1，但**支持用户自然语言交互**

#### 本地进行pdf解析 + 上传纯文本内容给LLM

对应工作流含“text”字段，包括：
+ `checklist_text_v1`：旧版工作流，没有包括对参考文献的审查
+ `checklist_text_v2`：包括对**所有正文部分**的审查（摘要、绪论、背景与相关工作、方法、实验、参考文献 共 6 部分，**不包括图片、图表、表格等**）；支持自然语言输入路径
+ `checklist_text_v3`：审查逻辑与 v2 相同；`preflight_inputs` 关闭 LLM，适合 `check_text.py` 批量脚本（结构化 JSON 路径输入）

v1 / v2 支持自然语言交互（含待审 PDF、checklist 路径，可选输出路径）。v3 推荐批处理时使用 `check_text.py` 或自行传入上述 JSON。工作时六路并行分别审查各章节文本，结束后提供批注 PDF 下载。

### 如何运行

```bash
# 1. 克隆项目
git clone https://github.com/BCyyyyyyTZ/Tex_Agent.git
cd TeX_Agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env

# 4. 运行web-ui
python -m ui.web.server

# 5. 选择带multi或text的工作流，对工作流的描述见上

# 6. 如果选用multi_v1~v3工作流，需要构造输入，直接输在对话框中，例如：
"pdf_path": "./storage/pdfs/paper1.pdf",
"checklist_path": "./storage/checklists/thesis-checklists.md",
"output_path": "./storage/documents/paper1-checked.pdf"
# 路径可以使用绝对路径或相对Tex_Agent的相对路径
# 可以不用手动上传文件，直接在输入注入文件路径即可

# 如果其他工作流，就可以不用标准格式的输入，可以支持自然语言输入

# 7. 如果正常就可以看到输出了（请耐心等待），输出的文档点击链接下载，也会同时保存在"output_path"路径下
```

### 一些说明

1. Gemini API可能连接不够稳定，并发执行大概率会有的连接失败，串行执行也有小概率失败某一个节点 —— 一个节点失败理论上有的时候不影响正常输出标注pdf，但会在UI显示有错误（有些情况下一些节点请求API失败，但Agent会根据请求成功的API输出进行工作，仍然在"output_path"下保存结果）
2. 目前支持的工作流是`checklist_multi_v1`、`checklist_multi_v2`、`checklist_multi_v3`、`checklist_multi_v4`（支持论文审查），其他一些工作流属于是项目开发过程中调试用的，可能不能运行或有一些问题，尽量不要使用
3. 目前项目可以更方便地自定义工作流，可以参考 `checklist_multi_v1` 设计节点和边的关系，将 JSON 保存在 `config/workflow/` 下，并在 `config/workflow_registry.json` 中注册（关于自定义工作流的详细说明之后可以补充）
4. `checklist_multi_v4`支持用户自然语言输入，需要包括文件路径信息和checkinglist路径信息

## 命令行批量审查：`check.py`（checklist_multi v1 / v2 / v3）

用于不经过 Web UI、按配置文件顺序跑多份 PDF 的 checklist 审查。

1. **论文文件组织结构**
   - `files/input/`：待审PDF原件（还在这里面的就是没审查的，审查完的会移动到checked下面）
   - `files/checklist/`：checklist 文件
   - `files/output/`：批注后的 PDF（脚本自动生成，无需在配置里写路径，同一个论文多次批注的结果会在后面标版本的）
   - `files/checked/`：已审PDF原件


2. **配置文件**：仓库中config/run_config.json
   - `version`：`"v1"`、`"v2"` 或 `"v3"`（对应三套并行/串行/单节点审查策略）
   - `checklist_path`：绝对路径 or 相对于 `files/checklist/` 的相对路径
   - `pdf_path`（单个）或 `pdf_paths`（列表）：绝对路径 or 相对于 `files/input/` 的相对路径  
   - 不用写输出路径

3. **运行**：

   ```bash
   python check.py
   ```

4. **行为说明**
   - 启动前会探测 **Gemini** 与 **OpenAI 兼容 API**；**连不上模型则直接退出**，不跑任何 PDF。
   - 某个 **PDF 或 checklist 路径不存在**：**跳过该条**（若共享的 checklist 不存在则整批跳过）。
   - 某一 PDF **执行失败（非连接类错误）**：打印错误并**继续**下一个。
   - 运行中出现 **连接类错误**：**立即停止**，不再处理后续文件。
   - **成功**：在 `files/output/` 生成批注 PDF，并把**原稿**归档到 `files/checked/`；**失败**：原文件仍留在原位置（例如仍在 `files/input/`）。

5. **退出码**：`0` 表示本批全部成功；`1` 表示存在失败项、配置错误或没有任何可处理文件；`2` 表示模型连通性检查失败或运行中出现连接类错误并已中止。

## 命令行批量审查：`check_text.py`（checklist_text_v3）

用于不经过 Web UI、按**结构化路径**批量跑 **文本审查**工作流（`checklist_text_v3`，与 v2 审查逻辑一致；首节点 `preflight_inputs` 不调用 LLM，适合批处理）。

1. **配置文件**（可选）：将 `config/run_config_text.example.json` 复制为 `config/run_config_text.json`，字段说明：
   - `workflow`：默认 `checklist_text_v3`
   - `checklist_path`：审查清单（绝对路径或相对项目根）
   - `output_dir`：输出目录；每篇生成 `{PDF 原名}-checked.pdf`（重名时自动加 `_1` 后缀）
   - `pdf_paths`：待审 PDF 列表（绝对路径或相对项目根）

2. **运行**：

   ```bash
   # 使用配置文件
   python check_text.py

   # 或命令行直接指定
   python check_text.py --checklist thesis-checklists.md --output-dir files/output_text --pdfs doc/a.pdf doc/b.pdf
   ```

3. **行为说明**
   - 每篇论文向工作流传入 JSON：`{"pdf_path":"...","checklist_path":"...","output_path":"..."}`。
   - 某一 PDF 失败（非连接类错误）：打印错误并继续下一篇；连接类错误则立即停止。

4. **退出码**：与 `check.py` 相同（`0` / `1` / `2`）。


## 解析文章（pdf -> md + json）

### pypdf+pdfminer

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env

# 3. 直接运行web-ui   
python -m ui.web.server

# 4. 选择工作流：thesis_chapter_extract

# 5. 支持自然语言输入，给定待解析文件的路径和需要解析的章节（或章节名、摘要、全文等字样）
```


### 命令行直接调用工具（docling）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env

# 3. 直接运行document_parse
#    必填的参数是待解析的pdf路径
#    可选参数：-o 保存结果的路径；不填会默认保存在Tex_Agent/storage/documents路径下   
python -m rag.document_parse "D:\papers\my.pdf" -o "D:\output\my_parse_folder"
```

---

## LaTeX 论文辅助写作功能的说明

TeX_Agent 提供了一套 LaTeX 论文辅助写作子系统，覆盖**项目扫描**、**静态检查（ChkTeX）**、**编译检查（latexmk）**、**LLM 纠错建议**与**主动润色**。

| 通道 | 入口 | 适用场景 |
|------|------|----------|
| **Ghost 幽灵窗口（推荐）** | `python -m latex.ghost_cli` | 边看源码边改、行间纠错卡、应用/对比/忽略、项目文件树 |
| 一次性诊断 | `python main.py task --wf latex_diagnose_v0/v1` | CI、全库体检、无 UI |
| 终端监视 | `python -m latex.watch_cli` | 纯终端输出、旧版 watch 行为 |

---

### 1. 独立幽灵窗口 Ghost UI

Ghost UI 在**独立浏览器页**中展示 LaTeX 源码与**行间浮动建议卡**，不依赖 VS Code 扩展。

#### 快速启动

```bash
# 在项目根目录执行（需已配置 .env 中的 LLM API Key，纠错建议才可用）
python -m latex.ghost_cli --root latex文件夹 --main-tex 主tex文件.tex
```

启动后会尝试打开浏览器，默认地址：

**http://127.0.0.1:8771/**

`--root` 为 LaTeX 项目根目录；`--main-tex` 为编译入口主文件（相对 `root` 的正斜杠路径，如 `paper.tex`）。系统会扫描 `main_tex` 的 `\input` 闭包内全部子 `.tex`，子文件上的报错也会出现在对应文件的 Ghost 视图中。

#### 常用命令行参数

```bash
python -m latex.ghost_cli \
  --root 文件夹 \
  --main-tex paper.tex \
  --quiet-sec 1.0 \     # 静默时间（s），当文件修改后静默多少秒再触发静态检查
  --no-browser          # 可选：不自动打开浏览器，手动访问 http://127.0.0.1:8771/
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--root` | （必填） | LaTeX 项目根目录，支持绝对路径或相对项目根 |
| `--main-tex` | 无 | 主 tex，用于 latexmk 编译入口；建议始终指定 |
| `--quiet-sec` | `1.0` | 文件修改后静默多少秒再触发**静态检查** |
| `--disable-latexmk` | 关闭 | 默认**开启** latexmk；加上此参数则不做编译检查 |
| `--enable-auto-polish` | 关闭 | 启用后会在停笔约 2s 自动润色（Ghost 默认**关闭**自动润色，请用页面内「主动润色」） |
| `--idle-polish-sec` | `2.0` | 仅在与 `--enable-auto-polish` 联用时生效 |
| `--host` / `--port` | `127.0.0.1` / `8771` | 监听地址与端口 |
| `--no-browser` | 关闭 | 不自动打开系统浏览器 |

#### 页面功能说明

| 功能 | 说明 |
|------|------|
| **项目文件树** | 顶栏下拉按 `\input` / `\bibliography` 关系树状展示；可选 `.tex`、`.bib`；节点旁圆点表示该文件有待处理纠错卡或润色卡 |
| **源码区** | 当前选中文件的行号与内容；纠错范围红色高亮，润色范围绿色高亮 |
| **纠错幽灵卡** | 展示报错信息、定位、原因分析、改正方案；支持**应用**（直接替换）、**对比**（原文注释 + 新文插入）、**忽略** |
| **主动润色** | 底栏「主动润色」：输入需求 + 选择目标文件，由 LLM 生成润色卡（绿色） |
| **编译检查** | 顶栏按钮「编译检查」：手动触发整项目 latexmk |

#### 诊断与刷新策略（Ghost 专用）

与通用 `watch_cli` 不同，Ghost 采用 **GhostWatchPolicy**：

1. **静态检查（ChkTeX）**
   - 仅在您对监视目录内 `.tex` / `.bib` **有修改**，且**静默 `--quiet-sec` 秒（默认 1s）无新修改**后触发。
   - 扫描范围为 `main_tex` 可达闭包内的全部子 tex（不是只扫主文件）。
   - 用户一直不编辑时，**不会**反复空跑静态检查。

2. **编译检查（latexmk）**
   - **启动时自动执行一次**（以 `main_tex` 为入口编译整个项目，生成/更新 `paper.log` 等；**不是**对每个子 tex 单独编译）。
   - 之后仅在您点击 **「编译检查」** 时再次编译。
   - 编译在后台进行；顶部状态条会显示进度，结束后变为「编译检查完成」（可能编译检查完成后还要稍后一会才能看见结果，这是由于检查之后报错会经过处理生成改正建议）。

3. **纠错建议（LLM）**
   - 仅针对 **error** 级问题生成卡片；warning 不进 LLM 纠错链。
   - 若同一轮 error 集合未变，不重复调用 LLM，避免卡片抖动。
   - 点击「忽略」会持久化：同一文件、同一行、同一报错再次出现时默认不再出卡、不再送 LLM。

4. **行号确认**
   - 合并诊断后、出卡前会在报错行附近 **±5 行** 内根据报错锚点校准行号，缓解子文件 log 行号偏移。

5. **前端刷新**
   - 轮询 snapshot 时，仅当诊断结果版本或编译状态变化才重绘卡片，减少长卡片阅读时滚动条被重置。

#### 应用 / 对比 使用注意

- **应用**：按建议的 `range` 直接替换磁盘上的对应片段。
- **对比**：将 `range` 内原文改为 `% [TeX_Agent][compare] ...` 注释，并在其下插入建议正文，便于对照后决定是否再点「应用」。
- 空范围或重复点击「对比」已做幂等处理，避免产生 `% [TeX_Agent][compare] (empty)` 等污染行。

静态资源目录：`ui/ghost/`（`ghost.js`、`ghost.css`）。


### 2. 一次性全库诊断（CLI）

若只需对项目做一次全面体检、不需要浏览器 UI，可使用 `main.py task`：

- **基础诊断（无 LLM）**：ChkTeX + latexmk，速度快。
  ```bash
  python main.py task --wf latex_diagnose_v0 "{\"root\":\"您的项目路径\",\"main_tex\":\"paper.tex\"}"
  ```
- **智能诊断（带 LLM 修复建议）**：在 error 上调用大模型生成修改建议。
  ```bash
  python main.py task --wf latex_diagnose_v1 "{\"root\":\"您的项目路径\",\"main_tex\":\"paper.tex\"}"
  ```


### 3. 实时监视（终端 Watch 模式）

```bash
python -m latex.watch_cli start --root 您的项目路径 --main_tex main.tex
```

终端内输出诊断与润色摘要；默认防抖约 500ms、空闲约 2s 自动润色。改稿交互请优先使用上一节的 **Ghost UI**。

### 4. 环境与依赖说明

| 项 | 说明 |
|----|------|
| **路径** | `root` 支持 Windows / Linux 路径；API 与 JSON 内相对路径统一为正斜杠 |
| **TeX 工具链** | 建议安装 `chktex`、`latexmk`（及 TeX 发行版）。未安装时静态/编译能力会降级 |
| **LLM** | 纠错卡与主动润色需配置 `.env` 中 `OPENAI_API_KEY`（或项目使用的兼容 API） |
| **编译轮次** | 语法纠错通常**一次** latexmk + log 解析即可发现致命错误；完整引用/bib 收敛可能需 latexmk 多轮，Ghost 默认 `fast` 模式，侧重快速报错而非最终 PDF 质量 |



## 项目目录树结构与文件说明

```
TeX_Agent/
├── main.py                      # 程序主入口，支持 task / task --wf / plan
├── requirements.txt             # 项目依赖（含 FastAPI、uvicorn、python-multipart 等）
├── .env.example                 # 环境变量示例（OPENAI_API_KEY 等，复制为 .env 使用）
├── README.md                    # 本文件
├── check.py                     # 无 UI：按 config/run_config.json 批量跑 checklist_multi
├── files/                       # check.py 推荐目录：input / checklist / output / checked（见文首说明）
├── storage/pdfs/                # Web 上传的 PDF 存放目录（用户文件默认被 .gitignore 忽略）
├── ui/web/                      # FastAPI Web UI（默认 :8765）：server.py、静态页、pdf_storage 等
│   └── static/                  # index.html、app.js、分支/工作流/PDF 相关 JS 与样式
├── ui/ghost/                    # Ghost 幽灵窗口前端（默认 :8771）：index.html、ghost.js、ghost.css
├── latex/                       # LaTeX 辅助写作：监视、诊断、Ghost 服务与项目树
│   ├── ghost_cli.py             # 启动 Ghost：`python -m latex.ghost_cli --root ... --main-tex ...`
│   ├── ghost_server.py          # Ghost HTTP 服务与 /api/* 路由
│   ├── ghost_watch_policy.py    # Ghost 专用触发策略（静态防抖、启动一次编译、手动再编译）
│   ├── watch_cli.py             # 终端监视模式
│   ├── watch_service.py         # 诊断聚合、ChkTeX / latexmk、snapshot
│   ├── project_tree.py          # 项目文件树（\input / bib）
│   └── apply_compare.py         # 应用 / 对比写回磁盘
├── Framework.md                 # 框架拓展路线图
│
├── doc/                         # 相关说明文件
├── change_logs/                 # 变更记录（各成员子目录）
│
├── config/                      # 统一配置层（开发者只需关注此目录即可完成大部分配置）
│   ├── settings.py              # 全局配置：LLM 模型、API Key、RAG 分块参数、超时、重试
│   ├── agent_config.py          # 各 Agent 的 system prompt、temperature 等行为参数
│   ├── run_config.json          # check.py 运行配置（纳入版本库）
│   ├── run_config.example.json  # 配置模板备份/参考
│   ├── workflow_registry.json   # 工作流注册表（name -> config/workflow/*.json）
│   ├── workflow/                # 各工作流 JSON（如 workflow_default_dynamic.json、workflow_checklist_multi_v*.json）
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