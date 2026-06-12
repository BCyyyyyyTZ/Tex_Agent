# TeX\_Agent 测试计划

## 1. 目的

本测试计划面向当前项目，建立一套可执行、可扩展的测试体系：

- 覆盖项目大部分功能模块，兼顾单元测试与集成测试，并补充系统/端到端烟测。
- 通过新增测试代码与测试夹具实现可运行的验证。
- 统一新增测试代码目录，便于后续持续补齐用例与自动化执行。

## 2. 测试范围

### 2.1 在范围内

按模块覆盖：

- **工作流/编排**：workflow/、workflow\_engine/、router/、config/workflow/\*.json
- **智能体**：agents/、memory/、context/、core/
- **工具系统**：tools/、utils/
- **LaTeX 子系统**：latex/（解析、索引、切片、诊断、watch 服务、ghost server）
- **RAG 子系统**：rag/（loader、parse、pipeline、vector store）
- **Web UI 服务**：ui/web/（FastAPI、静态资源服务、文件存储、会议日历）
- **Overleaf 风格服务**：ui/overleaf/
- **安全与中间件**：security/
- **CLI/脚本入口**：main.py、check.py、check\_text.py、scripts/

### 2.2 不在范围内

- LLM 真实调用质量评估（需要外部 Key、费用与不稳定因素）。只做接口与退化路径测试。
- 大规模性能基准（可作为后续性能测试专项）。

## 3. 测试分层与总体策略

采用“金字塔 + 风险驱动”的策略：

1. **单元测试**：优先覆盖纯函数、解析器、序列化、规则校验、错误处理分支（快速、稳定）。
2. **集成测试**：覆盖关键对接点：文件系统、FastAPI 路由、Chroma/RAG、LaTeX 工具链（可用 marker 控制）。
3. **系统/端到端烟测**：覆盖主入口链路与最关键用户路径（少量、稳定、可重复）。

### 3.1 质量目标

- **功能覆盖**：关键模块（LaTeX/RAG/Workflow/Web）均有单元测试与至少 1 条集成路径。
- **回归能力**：对常见失败模式（无网络、无 TeX 命令、空文档/坏文档、取消执行、异常输入）有明确回归用例。
- **可维护性**：测试夹具集中管理；测试命名与分层一致；失败定位信息明确。

## 4. 测试方法与设计技术

### 4.1 黑盒测试

- **等价类划分**：输入文本（空/短/长/含特殊字符）、文件类型（pdf/docx/md/tex/unknown）、路径（相对/绝对/不存在）。
- **边界值分析**：最大/最小 chunk、行长度、超长文件名、极小 PDF、0 字节文件。
- **判定表/决策表**：工作流条件分支、工具参数组合（例如 rag-db-mode、latex 诊断开关）。
- **状态迁移**：watch service（启动→监视→事件→快照→停止）、运行取消（未取消→取消→清理）。
- **错误推测**：坏编码、权限不足、依赖命令不存在、网络超时、JSON 配置缺字段。

### 4.2 白盒测试

- **分支覆盖**：异常处理、退化路径、错误码映射、边界分支（尤其是日志解析与路径处理）。
- **契约测试**：核心数据结构（core/message、workflow state/metadata）字段完整性、兼容性。

### 4.3 组合测试与风险驱动

优先级遵循：

- P0：影响主流程且容易回归（工作流引擎、LaTeX 诊断/解析、RAG 管线、Web API 核心）。
- P1：工具集与辅助功能（图表/markdown/文件导入）。
- P2：可选增强与外部依赖强（LLM/网络/特定系统工具）。

## 5. 测试资产组织

仓库当前已有 `tests/`。为满足“统一新建目录”的要求，本计划新增测试代码统一放在：

- `qa_tests/`

### 5.1 目录结构

```
qa_tests/
  unit/
    test_*.py
  integration/
    test_*.py
  e2e/
    test_*.py
  fixtures/
    latex/
    rag/
    web/
  conftest.py
```

