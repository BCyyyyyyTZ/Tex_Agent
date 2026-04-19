# RAG 相关的说明文档

## 目前实现的内容及代码解释

### 抽象层

> 目录：/Tex_Agent/rag/base_retriever.py

三个基本的类：BaseRetriever / BaseRAGPipeline / RetrievedDocument

作用：定义向量检索器与高层 RAG 管道的接口，以及单条检索结果的数据结构，便于 workflow 侧依赖抽象、测试时 Mock

#### RetrievedDocument

这是**单条检索结果的数据容器**，包含几个字段的信息：

+ content: 文档片段的文本内容
+ source:  来源文件名或 URL，用于引用标注
+ score:   相关性分数（0~1，越高越相关）
+ metadata: 附加元数据（如 chunk 序号、原文页码等）

```python
@dataclass
class RetrievedDocument:
    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)
```

#### BaseRAGPipeline

**检索管道抽象基类（高层接口）**，负责向向量库中批量添加文档

*基类仅是接口，具体的实现细节要在继承子类中实现*

#### BaseRetriever

**向量检索器抽象基类（低层接口）**

负责：封装对具体向量数据库的增删查操作，屏蔽各向量库的 API 差异

除 `add_documents` / `retrieve` / `clear` / `document_count` 等抽象方法外，还提供 **`list_stored_page(offset, limit, fetch_fields)`**：分页列举库中已存储的 chunk，返回 **`StoredChunksPage`**（定义见 **`rag/store_listing.py`**）。**默认实现**为抛出 `NotImplementedError`；**`ChromaRetriever`** 与测试用 **`MockRetriever`** 中给出具体实现。

### 文档加载与分块

> 目录：/Tex_Agent/rag/document_loader.py

目前只实现了基本的文件类型和最基础的overlap分块

#### chunk_text：将长文本切割为固定大小、带重叠的文本块

使用滑动窗口策略保证上下文连续性：每个 chunk 的末尾 overlap 个字符与下一个 chunk 的开头重叠，避免在 chunk 边界处切断关键语义信息。

**注**：以字符数为单位切分（非 Token），跨语言均适用；建议 overlap < chunk_size / 5，避免冗余内容过多

输入参数：
+ text:       待分块的原始文本
+ chunk_size: 每块的最大字符数（默认 500）
+ overlap:    相邻块之间的重叠字符数（默认 50）

```python
def chunk_text(text: str, chunk_size: int = 500,  overlap: int = 50,
) -> List[str]:
    text = text.strip()
    ...  # 边界判断
    chunks: List[str] = []
    step = chunk_size - overlap
    ...
    start = 0
    while start < len(text):
        ... # 滑动窗口进行分块
    return chunks
```

#### 读取文档再分块

**注：目前支持的文件类型 .txt / .md / .tex**

`load_text_file()`：**输入文件绝对路径/相对路径**，读取文本文件内容（UTF-8 编码）

`load_and_chunk()`：加载文件并切块
    输入参数：文件路径、块数、重叠字符数
    返回内容包括文档块列表、文件名（source）和块序号（chunk_idx）

```python
def load_text_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    return file_path.read_text(encoding="utf-8")

def load_and_chunk(path: str, chunk_size: int = 500, overlap: int = 50,
) -> Tuple[List[str], List[dict]]:
    file_path = Path(path)
    ... # 边界判断 & 检查文件类型是否合规
    content = load_text_file(path) # 加载文件
    chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)  # 文档分块
    metadatas = [ # 元数据列表，包括文件路径和块号
        {"source": file_path.name, "chunk_idx": i}
        for i in range(len(chunks))
    ]
    return chunks, metadatas
```

### 向量存储和检索 ChromaRetriever

> 目录：/Tex_Agent/rag/vector_store.py

ChromaRetriever类继承自BaseRetriever，是**基于 ChromaDB 的本地向量检索器**

类定义的输入参数：
+ collection_name:   ChromaDB 集合名称（相当于向量库中的"表"）
+ persist_directory: 持久化存储路径。None 表示使用内存模式（进程退出后数据丢失）
+ embedding_fn:      自定义 Embedding 函数。None 时使用 ChromaDB 默认 Embedding

目前分为内存模式（`chromadb.EphemeralClient()`）、持久化模式（`PersistentClient(path=...)`）

