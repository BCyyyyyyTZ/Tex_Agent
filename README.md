<div align="center">

# 🧪 TeX_Agent

**基于多智能体架构的 LaTeX 论文写作增强系统**

[![Stars](https://img.shields.io/github/stars/BCyyyyyyTZ/Tex_Agent?style=flat&logo=github)](https://github.com/BCyyyyyyTZ/Tex_Agent)
[![Views](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FBCyyyyyyTZ%2FTex_Agent&count_bg=%2344CC11&title_bg=%23555555&title=views&edge_flat=true)](https://github.com/BCyyyyyyTZ/Tex_Agent)

</div>

---

## 🚀 快速启动

环境准备好后，**双击 `start_all.bat`** 即可一键启动两个服务：

| 服务 | 地址 | 说明 |
|------|------|------|
| 💬 Chat Mode | `http://127.0.0.1:8765/` | Web UI，工作流编排、论文审查 |
| ✍️ Writing Mode | `http://127.0.0.1:8772/` | Overleaf 风格在线 LaTeX 编辑器 |

> 如果需要手动启动，也可以逐个运行：
> ```bash
> python -m ui.web.server       # Chat Mode
> python -m ui.overleaf.server  # Writing Mode
> ```

---

## 📦 环境安装

```bash
# 1. 克隆项目
git clone https://github.com/BCyyyyyyTZ/Tex_Agent.git
cd Tex_Agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 OpenAI / Gemini API Key 等
```

---

## 🔧 其他功能

### LaTeX 写作辅助（Ghost UI）

独立的 LaTeX 源码编辑辅助窗口，支持静态检查（ChkTeX）、编译检查（latexmk）、**LLM 纠错与润色**：

```bash
python -m latex.ghost_cli --root <项目目录> --main-tex <主文件.tex>
```

默认地址 `http://127.0.0.1:8771/`

### 命令行批量审查

对 PDF 论文进行批量 checklist 审查：

```bash
python check.py                                    # 多模态审查
python check_text.py --checklist <清单> --pdfs <PDF列表>  # 文本审查
```

### 文档解析（PDF → Markdown + JSON）

```bash
python -m rag.document_parse <PDF路径> -o <输出目录>
```

---

## 📁 项目结构

```
TeX_Agent/
├── ui/            # Web 前端（Chat + Overleaf + Ghost）
├── core/          # 核心数据结构与协议
├── agents/        # 智能体模块（SimpleAgent + 扩展占位）
├── workflow/      # LangGraph 工作流编排
├── rag/           # 检索增强生成
├── tools/         # 工具模块（arXiv 检索等）
├── latex/         # LaTeX 辅助写作
├── config/        # 统一配置层
└── tests/         # 测试模块
```

详细信息请参阅 [Framework.md](./Framework.md)。

---

## 🧱 技术栈

| 层次 | 选型 |
|------|------|
| 工作流编排 | LangGraph |
| LLM 调用 | LangChain + OpenAI / Gemini / DeepSeek |
| Web 框架 | FastAPI + Uvicorn |
| 向量数据库 | ChromaDB（本地嵌入） |
| 异步并发 | asyncio |
| 测试 | pytest + pytest-asyncio |

---

<div align="center">

Made with ❤️ by [BCyyyyyyTZ](https://github.com/BCyyyyyyTZ)

</div>