### 5.2 命名与约定

- 文件：`test_<模块或场景>_<类型可选>.py`
- 用例：`test_<行为>__<条件>__<期望>()`（双下划线分段，便于阅读与检索）
- marker（与现有 pytest.ini 对齐）：
  - `@pytest.mark.integration`：需要 chromadb/embedding 或明显外部依赖的集成测试
  - `@pytest.mark.latex_integration`：需要本机 TeX 工具链（latexmk/chktex/pdflatex 等）
  - `@pytest.mark.slow`：端到端或耗时较长

## 6. 测试环境与依赖

### 6.1 基础环境

- OS：Windows
- Python：以项目运行所用版本为准
- 依赖：按 `requirements.txt` 安装（含 pytest、pytest-asyncio、fastapi、chromadb 等）

### 6.2 外部系统依赖

- **LaTeX 工具链**：TeX Live 或 MiKTeX；命令建议在 PATH 中可执行：`latexmk`、`chktex`、`pdflatex`
- **RAG embedding 模型下载**：Chroma DefaultEmbeddingFunction 首次需要联网下载模型；离线环境下需缓存或跳过相关用例

### 6.3 环境隔离与可重复性

- 文件系统：统一使用临时目录（pytest `tmp_path`）写入中间产物，避免污染仓库。
- 网络：对需要联网的工具/流程，优先 mock；必要时标记为 `integration` 并允许在 CI 里按需跳过。

## 7. 测试数据与夹具策略

### 7.1 夹具原则

- 小而确定：尽量使用小文本、小 latex 工程、小 PDF（或 mock）以减少不稳定因素。
- 明确期望：每个夹具提供对应的期望输出，例如解析结果 JSON、诊断问题列表。
- 可复用：跨模块共享的夹具放在 `qa_tests/fixtures/`，每个领域子目录内独立维护。

### 7.2 建议新增夹具集合

- `latex/min_project/`：最小可编译工程（含引用、bib、图片占位）
- `latex/broken_cases/`：缺括号、缺 \end、未定义引用、编码问题
- `rag/docs/`：tex/md/txt 小样本 + 空文件 + 超长行文本
- `web/`：上传/下载/静态资源的最小样本文件

## 8. 测试项分解与用例目录

下表给出“测试项 → 用例建议 → 分层 → 期望”的设计，用于指导后续写测试代码。

### 8.1 Workflow / Workflow Engine

| 编号    | 测试项         | 重点用例                        | 分层          | 预期                           |
| ----- | ----------- | --------------------------- | ----------- | ---------------------------- |
| WF-01 | 工作流解析与注册    | JSON 缺字段/多余字段/非法 node\_type | Unit        | 抛出可读异常；错误信息包含字段名             |
| WF-02 | DAG 校验与拓扑顺序 | 有环/多入口/多出口/孤立节点             | Unit        | 拒绝保存/构建；返回明确原因               |
| WF-03 | 条件分支评估      | 条件表达式 True/False/异常         | Unit        | 分支选择符合判定表；异常时有退化策略           |
| WF-04 | 并行合并        | fan-in barrier 合并顺序与一致性     | Unit        | 合并结果稳定、可复现                   |
| WF-05 | 端到端最小工作流    | 2 节点 agent 串联（mock 输出）      | Integration | state/output/metadata 字段契约正确 |

### 8.2 Agents / Memory / Context / Core

| 编号    | 测试项            | 重点用例                            | 分层               | 预期                       |
| ----- | -------------- | ------------------------------- | ---------------- | ------------------------ |
| AG-01 | BaseAgent 输出契约 | 消息 role/content、结构化输出           | Unit             | 对齐 message/state 合约      |
| AG-02 | 取消执行           | 触发取消标志后及时退出                     | Unit/Integration | 不继续执行后续节点；清理 run\_cancel |
| AG-03 | Context Policy | 不同 policy 下的裁剪/保留               | Unit             | 行为符合规则；边界输入不崩溃           |
| AG-04 | Memory 工厂      | persona/branch/simple memory 构造 | Unit             | 默认值与序列化稳定                |