```python
class ChromaRetriever(BaseRetriever):
    """
    Example:
        # 内存模式（测试用）
        retriever = ChromaRetriever()
        retriever.add_documents(["关于 Transformer 的研究..."], [{"source": "paper.txt"}])
        docs = retriever.retrieve("注意力机制", k=3)

        # 持久化模式（生产用）
        retriever = ChromaRetriever(persist_directory="./chroma_data")
    """
    ...
```

#### add_documents

批量向 ChromaDB 集合添加文档，每条文档自动生成唯一 UUID 作为 ID
ChromaDB 会自动调用 embedding_fn 对文本向量化并存储

```python
    def add_documents(self, texts: List[str], metadatas: Optional[List[dict]] = None, ) -> int:
        ids = [str(uuid.uuid4()) for _ in texts]
        metas = metadatas if metadatas is not None else [{} for _ in texts]
        self._collection.add(documents=texts, ids=ids, metadatas=metas, )
        return len(texts)
```

#### retrieve

向 ChromaDB 执行近邻搜索，返回最相关的文档片段列表，query → RetrievedDocument 列表。
相似度分数：score = 1 / (1 + distance)

```python
    def retrieve(self, query: str, k: int = 5) -> List[RetrievedDocument]:
        results = self._collection.query(
            query_texts=[query],
            n_results=min(k, self.document_count()),
            include=["documents", "metadatas", "distances"],
        )

        documents: List[RetrievedDocument] = []
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            distance = results["distances"][0][i] if results.get("distances") else 1.0
            score = 1.0 / (1.0 + distance)

            documents.append(
                RetrievedDocument(
                    content=doc_text,
                    source=meta.get("source", ""),
                    score=round(score, 4),
                    metadata=meta,
                )
            )

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents
```

#### clear

删除并重新创建集合，实现清空所有文档的效果

#### document_count

返回当前集合中存储的文档片段数量

#### list_stored_page（分页列举）

基于 Chroma `collection.get(include=..., limit=..., offset=...)` 拉取当前集合中的一页记录，返回 `StoredChunksPage`，**不在此层做终端打印**。

### 列举与展示（数据结构 + 格式化）

> 目录：`rag/store_listing.py`

与具体向量库实现解耦的一层：描述一页数据的结构

+ **`StoreField`（`Flag`）**：`ID`、`METADATA`、`DOCUMENT`、`EMBEDDING` 的组合；预置 **`DEFAULT = ID | METADATA`**、**`MINIMAL = ID`**、**`FULL`**（含正文与向量，体积大，一般仅调试）。
+ **`StoredChunkRecord`**：单条记录，含 `id` 以及可选的 `metadata` / `document` / `embedding`。
+ **`StoredChunksPage`**：`items`、`total`、`offset`、`limit`、`persist_directory`、`collection_name`；**`has_next`** 表示是否还有下一页。
+ **`format_stored_chunks_page(page, display=..., document_max_chars=...)`** → `str`，便于日志、API 或其它模块再加工。
+ **`print_stored_chunks_page(..., stream=sys.stdout)`**：内部调用 `format_*`，向指定流输出。
典型数据流：**`RAGPipeline.list_stored_page`**（或 **`ChromaRetriever.list_stored_page`**）得到 **`StoredChunksPage`** → **`format_stored_chunks_page`** / **`print_stored_chunks_page`** 负责展示。

### 端到端管道 RAGPipeline

> 目录：/Tex_Agent/rag/rag_pipeline.py

输入参数：
+ retriever:    底层向量检索器实例（BaseRetriever 接口）。未注入retriever时延迟导入 ChromaRetrieve，避免未装 chromadb 时 import 即崩
+ chunk_size:   文本分块大小（字符数）。None 时读取 settings.rag_chunk_size
+ chunk_overlap: 分块重叠字符数。None 时读取 settings.rag_chunk_overlap
+ persist_directory: 向量库持久化路径（仅当 retriever=None 时生效）


```Python
class RAGPipeline(BaseRAGPipeline):
    """
    Example:
        # 快速使用（内存模式）
        pipeline = RAGPipeline()
        pipeline.index_text("Transformer 使用多头注意力机制...", source="intro.txt")
        result = pipeline.retrieve("attention mechanism")
        print(result)

        # 持久化模式
        pipeline = RAGPipeline(persist_directory="./knowledge_base")
        pipeline.index_file("papers/survey.md")
        result = pipeline.retrieve("大语言模型综述")
    """
    ...
```

#### 索引接口 index_text、index_file

`index_text()` 对原始文本分块后写入向量库：chunk_text → add_documents

