
## 第一阶段：项目初期与中期前（核心底层、最小可运行单元与统一接口）

- [ ] 确立系统最底层的通信基石，定义智能体之间消息传递的标准数据结构（如发件人、收件人、消息体、时间戳等）以及发布-订阅机制
    > 核心总线代码实现在 Tex/core/message_bus.py 和 Tex/core/event_system.py 中

- [ ] 基于上述总线实现多智能体通信协议，确保不同 Agent 能正确序列化和反序列化标准化消息，不产生信息丢失
    > Tex/mas/agent_communication.py

- [ ] 搭建基础的 Agent 父类接口，规范化所有智能体的初始化、执行入口、状态流转与错误处理逻辑
    > 相关抽象类代码写入 Tex/core/base_agent.py 和 Tex/core/state_machine.py

- [ ] 实现一个智能体注册中心，方便后续的统一管理和动态调用
    > Tex/core/agent_registry.py

- [ ] 在此底层基础上，详细实现四种最基础的 Agent 架构：
  - [ ] 在 Tex/agents/base/simple_agent.py 中编写单次推理和直接封装工具调用的线性逻辑
  - [ ] 在 Tex/agents/base/react_agent.py 中实现包含思考（Thought）、行动（Action）、观察（Observation）循环的推理链路解析与控制流
  - [ ] 在 Tex/agents/base/reflection_agent.py 中实现生成初稿、利用评价准则进行自我评价、再进入循环修正的内部反馈逻辑
  - [ ] 在 Tex/agents/base/plan_and_solve_agent.py 中编写将复杂数学或逻辑任务拆解为子任务队列，并按顺序调度执行器的代码
  
  注：各 Agent 对应的具体基础系统提示词文本，则需分类写入 Tex/prompts/agents/base/ 目录下的对应 python 文件中（此处为硬编码的prompts实现，后续再转化成支持自定义建构的prompts）

- [ ] 将这些散落的 Agent 串联起来，构建基于 LangGraph 思想的图工作流引擎
  - [ ] 在 Tex/mas/graph_builder.py 中编写图结构的节点（Node）定义与条件边（Edge）的路由判断逻辑
  - [ ] 在 Tex/mas/workflow_engine.py 中实现图的遍历、全局状态在节点间的传递、以及多 Agent 并发执行与等待的控制流

- [ ]  实现基于 JSON/YAML 的配置文件解析器，允许用户在外部定义工作流 DAG 结构和注入自定义提示词
    > Tex/config/agent_configs.py 和 Tex/config/settings.py

- [ ]  中期先实现最简易的线性上下文保存：
  - [ ]  在 Tex/context/session/session_manager.py 中编写会话 ID 的生成、加载与销毁逻辑
  - [ ]  在 Tex/memory/short_term/conversation_memory.py 中实现基于 Token 长度的滑动窗口截断机制和基础的对话历史追加（Append-only）功能，暂不处理复杂分支

- [ ] RAG 模块同样搭建最小可用版本：
  - [ ] 在 Tex/rag/processors/document_processor.py 和 Tex/rag/processors/chunk_splitter.py 中实现对单一 TXT 或 PDF 文本的字符级读取与简单的固定长度或按段落分块
  - [ ] 在 Tex/rag/processors/embedding_generator.py 中编写调用本地 Sentence-Transformers 或 OpenAI API 生成向量的函数
  - [ ] 在 Tex/memory/long_term/vector_store.py 和 Tex/rag/retrievers/local_retriever.py 中封装对本地向量数据库（如 ChromaDB）的最基础初始化、数据插入和 Top-K 相似度检索函数

- [ ] 提前定义好 Tool 和 Skill 的标准入参和出参接口验证
    > Tex/skills/skill_registry.py 和 Tex/skills/skill_executor.py

- [ ] 针对单一 LaTeX 文本的理解:
  - [ ] 在 Tex/tools/latex/parser.py 中实现基于正则表达式的简单标签过滤和正文段落提取
  - [ ] 在 Tex/tools/latex/validator.py 中编写最基础的 LaTeX 括号匹配、环境闭合等基本语法检查逻辑

- [ ] 在此基础上实现第一批初级的学术文本处理技能:封装具体的 LLM 提示词调用，完成特定段落的重写与润色
    > Tex/skills/academic/abstract_writing_skill.py 和 Tex/skills/academic/introduction_writing_skill.py

- [ ] 将上述技能组装进专业智能体：在 Tex/agents/specialized/writing_agent.py 和 Tex/agents/specialized/literature_agent.py 中实现对文本工具的条件触发和处理结果整理。