### 8.3 LaTeX 子系统（解析/索引/诊断/修复/Watch/Ghost）

| 编号    | 测试项                      | 重点用例                                 | 分层                 | 预期               |
| ----- | ------------------------ | ------------------------------------ | ------------------ | ---------------- |
| TX-01 | 项目索引                     | 多文件、include、跨目录路径                    | Unit               | 索引完整；相对/绝对路径处理一致 |
| TX-02 | slice/结构抽取               | 章节切片、环境识别、边界行号                       | Unit               | 切片范围正确；不越界       |
| TX-03 | 日志解析                     | latexmk/pdflatex 日志常见错误              | Unit               | 解析出标准化 issues 列表 |
| TX-04 | 建议/应用                    | suggestion merge、apply\_edit/compare | Unit               | 应用后文本符合预期；冲突可检测  |
| TX-05 | chktex/latexmk runner 退化 | 命令不存在/返回非 0/超时                       | Unit               | 返回可读错误；不崩溃       |
| TX-06 | LaTeX 工具链集成              | 在有 TeX 环境下编译/静态检查                    | latex\_integration | 生成产物与诊断一致        |
| TX-07 | WatchService 事件链路        | 新增/修改/删除 tex 文件                      | Integration        | 快照更新正确；停止后线程退出   |
| TX-08 | Ghost server API         | 启动→请求→返回                             | Integration/slow   | API 可用；错误码与消息合理  |

### 8.4 RAG 子系统（loader/parse/vector store/pipeline）

| 编号    | 测试项                | 重点用例                    | 分层               | 预期              |
| ----- | ------------------ | ----------------------- | ---------------- | --------------- |
| RG-01 | 文档加载               | 支持类型、空文件、坏编码            | Unit             | 返回文档对象或明确错误     |
| RG-02 | chunk 与规范化         | 超长行、空白折叠、多语言            | Unit             | chunk 数、边界与内容稳定 |
| RG-03 | vector store 列表/删除 | 列表格式、空库、删除不存在           | Unit/Integration | 行为可预期；幂等        |
| RG-04 | pipeline mock 集成   | 使用 mock embedding/检索    | Integration      | 召回结果结构正确        |
| RG-05 | pipeline 真集成       | chromadb + 默认 embedding | integration      | 端到端索引/检索可用      |

### 8.5 Tools（工具系统）

| 编号    | 测试项               | 重点用例                          | 分层               | 预期                   |
| ----- | ----------------- | ----------------------------- | ---------------- | -------------------- |
| TL-01 | 输入校验（pydantic/参数） | 缺字段/类型错/非法枚举                  | Unit             | 抛出一致错误；错误信息可定位       |
| TL-02 | 命令执行工具            | 正常输出/超时/非 0/取消                | Unit/Integration | 返回结构化结果；不泄露敏感信息      |
| TL-03 | 文档解析工具            | docling/pymupdf 的退化路径         | Unit             | 未安装/异常时提示清晰          |
| TL-04 | Web 工具箱           | chart/diagram/qrcode/markdown | Unit             | 输出文件生成；registry 记录正确 |

### 8.6 Web UI（FastAPI）

| 编号     | 测试项            | 重点用例                | 分层               | 预期            |
| ------ | -------------- | ------------------- | ---------------- | ------------- |
| WEB-01 | App 启动与路由      | 应用可 import；关键路由 200 | Unit/Integration | 基本路由响应；异常路径合理 |
| WEB-02 | 文件上传/下载        | 上传空文件/大文件边界/非法扩展    | Integration      | 存储路径正确；安全检查生效 |
| WEB-03 | Streaming 响应   | 中断/取消/异常            | Integration      | 不阻塞；错误返回明确    |
| WEB-04 | CORS/中间件       | 允许源/禁止源/头部处理        | Unit             | 响应头符合策略       |
| WEB-05 | conferences 数据 | deadline JSON 解析、筛选 | Unit             | 输出排序正确；坏数据可处理 |