输入参数：
+ text:     待索引的原始文本
+ source:   文本来源标识（文件名、URL 等）
+ metadata: 附加到所有分块的元数据

`index_file()`加载本地文件，分块后写入向量库：load_and_chunk → add_documents

输入参数：path: 文件路径（支持 .txt / .md / .tex）

#### 检索接口 retrieve

调用底层 retrieve，格式化成多段中文提示串，供直接塞进 Prompt

输入参数：
+ query: 检索查询文本（通常为用户原始任务描述）
+ k:     返回片段数，None 时使用 settings.rag_top_k

返回的字符串格式设计为可直接嵌入 LLM Prompt 的参考资料段落：
```
            【相关片段 1】（来源：paper.md）
            ...片段内容...

            ---

            【相关片段 2】（来源：survey.txt）
            ...片段内容...
```

```python
    def retrieve(self, query: str, k: Optional[int] = None) -> str:
        # 调用底层的retrieve函数
        docs = self._retriever.retrieve(query, k=actual_k)
        parts = [
            f"【相关片段 {i + 1}】（来源：{d.source or '未知'}，相关度：{d.score:.2f}）\n{d.content}"
            for i, d in enumerate(docs)
        ]
        return "\n\n---\n\n".join(parts)
```

#### is_ready

知识库中有索引内容（调用底层document_count() > 0）时返回 True

#### clear

调用底层clear，清空知识库中的所有文档

#### document_count

调用底层document_count，返回当前知识库中的文档片段总数

#### list_stored_page

委托底层 `BaseRetriever.list_stored_page`

### workflow接入：Retrieve 节点 + 图拓扑

[对workflow的说明](../README.md)在README中

#### 节点函数 make_retrieve_node

> 目录：/Tex_Agent/workflow/nodes.py

pipeline.is_ready() 检查是否有准备好的知识库 -> pipeline.retrieve(input) 检索并返回信息

#### 图构建

> 目录：/Tex_Agent/workflow/graph_builder.py

传入 rag_pipeline 时：START → design → retrieve → think → execute → END

注意：make_retrieve_node 的参数里有 ctx，但当前实现里没有使用 ctx；检索只依赖 state["input"]

### 状态与prompt注入

#### 状态字段

> 目录：/Tex_Agent/core/state.py

相关字段：retrieved_context: str  # RAG 检索结果，由 retrieve_node 写入；未启用 RAG 时为空

#### 上下文拼装

> 目录：/Tex_Agent/context/context_manager.py

若 retrieved_context 非空，会包一层 `<context type='retrieved'>`，供后续各节点 Prompt 使用

*暂未深入理解上下文工程*

### 全局配置

> 目录：/Tex_Agent/config/settings.py

+ rag_chunk_size: int = 500   # 文档分块大小（字符数），较大值保留更多上下文，但向量质量下降
+ rag_chunk_overlap: int = 50 # 相邻块重叠字符数
+ rag_top_k: int = 5          # 次检索返回的最大片段数，注入 Prompt 的片段越多 Token 消耗越大
+ rag_persist_directory       # 向量库持久化路径，空字符串表示使用内存模式（进程退出后清空）

#### 向量库持久化路径说明

RAG_PERSIST_DIR -- rag_persist_directory

目前的环境变量是默认在项目根目录下的`./knowledge_base`路径

在`settings.py`中添加了对路径转化为绝对路径的解析函数，相对路径可以转化成绝对路径而直接使用

### Docling 文档解析

> 目录：rag/docling_parse.py 与 tools/docling_tool.py

#### 定位与分工
- **`docling_parse.py`**：底层「单次解析」——把本地文档交给 Docling，写出 `document.md`、`document.json` 及资源目录；不关心是否曾被解析过。
- **`docling_tool.py`**：对外 **Tool**——在相同落盘规则下，增加 **按文件名复用已有输出** 的策略，减少重复跑 Docling。

#### 设计思路
1. **落盘结构**：在解析根目录（默认 `doc/parsed_doc`，见配置）下创建子目录 `{净化后的源文件名}_{Unix时间戳}`，避免多次解析互相覆盖。
2. **设备选择**：PDF 可根据配置在 **CPU 默认管线** 与 **CUDA 线程化 PDF 管线** 间切换；非 PDF 仍走 Docling 的默认格式处理。与「输出路径」无关，GPU/CPU 写入同一套目录逻辑。
3. **大 PDF**：先按页数做路由（阈值见环境变量）；旁路相关能力在代码中预留，当前以默认管线为主。
4. **Tool 层缓存**：`redo=False`（默认）时，在解析根目录下查找 **目录名前缀** 与「当前源文件 stem 经同样规则净化后」一致、且已有 **非空** `document.md` / `document.json` 的子目录；命中则 **直接返回路径**，不再次调用 Docling。`redo=True` 时 **始终重新解析**。