- [ ] 开发一个纯命令行的交互界面：
  - [ ] 在 Tex/ui/cli/main_cli.py 中实现一个持续监听用户输入的 REPL（读取-求值-输出）循环
  - [ ] 在 Tex/ui/cli/output_formatter.py 中编写拦截 Agent 内部流式输出、高亮特定角色信息，并将执行过程以清晰的纯文本格式打印到控制台的逻辑


## 第二阶段：项目中后期（复杂逻辑理解、高级存储与智能路由）

- [ ] 复杂文档的解析：引入 AST（抽象语法树）解析，处理 \input 和 \include 命令，实现跨文件的复杂多层级 LaTeX 目录结构理解与整体格式化
    > Tex/tools/latex/formatter.py 和 Tex/plugins/latex_plugin/plugin_core.py

- [ ] 正式引入复杂的多分支上下文管理（类似 Git）：
  - [ ] 在 Tex/context/branch/checkpoint_manager.py 中实现记忆状态的快照打包与持久化
  - [ ] 在 Tex/context/branch/branch_manager.py 中实现分支树的创建、指针移动以及让 Agent 的短期记忆在不同节点间平滑切换的功能
  - [ ] 在 Tex/context/branch/branch_diff.py 和 Tex/context/branch/merge_handler.py 中实现不同分支想法的差异比对与合并逻辑

- [ ] 开发数据分析功能：集成 pandas 和 scipy，实现对用户上传 CSV/Excel 数据的读取和描述性统计计算
    > ex/tools/analysis/statistical_analysis.py

- [ ] 编写将用户的自然语言分析需求转化为具体 Python 分析代码并交由工具执行的智能体逻辑
    > Tex/agents/specialized/analysis_agent.py

- [ ] 构建智能路由核心模块：
  - [ ] 在 Tex/router/task_classifier.py 中实现对用户意图的分类识别（如判定是写作、查文献还是数据分析）
  - [ ] 在 Tex/router/complexity_estimator.py 中编写估算任务复杂度的算法，决定是分配给轻量级模型还是推理大模型
  - [ ] 在 Tex/router/routing_strategies/adaptive_router.py 和 Tex/agents/meta/router_agent.py 中实现根据上述参数动态分发任务给特定 Agent 并回收结果的自适应路由中枢

- [ ] 升级 RAG 系统：建立多节点知识库，实现基于关键词和稠密向量的混合检索，提高领域知识理解的准确率
    > Tex/rag/knowledge_bases/expert_kb.py 和 Tex/rag/retrievers/hybrid_retriever.py

- [ ] 开始开发轻量级 Web 服务接口：
  - [ ] 在 Tex/api/main.py 和 Tex/api/routes/agent_routes.py 中使用 FastAPI 编写 RESTful 接口，将 Agent 的执行过程暴露给网络请求
  - [ ] 在 Tex/ui/web/app.py 中利用 Gradio 或 Streamlit 搭建提供文件上传、状态可视化和聊天窗口的轻量级 Web 交互界面

## 第三阶段：项目后期（外围扩展功能、人性化体验与安全底座）

- [ ] 开发可视化功能：
  - [ ] 在 Tex/tools/visualization/chart_generator.py 中封装 matplotlib/seaborn，实现根据统计数据自动生成符合 IEEE 标准格式图表的代码生成器
  - [ ] 在 Tex/agents/specialized/visualization_agent.py 中编写接收分析结果并调度图表生成工具的逻辑

- [ ] 开发图像生成能力：
  - [ ] 在 Tex/tools/image_generation/dalle_client.py 中编写接入外部绘画 API 的网络请求与重试逻辑
  - [ ] 在 Tex/tools/image_generation/tikz_generator.py 中编写将自然语言精确转换为 LaTeX TikZ 绘图代码的特定 Prompt 链路

- [ ] 实现情感陪伴边缘功能：
  - [ ] 在 Tex/companion/emotion_detector.py 中编写分析用户输入文本以提取情绪特征（如焦虑、疲惫）的轻量级判别逻辑
  - [ ] 在 Tex/companion/encouragement_generator.py 和 Tex/agents/specialized/companion_agent.py 中编写在科研长期任务中适时穿插鼓励性话语和情绪价值反馈的生成模块

- [ ] 完善系统安全与权限底座：
  - [ ] 在 Tex/security/auth_manager.py 和 Tex/security/permission_controller.py 中实现 API 密钥鉴权、用户身份验证以及针对特定目录下文档的操作权限拦截
  - [ ] 在 Tex/security/data_sanitizer.py 和 Tex/security/audit_logger.py 中实现对敏感学术数据的脱敏处理，以及对系统异常调用和重要操作的日志持久化记录