### 8.7 Overleaf 服务

| 编号    | 测试项         | 重点用例                     | 分层                 | 预期           |
| ----- | ----------- | ------------------------ | ------------------ | ------------ |
| OV-01 | 服务启动与静态资源   | index.html、editor.js 可访问 | Integration        | 静态资源 200     |
| OV-02 | 编译 API（若启用） | 无 TeX 环境/有 TeX 环境        | latex\_integration | 退化提示/编译成功    |
| OV-03 | 生成器/模板      | thesis\_generator 输出结构   | Unit               | 输出可解析；关键字段齐全 |

### 8.8 CLI/脚本入口（烟测）

| 编号     | 测试项                  | 重点用例             | 分层       | 预期          |
| ------ | -------------------- | ---------------- | -------- | ----------- |
| CLI-01 | `main.py` 子命令解析      | 不同命令、缺参、非法参数     | Unit     | help/错误码稳定  |
| CLI-02 | `check_text.py` 最小运行 | 指定最小输入与 mock     | E2E/slow | 运行完成并输出结果结构 |
| CLI-03 | `check.py` 配置读取      | config 缺字段/路径不存在 | Unit     | 明确报错，定位字段   |

## 9. 非功能性测试

### 9.1 可靠性与鲁棒性

- 异常输入（坏 JSON、坏 latex、坏 PDF）不导致崩溃；返回结构化错误。
- 外部依赖缺失时有清晰退化提示（TeX 命令、docling、网络、embedding）。

### 9.2 安全

- 路径穿越：上传文件名/路径参数不可写入仓库外。
- XSS/HTML 注入：Web UI markdown 渲染输入经净化（做基本回归断言）。
- 敏感信息：日志/返回体不包含密钥与环境变量内容。

### 9.3 性能（后续专项）

- RAG 建索引与检索耗时上限（小样本基线）。
- LaTeX 日志解析与索引在中等工程规模下的耗时基线。

## 10. 执行方式与测试集划分

### 10.1 本地执行（建议命令）

仅跑新增目录：

```bash
pytest -q qa_tests
```

快速回归（排除外部依赖与慢测）：

```bash
pytest -q qa_tests -m "not integration and not latex_integration and not slow"
```

仅 RAG 集成：

```bash
pytest -q qa_tests -m integration
```

仅 LaTeX 工具链集成：

```bash
pytest -q qa_tests -m latex_integration
```

### 10.2 失败定位要求

每个测试应做到：

- 断言信息可读（包含关键输入/路径/状态片段）。
- 失败时能定位到模块与场景（通过文件名、用例名、marker）。

## 11. 进入/退出准则（Entry/Exit Criteria）

### 11.1 进入准则

- 依赖安装完成，基础模块可 import。
- 集成测试所需外部依赖可用（否则跳过相应 marker）。

### 11.2 退出准则

- P0 用例全部通过；P1 用例通过率满足团队标准。
- 主要模块均具备至少 1 个单元测试覆盖关键路径。
- 集成测试在具备依赖的环境中可稳定通过（允许按 marker 选择性执行）。

## 12. 风险与缓解

- 外部依赖不稳定（网络/模型下载/系统命令）：通过 marker 分离 + 可控跳过；优先 mock 单元测试覆盖逻辑。
- 端到端链路慢且波动：限制 E2E 数量，仅保留烟测；将复杂场景下沉到集成/单元。
- 平台差异（Windows 路径/编码）：专门覆盖路径分隔与编码用例；使用 `pathlib` 与 `tmp_path` 夹具生成路径。