#### 对外约定（接口层面）
- 库函数返回 **`DoclingParseResult`**：含是否成功、`output_dir`、`markdown_path`、`json_path`、`artifacts_dir`、错误信息及路由/页数等观测字段。
- Tool 返回 **`ToolResult`**：人类可读说明在 **`output`**；机器好用字段在 **`metadata`**（如 `markdown_path`、`json_path`、`from_cache`、`redo` 等）。

---

## 外部调用说明

### 向量库手动注入

> 目录：Tex_Agent/rag/rag_index_cli.py

需要在Tex_Agent根目录执行：

```bash
python rag/rag_index_cli.py              # 交互输入路径
# 或者
python rag/rag_index_cli.py a.md b.tex   # 直接指定文件
```

路径方面可以使用绝对路径也可以使用相对路径，相对于当前工作目录

可以在交互输入路径中输入多个文件路径，最后输入空行或 quit / exit 结束即可开始索引

**注：目前没有支持pdf直接注入，可以注入的文本类型为.txt, .md, .tex**

### 向量库内容查看

> 目录：rag/rag_list_cli.py

用于在终端查看当前 RAG / Chroma 中已有哪些 chunk


+ 交互浏览（TTY 下）：默认每页 5 条；w 上一页、s 下一页、e / Esc / q 退出:
```bash
    python -m rag.rag_list_cli
```
+ 只打印一页到 stdout 后退出
```bash
    python -m rag.rag_list_cli --dump
```
+ 从指定偏移开始的一页；控制每页条数（不超过 5）
```bash
    python -m rag.rag_list_cli --dump --offset 5 --limit 5
```

用标志位组合控制拉取与展示内容：加上 --metadata 可看 source、chunk_idx 等；加上 --document 可看该块正文节选

```bash
python -m rag.rag_list_cli --metadata --document
```

### 向量数据库删除

目前支持按id删除和按resource删除的操作：

```bash
# 查看可选命令
python rag/rag_delete_cli.py --help

# 按id删除一条或多条记录
# 建议通过 rag.rag_list_cli 先查看好需要删除的id，再删除
python rag/rag_delete_cli.py --ids <uuid1> <uuid2> ...

# 按来源名删整文件产生的 chunk
python rag/rag_delete_cli.py --source <文件名或字符串>

# 整个库的清空
# 必须同时带 --yes，防止误删
python rag/rag_delete_cli.py --clear-all --yes
```

### Docling 解析

> 目录：rag/docling_parse.py

+ 命令行直接调用文档解析工具：

  ```bash
    python rag/docling_parse.py <源文件路径> [-o 输出根目录]
  ```

  > 不传 `-o` 时使用配置中的解析根目录，目前是`Tex_Agent\doc\parsed_doc`


+ 代码调用：

  ```python
  from rag.docling_parse import parse_document_to_dir
  
  parse_document_to_dir(source, [output_root])

### Docling 解析：Tool

> 目录：tools/docling_tool.py

- **工具名**：`docling_parse`（已加入 `tools/tool_list.py`）。
- **参数**：  
  - `doc_path`（必填）：待解析文件路径。  
  - `redo`（可选，默认 `False`）：`True` 强制重新解析；`False` 时优先命中缓存。
- **Python 直接调用**：
  ```python
  DoclingParseTool().run(doc_path="...", redo=False)
  ```
  检查 `ToolResult.success` 与 `metadata` 中的路径字段，如果非redo且命中就直接复用现有结果

---

## 未来实现方向

### 近期优化目标

- [ ] docling解析工具对大pdf的支持（目前思路是分块解析+拼接）
- [ ] RAG库封装入tool
- [ ] RAG库的删除单项操作
- [ ] RAG库方法优化：支持markdown文件按标题和段落chunk，而非纯字符数
- [ ] RAG库方法优化：支持tex文件按标题和段落chunk，而非纯字符数（可能考虑解析tex的方法？）
- [ ] RAG库多层次设计

### 按实现难度从易到难的 RAG 功能建议（面向论文写作）

#### 1) 检索结果“可引用化”输出（很容易）
做什么：把检索结果统一成“片段 + 来源 + 引文键（citation key）”格式，例如 [R1]。
改动点：rag/rag_pipeline.py 的 retrieve() 返回格式。
论文帮助：模型生成正文时可以直接引用证据，减少“无来源陈述”。
价值：立刻提升可解释性，几乎零架构风险。

#### 2) 查询重写（Query Rewrite）与关键词扩展（容易）
做什么：在 retrieve 前增加轻量重写：同义词扩展、英文术语展开、缩写展开。
改动点：workflow/nodes.py 的 make_retrieve_node() 前置处理；或在 rag_pipeline.retrieve() 内封装。
论文帮助：提升“相关工作”检索召回率（尤其中英混合术语场景）。
价值：少量代码可显著改善 top-k 命中。

#### 3) 动态 top-k + 分数阈值 + 空检索回退（容易）
做什么：按任务类型调 k；低于阈值则触发“扩展查询/提示无足够证据”。
改动点：config/settings.py 增加阈值配置；retrieve_node 增加判断逻辑。
论文帮助：降低把低相关片段硬塞进 prompt 的风险，减少幻觉。

#### 4) 面向 LaTeX/Markdown 的结构化分块（中等偏易）
做什么：按章节标题、段落、公式块分块，而不是纯字符窗口。
改动点：rag/document_loader.py（新增 smart chunk 策略）。
论文帮助：检索片段语义更完整，尤其“方法/实验”段落不被切裂。
科研点：可对比“固定窗口 vs 结构分块”的效果。

#### 5) 元数据增强检索（中等）
做什么：写入并利用 year/venue/authors/section_type/task_type 等 metadata 过滤。
改动点：index_file/index_text 的 metadata 组织 + vector_store 查询过滤。
论文帮助：例如“只检索近五年方法类文献”，更符合写作需求。
价值：让 RAG 从“搜相似文本”进化到“可控学术检索”。

#### 6) 混合检索（向量 + 关键词 BM25）与重排序（中等偏难）
做什么：先并行做 dense/sparse 检索，再融合重排（RRF 或交叉编码器）。
改动点：在 rag/ 下加 hybrid retriever 适配层。
论文帮助：专业术语、公式符号、实体名通常 keyword 检索更强，混合检索更稳。
科研点：可写成“Hybrid Retrieval for Academic Writing Assistant”。

#### 7) 写作任务感知检索（中等偏难）
做什么：根据当前任务是“引言/相关工作/方法/实验”走不同检索模板。
改动点：workflow/nodes.py 中 retrieve 与 think 的任务路由。
论文帮助：不同章节拿到不同证据类型（综述类 vs 方法细节 vs 数值对比）。
价值：从通用 RAG 升级到“论文写作专用 RAG”。

#### 8) 证据-主张对齐（Claim-Evidence Alignment）（难）
做什么：让模型输出“每条主张对应哪几个检索片段”，并打置信度。
改动点：think/execute prompt 输出协议 + metadata 结果结构。
论文帮助：可直接用于“可追溯写作”，审稿时很加分。
科研点：能形成你系统的核心创新卖点之一。

#### 9) 自动“相关工作综述矩阵”生成（难）
做什么：RAG 检索后自动组织成“方法-数据集-指标-优缺点”矩阵。
改动点：新增一个专用节点（可插在 retrieve -> think 之间）。
论文帮助：直接服务 related work 写作，节省大量人工整理时间。
价值：用户可感知收益非常强。

#### 10) RAG 评测基准与可复现实验脚本（最难但最值得写论文）
做什么：建立离线评测（Recall@k、MRR、引用覆盖率、事实一致性）。
改动点：tests/test_rag/ 扩展为数据集驱动评测脚本。
论文帮助：没有评测就很难发表；这是从“工程功能”走向“研究成果”的关键。
科研点：可以形成完整实验章节。

### 你可以优先走的两条路线
+ 工程落地优先（快出效果）：1 → 2 → 3 → 4 → 5
+ 论文创新优先（快出研究点）：4 → 6 → 8 → 10

### 给你的 MVP 建议（不含 memory/context）

如果你只做一个月，我建议你先做这 4 个：

可引用化输出
查询重写
结构化分块
RAG评测脚本

这四个组合已经足够写一篇“论文写作辅助 RAG 优化”的中小型实验论文。