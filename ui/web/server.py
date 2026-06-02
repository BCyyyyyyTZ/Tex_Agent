"""
TeX Agent Web UI：FastAPI 服务 + 静态页面（Cursor 风格聊天 + Markdown）。

启动：
  uvicorn ui.web.server:app --host 127.0.0.1 --port 8765
或：
  python -m ui.web.server
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import queue
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from collections import deque
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Set, Tuple

import anyio
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.agent_cli import TeXAgentCLI, _serialize_plan_graph_for_ui
from utils.run_cancel import clear_run_cancel, install_sigint_handler, is_run_cancelled
from ui.web import file_storage
from ui.web.conferences_data import list_deadlines
from latex.watch_service import WatchService
from latex.watch_events import WatchSnapshot

STATIC_DIR = Path(__file__).resolve().parent / "static"

# 左侧编排默认：与 default 同构的两步 Agent 链，用户可再改
DEFAULT_WEB_WORKFLOW: Dict[str, Any] = {
    "nodes": [
        {
            "node_id": "design",
            "node_type": "agent",
            "agent_name": "SimpleAgent",
            "config": {
                "system_prompt": "你是设计节点，把用户问题整理为清晰任务说明与可执行结构，供下一节点使用。",
                "subtask": "提炼目标、约束与输出形式。",
                "depends_on": [],
                "temperature": 0.5,
            },
        },
        {
            "node_id": "execute",
            "node_type": "agent",
            "agent_name": "SimpleAgent",
            "config": {
                "system_prompt": "你是执行/交付节点，基于上游设计生成完整、可执行的最终回答。",
                "subtask": "输出最终可交付内容。",
                "depends_on": ["design"],
                "temperature": 0.4,
            },
        },
    ],
    "edges": [
        {"from_node": "design", "to_node": "execute", "condition": None},
    ],
}


def _sanitize_reply_text(text: str) -> str:
    from utils.reply_format import format_reply_for_ui

    return format_reply_for_ui(text)


def _format_reply_from_result(result: Dict[str, Any]) -> str:
    """
    从工作流 state 中只取「最后一处节点产物」的文本，原样给前端做 Markdown 渲染。

    优先顺序与 workflow/state 一致：
    1) state.output — 由末端交付节点写入的终端输出
    2) metadata[__execution_order__] 中最后一个 node_id 的 result（NodeOutput）
    3) 退化为最后一条含内容的 assistant 消息（极少情况下 output / 元数据未写）
    """
    err = result.get("error")
    meta: Dict[str, Any] = result.get("metadata") or {}

    if err:
        body = f"**执行出错**\n\n```\n{err}\n```"
        return _append_artifact_download_links_to_reply(body, meta)

    out = str(result.get("output") or "").strip()
    if out:
        return _append_artifact_download_links_to_reply(_sanitize_reply_text(out), meta)

    order = meta.get("__execution_order__")
    if isinstance(order, list) and order:
        last_id = str(order[-1])
        if last_id:
            node_data = meta.get(last_id)
            if isinstance(node_data, dict):
                r = str(node_data.get("result") or "").strip()
                if r:
                    return _append_artifact_download_links_to_reply(_sanitize_reply_text(r), meta)

    messages: List[Any] = result.get("messages") or []
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "") != "assistant":
            continue
        content = str(m.get("content") or "").strip()
        if content:
            return _append_artifact_download_links_to_reply(_sanitize_reply_text(content), meta)

    return _append_artifact_download_links_to_reply("（本轮无有效输出。）", meta)


def _collect_artifact_download_links(metadata: Dict[str, Any]) -> List[Tuple[str, str]]:
    """从工作流 metadata 各节点中收集 offer_artifact_download 注册的下载项。"""
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    meta = metadata or {}
    for k, v in meta.items():
        if str(k).startswith("__") or not isinstance(v, dict):
            continue
        inner = v.get("metadata")
        if not isinstance(inner, dict):
            continue
        tm = inner.get("tool_metadata")
        if not isinstance(tm, dict):
            continue
        tok = tm.get("download_token")
        if not tok:
            continue
        ts = str(tok)
        if ts in seen:
            continue
        seen.add(ts)
        rel = str(tm.get("relative_url") or f"/api/download/artifact?token={ts}")
        fn = str(tm.get("download_filename") or "download")
        out.append((fn, rel))
    return out


def _append_artifact_download_links_to_reply(text: str, metadata: Dict[str, Any]) -> str:
    """在终局回复末尾附加 Markdown 下载列表（与工具输出互补，防止 LLM 省略链接）。"""
    links = _collect_artifact_download_links(metadata)
    if not links:
        return text or ""
    block_lines = ["", "---", "**附件下载**", ""]
    for fn, url in links:
        block_lines.append(f"* [{fn}]({url})")
    block = "\n".join(block_lines)
    base = (text or "").rstrip()
    if not base:
        return block.strip()
    return base + block


class TeXAgentWebUI(TeXAgentCLI):
    """Web 模式：交互节点不阻塞 input()，改为返回说明性占位；支持左侧组装的 ``__web__`` 工作流。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web_workflow: Optional[Dict[str, Any]] = copy.deepcopy(DEFAULT_WEB_WORKFLOW)

    def _build_app_for_workflow(self, workflow_name: Optional[str]) -> Any:
        """在 workflow_name == ``__web__`` 时用内存图 JSON，否则走注册表文件。"""
        from workflow.graph_builder import build_app_from_workflow

        target = workflow_name or self.DEFAULT_WORKFLOW
        if target == "__web__":
            if not self.web_workflow or not isinstance(self.web_workflow.get("nodes"), list):
                raise ValueError("自定义工作流未初始化")
            if not self.web_workflow.get("nodes"):
                raise ValueError("自定义工作流没有节点，请在左侧添加并「保存到服务器」")
            return build_app_from_workflow(
                workflow_name="web_custom",
                config_dict=self.web_workflow,
                context_manager=self.context,
                persona_memory=self.persona_memory,
                runtime_memory=self.context,
                human_input_provider=self._human_input_provider,
                execution_mode="task",
            )
        return super()._build_app_for_workflow(workflow_name)

    def _human_input_provider(
        self, prompt: str, schema: Dict[str, Any], rules: Dict[str, Any]
    ) -> Any:
        _ = rules
        options: List[Any] = []
        if isinstance(schema, dict):
            options = schema.get("options") or []
        if isinstance(options, list) and options:
            return str(options[0])
        return (
            "[Web UI] 当前在网页中无法同步填写节点表单。请改在输入框继续说明需求。\n"
            f"节点提示：{prompt}"
        )


def _validate_workflow_dag_and_flow(
    node_ids: Set[str], edge_pairs: List[Tuple[str, str]]
) -> None:
    """
    保存时校验有向工作流图（仅无条件的 web 边）：

    1) 有且仅有一个入度为 0 的入口节点；
    2) 有且仅有一个出度为 0 的「最终输出」节点（与图构建器里汇点一致）；
    3) 无环（可拓扑排序覆盖全部节点）；
    4) 无孤立子图：自入口可正向到达所有节点、自出口反向可到达所有节点
       （即每个节点在「入口 → … → 出口」的连通的 DAG 中）；
    5) 无自环边 u→u；多节点时至少一条边（否则入/出度无法同时形成唯一入口/出口（除单点无边））。
    """
    n = len(node_ids)
    if n == 0:
        raise ValueError("工作流没有节点")
    for u, v in edge_pairs:
        if u not in node_ids or v not in node_ids:
            raise ValueError(f"边引用了不存在的节点: {u!r} → {v!r}")
    for u, v in edge_pairs:
        if u == v:
            raise ValueError("不允许自环边（节点指向自身）。")
    in_deg: Dict[str, int] = {i: 0 for i in node_ids}
    out_deg: Dict[str, int] = {i: 0 for i in node_ids}
    out_list: Dict[str, List[str]] = {i: [] for i in node_ids}
    pred: Dict[str, Set[str]] = {i: set() for i in node_ids}
    for u, v in edge_pairs:
        in_deg[v] += 1
        out_deg[u] += 1
        out_list[u].append(v)
        pred[v].add(u)

    sources = [i for i in node_ids if in_deg[i] == 0]
    sinks = [i for i in node_ids if out_deg[i] == 0]
    if len(sources) != 1:
        raise ValueError(
            "必须恰好有 1 个入口节点（入度为 0）；当前: "
            f"{len(sources)} 个: {sources if len(sources) <= 5 else sources[:5] + ['...']}"
        )
    if len(sinks) != 1:
        raise ValueError(
            "必须恰好有 1 个最终输出节点（出度为 0）；当前: "
            f"{len(sinks)} 个: {sinks if len(sinks) <= 5 else sinks[:5] + ['...']}"
        )
    entry, sink = sources[0], sinks[0]

    # Kahn：若无法处理完全部节点，则存在有向环
    in_copy = in_deg.copy()
    q: deque = deque(s for s in node_ids if in_copy[s] == 0)
    done = 0
    while q:
        u = q.popleft()
        done += 1
        for v in out_list[u]:
            in_copy[v] -= 1
            if in_copy[v] == 0:
                q.append(v)
    if done != n:
        raise ValueError("图中存在有向环，请调整边使流程为无环的 DAG。")

    # 自入口可达（正向 BFS/DFS）
    fwd: Set[str] = {entry}
    stack = [entry]
    while stack:
        u = stack.pop()
        for v in out_list[u]:
            if v not in fwd:
                fwd.add(v)
                stack.append(v)
    if fwd != node_ids:
        miss = list(node_ids - fwd)
        raise ValueError(
            "存在从入口无法到达的节点（与主图不连通）。无法到达: "
            f"{miss[:6]!r}{'...' if len(miss) > 6 else ''}"
        )

    # 能到达终局输出（在反向图上自 sink 出发）
    bwd: Set[str] = {sink}
    stack2 = [sink]
    while stack2:
        u = stack2.pop()
        for p in pred[u]:
            if p not in bwd:
                bwd.add(p)
                stack2.append(p)
    if bwd != node_ids:
        miss = list(node_ids - bwd)
        raise ValueError(
            "存在无法将结果送达「最终输出」的节点，或该节点处于死分支上。请检查: "
            f"{miss[:6]!r}{'...' if len(miss) > 6 else ''}"
        )
    if n >= 2 and not edge_pairs:
        raise ValueError("多个节点时至少需要一条有向边，且须形成单入口、单出口的 DAG。")


def _validate_workflow_dict(d: Dict[str, Any]) -> None:
    from workflow.workflow_parser import YAMLWorkflowParser

    p = YAMLWorkflowParser()
    try:
        nodes = p.parse_nodes(d)
        edges = p.parse_edges(d)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"工作流无法解析: {e}") from e
    if not nodes:
        raise ValueError("工作流必须至少有一个节点")
    ids = {n.node_id for n in nodes}
    edge_pairs: List[Tuple[str, str]] = []
    for e in d.get("edges") or []:
        if not isinstance(e, dict):
            continue
        a = e.get("from_node", e.get("from"))
        b = e.get("to_node", e.get("to"))
        if a is not None and b is not None:
            edge_pairs.append((str(a), str(b)))
    for ed in edges:
        if ed.from_node not in ids or ed.to_node not in ids:
            raise ValueError(
                f"边引用了不存在的节点: {ed.from_node!r} → {ed.to_node!r}"
            )
    # 以解析结果为准
    _validate_workflow_dag_and_flow(
        ids, [(e.from_node, e.to_node) for e in edges]
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    mode: Literal["task", "plan", "auto"] = "auto"
    workflow: Optional[str] = Field(
        None,
        description="工作流名称；填 __web__ 使用左侧自组工作流，否则为 registry 名称；省略时服务端用 DEFAULT_WORKFLOW（通常为 default）",
    )
    # 勾选后随请求发送 basename，服务端解析为 storage 下绝对路径并注入消息前部
    active_pdfs: Optional[List[str]] = Field(
        default=None, description="storage/pdfs 中已勾选文件名"
    )
    active_documents: Optional[List[str]] = Field(
        default=None, description="storage/documents 中已勾选文件名"
    )
    active_skills: Optional[List[str]] = Field(
        default=None, description="storage/skills 中已勾选文件名"
    )
    active_checklists: Optional[List[str]] = Field(
        default=None, description="storage/checklists 中已勾选文件名"
    )
    stream: bool = Field(
        default=False,
        description=(
            "为 true 时以 NDJSON 流式返回：plan 先发 plan_graph；"
            "task/auto 先发 workflow_graph；均推送 exec_nodes 与 result"
        ),
    )
    stream_plan: bool = Field(
        default=False,
        description="兼容旧字段：与 stream 任一为 true 则启用流式",
    )


class WorkflowDraftIn(BaseModel):
    """与 ``config/workflow/workflow_*.json`` 同构的 ``nodes`` / ``edges``。"""

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)


def _registry_workflow_draft_sync(name: str) -> WorkflowDraftIn:
    """从注册表加载工作流 nodes/edges（与 ``GET /api/workflow/graph`` 一致）。"""
    from workflow.workflow_parser import YAMLWorkflowParser
    from workflow.workflow_registry import WorkflowRegistry

    reg = WorkflowRegistry()
    names = reg.list_workflows()
    if name not in names:
        raise ValueError(
            f"未知工作流: {name!r}，可用: {', '.join(names[:12])}…"
        )
    cfg_path = reg.get_config_path(name)
    parser = YAMLWorkflowParser()
    config = parser.load_config(str(cfg_path))
    raw_nodes = config.get("nodes") or []
    raw_edges = config.get("edges") or []
    if not isinstance(raw_nodes, list):
        raw_nodes = []
    if not isinstance(raw_edges, list):
        raw_edges = []
    nodes: List[Dict[str, Any]] = []
    for item in raw_nodes:
        if isinstance(item, dict):
            nodes.append(dict(item))
    edges_out: List[Dict[str, Any]] = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        a = e.get("from_node", e.get("from"))
        b = e.get("to_node", e.get("to"))
        if a is None or b is None:
            continue
        edges_out.append(
            {
                "from_node": str(a),
                "to_node": str(b),
                "condition": e.get("condition"),
            }
        )
    return WorkflowDraftIn(nodes=nodes, edges=edges_out)


def _workflow_stream_graph_payload(
    cli: TeXAgentWebUI, workflow_name: Optional[str]
) -> Dict[str, Any]:
    """Task 流式首包：与当前执行所用工作流一致的图示 JSON。"""
    wn = workflow_name or cli.DEFAULT_WORKFLOW
    if wn == "__web__":
        wf = cli.web_workflow or {}
        if not wf.get("nodes"):
            raise ValueError(
                "自定义工作流没有节点，请在左侧添加并「保存到服务器」"
            )
        nodes = [dict(n) for n in (wf.get("nodes") or []) if isinstance(n, dict)]
        edges_out: List[Dict[str, Any]] = []
        for e in wf.get("edges") or []:
            if not isinstance(e, dict):
                continue
            a = e.get("from_node", e.get("from"))
            b = e.get("to_node", e.get("to"))
            if a is None or b is None:
                continue
            edges_out.append(
                {
                    "from_node": str(a),
                    "to_node": str(b),
                    "condition": e.get("condition"),
                }
            )
        return {"nodes": nodes, "edges": edges_out}
    draft = _registry_workflow_draft_sync(wn)
    return {"nodes": list(draft.nodes), "edges": list(draft.edges)}


class WorkflowRegistryOut(BaseModel):
    workflows: List[str]


class ToolItemOut(BaseModel):
    name: str
    description: str = ""


class ToolsListOut(BaseModel):
    tools: List[ToolItemOut]


class PdfFileItem(BaseModel):
    name: str
    size: int
    modified: str


class PdfListResponse(BaseModel):
    files: List[PdfFileItem]


class PdfUploadResponse(BaseModel):
    ok: bool = True
    name: str
    size: int


class ChatResponse(BaseModel):
    reply: str
    error: Optional[str] = None
    plan_graph: Optional[Dict[str, Any]] = Field(
        default=None,
        description="plan 模式下 PlanAgent 生成的运行时工作流（nodes/edges），供左侧图示",
    )


class RAGIndexResponse(BaseModel):
    ok: bool = True
    indexed_chunks: int
    total_chunks: int
    source: str = ""


class RAGTextIndexRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGHitOut(BaseModel):
    id: str = ""
    content: str
    source: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RAGQueryResponse(BaseModel):
    query: str
    top_k: int
    hits: List[RAGHitOut] = Field(default_factory=list)


class RAGRecordOut(BaseModel):
    id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    document: Optional[str] = None


class RAGRecordsResponse(BaseModel):
    items: List[RAGRecordOut] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 20
    has_next: bool = False


class RAGDeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 0
    total: int = 0
    record_id: Optional[str] = None


class BranchNodeOut(BaseModel):
    id: str
    parent: Optional[str] = None
    size: int = 0
    messages: int = 0


class BranchTreeOut(BaseModel):
    current: str
    nodes: List[BranchNodeOut]


class BranchCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    from_branch: str = Field("main", min_length=1, max_length=64)


class BranchSwitchBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class BranchHistoryMsgOut(BaseModel):
    role: str
    content: str


class BranchHistoryOut(BaseModel):
    branch: str
    messages: List[BranchHistoryMsgOut]

class WatchStartRequest(BaseModel):
    root: str = Field(..., description="LaTeX 项目根目录")
    main_tex: Optional[str] = Field(None, description="主文件相对路径")
    idle_polish_sec: Optional[float] = Field(2.0, description="空闲润色触发时间")

class WatchStartResponse(BaseModel):
    watch_id: str
    status: str

def _augment_message_with_active_files(message: str, body: "ChatRequest") -> str:
    """将各 storage 子目录中已勾选文件解析为绝对路径，置于用户消息前。"""
    parts: List[str] = []
    for label, cat, names in [
        ("PDF", file_storage.CATEGORY_PDFS, body.active_pdfs),
        ("文档", file_storage.CATEGORY_DOCUMENTS, body.active_documents),
        ("Skill", file_storage.CATEGORY_SKILLS, body.active_skills),
        ("Checklist", file_storage.CATEGORY_CHECKLISTS, body.active_checklists),
    ]:
        if not names:
            continue
        for raw in names:
            if not isinstance(raw, str):
                continue
            name = raw.strip()
            if not name:
                continue
            p = file_storage.abs_path_for_injection(cat, name)
            if p:
                parts.append(f"- [{label}] {p}")
    if not parts:
        return message
    return (
        "[Web UI 已勾选以下本地文件路径，需要时请用工具或根据路径引用。]\n"
        + "\n".join(parts)
        + "\n\n---\n\n"
        + message
    )


async def _upload_to_category(
    category: str, file: UploadFile
) -> "PdfUploadResponse":
    if category not in file_storage.ALL_CATEGORIES:
        raise HTTPException(status_code=400, detail="无效存储类别")
    fn = (file.filename or "").strip()
    if not file_storage.extension_allowed(category, fn):
        hint = file_storage.allowed_extensions_hint(category)
        raise HTTPException(
            status_code=400,
            detail=f"此类别不支持的扩展名。允许: {hint}",
        )
    try:
        dest = file_storage.unique_stored_path(category, fn or "file")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    total = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > file_storage.MAX_UPLOAD_BYTES:
                    try:
                        dest.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件过大，单文件上限 {file_storage.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return PdfUploadResponse(name=dest.name, size=total)


_BR_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")

_cli: Optional[TeXAgentWebUI] = None
_rag_pipeline: Optional[Any] = None

# 阶段 9：LaTeX 监视服务会话存储
_watch_sessions: Dict[str, WatchService] = {}


def get_cli() -> TeXAgentWebUI:
    global _cli
    if _cli is None:
        _cli = TeXAgentWebUI(use_branch=True)
    return _cli


def get_rag_pipeline() -> Any:
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.rag_pipeline import RAGPipeline

        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def _parse_rag_metadata_json(raw: str) -> Dict[str, Any]:
    txt = (raw or "").strip()
    if not txt:
        return {}
    try:
        obj = json.loads(txt)
    except json.JSONDecodeError as e:
        raise ValueError(f"metadata_json 不是合法 JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("metadata_json 必须是 JSON 对象")
    return obj


def _record_matches_metadata(
    metadata: Dict[str, Any], key: str, value: str
) -> bool:
    if not key:
        return True
    if key not in metadata:
        return False
    if not value:
        return True
    raw = metadata.get(key)
    if raw is None:
        return False
    return value.lower() in str(raw).lower()


async def _drain_worker_queue(out_q: queue.Queue) -> Tuple[str, Any]:
    """
    异步轮询工作线程队列。勿使用 to_thread.run_sync(queue.get)，否则 Ctrl+C 无法打断。
    """
    while True:
        try:
            return out_q.get_nowait()
        except queue.Empty:
            if is_run_cancelled():
                raise KeyboardInterrupt
            await asyncio.sleep(0.15)


@asynccontextmanager
async def _app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from ui.web.ide_launch import schedule_open_ide

    install_sigint_handler()
    # 默认用系统/Windows 打开；TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER=1 时再试 Simple（见 ide_launch）
    schedule_open_ide(1.0)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TeX Agent Web UI",
        version="0.1.0",
        lifespan=_app_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/conferences/deadlines")
    async def conferences_deadlines(
        fields: Optional[str] = Query(
            None,
            description="逗号分隔领域：cv,nlp,networking,ml 等；空=全部",
        ),
        include_past: bool = Query(False, description="是否包含已截止会议"),
    ) -> Dict[str, Any]:
        """顶会投稿日历（静态 JSON，非实时）。"""
        field_list: Optional[List[str]] = None
        if fields and fields.strip():
            field_list = [x.strip() for x in fields.split(",") if x.strip()]
        try:
            return list_deadlines(fields=field_list, include_past=include_past)
        except FileNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"日历配置 JSON 无效: {e}") from e

    # --- 阶段 9: LaTeX Watch API ---
    @app.post("/api/latex/watch", response_model=WatchStartResponse)
    async def start_latex_watch(body: WatchStartRequest) -> WatchStartResponse:
        import uuid
        root_path = Path(body.root).expanduser().resolve()
        if not root_path.is_dir():
            raise HTTPException(status_code=400, detail=f"目录不存在: {body.root}")
            
        # 检查是否已有同目录的 running session
        for wid, svc in _watch_sessions.items():
            if svc.root_path == root_path and svc.status == "running":
                return WatchStartResponse(watch_id=wid, status="already_running")
                
        watch_id = str(uuid.uuid4())
        service = WatchService(
            watch_id=watch_id,
            root=str(root_path),
            main_tex=body.main_tex,
            idle_polish_sec=body.idle_polish_sec
        )
        service.start()
        _watch_sessions[watch_id] = service
        return WatchStartResponse(watch_id=watch_id, status="started")

    @app.get("/api/latex/watch/{watch_id}", response_model=WatchSnapshot)
    async def get_latex_watch_status(watch_id: str) -> WatchSnapshot:
        if watch_id not in _watch_sessions:
            raise HTTPException(status_code=404, detail="Watch session not found")
        return _watch_sessions[watch_id].get_snapshot()

    @app.get("/api/latex/watch/{watch_id}/snapshot", response_model=WatchSnapshot)
    async def get_latex_watch_snapshot(watch_id: str) -> WatchSnapshot:
        if watch_id not in _watch_sessions:
            raise HTTPException(status_code=404, detail="Watch session not found")
        return _watch_sessions[watch_id].get_snapshot()

    @app.delete("/api/latex/watch/{watch_id}")
    async def stop_latex_watch(watch_id: str):
        if watch_id not in _watch_sessions:
            raise HTTPException(status_code=404, detail="Watch session not found")
        _watch_sessions[watch_id].stop()
        del _watch_sessions[watch_id]
        return {"status": "stopped", "watch_id": watch_id}
    # -------------------------------

    @app.post("/api/rag/index-text", response_model=RAGIndexResponse)
    async def rag_index_text_ep(body: RAGTextIndexRequest) -> RAGIndexResponse:
        def _work() -> Tuple[int, int, str]:
            p = get_rag_pipeline()
            src = (body.source or "").strip()
            md = body.metadata if isinstance(body.metadata, dict) else {}
            indexed = p.index_text(body.text, source=src, metadata=md)
            return indexed, p.document_count(), src

        try:
            indexed, total, src = await anyio.to_thread.run_sync(_work)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return RAGIndexResponse(
            indexed_chunks=indexed,
            total_chunks=total,
            source=src,
        )

    @app.post("/api/rag/index-file", response_model=RAGIndexResponse)
    async def rag_index_file_ep(
        file: UploadFile = File(..., description="待注入 RAG 的文本文件"),
        source: str = Form("", description="可选 source 覆盖值"),
        metadata_json: str = Form("{}", description="可选 metadata JSON 对象"),
    ) -> RAGIndexResponse:
        try:
            metadata = _parse_rag_metadata_json(metadata_json)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="上传文件为空")
        if len(raw) > file_storage.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大，单文件上限 {file_storage.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail="仅支持 UTF-8 文本文件上传到 RAG",
            ) from e
        src = (source or "").strip() or str(file.filename or "upload_text")

        def _work() -> Tuple[int, int]:
            p = get_rag_pipeline()
            indexed = p.index_text(text, source=src, metadata=metadata)
            return indexed, p.document_count()

        try:
            indexed, total = await anyio.to_thread.run_sync(_work)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return RAGIndexResponse(
            indexed_chunks=indexed,
            total_chunks=total,
            source=src,
        )

    @app.post("/api/rag/query", response_model=RAGQueryResponse)
    async def rag_query_ep(body: RAGQueryRequest) -> RAGQueryResponse:
        q = body.query.strip()
        if not q:
            raise HTTPException(status_code=400, detail="query 不能为空")

        def _work() -> List[Any]:
            p = get_rag_pipeline()
            return p.retrieve_documents(q, k=body.top_k)

        try:
            docs = await anyio.to_thread.run_sync(_work)
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        hits = [
            RAGHitOut(
                id=str(((getattr(d, "metadata", {}) or {}).get("_id") or "")),
                content=str(getattr(d, "content", "") or ""),
                source=str(getattr(d, "source", "") or ""),
                score=float(getattr(d, "score", 0.0) or 0.0),
                metadata=(getattr(d, "metadata", {}) or {}),
            )
            for d in docs
        ]
        return RAGQueryResponse(query=q, top_k=body.top_k, hits=hits)

    @app.get("/api/rag/records", response_model=RAGRecordsResponse)
    async def rag_records_ep(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=50),
        metadata_key: str = Query("", description="metadata 字段名"),
        metadata_value: str = Query("", description="metadata 字段值（可留空）"),
        include_document: bool = Query(False, description="是否附带文档片段文本"),
    ) -> RAGRecordsResponse:
        from rag.store_listing import MAX_LIST_PAGE_SIZE, StoreField

        key = (metadata_key or "").strip()
        val = (metadata_value or "").strip()
        fetch_fields = StoreField.DEFAULT
        if include_document:
            fetch_fields |= StoreField.DOCUMENT

        def _work() -> RAGRecordsResponse:
            p = get_rag_pipeline()
            if not key:
                scan_offset = offset
                total = 0
                raw_items: List[Any] = []
                while len(raw_items) < limit:
                    page = p.list_stored_page(
                        offset=scan_offset,
                        limit=min(limit - len(raw_items), MAX_LIST_PAGE_SIZE),
                        fetch_fields=fetch_fields,
                    )
                    total = int(page.total)
                    raw_items.extend(page.items)
                    if not page.has_next:
                        break
                    if len(page.items) <= 0:
                        break
                    scan_offset += len(page.items)
                items = [
                    RAGRecordOut(
                        id=str(getattr(rec, "id", "") or ""),
                        metadata=(getattr(rec, "metadata", {}) or {}),
                        document=(
                            str(getattr(rec, "document", "") or "")
                            if include_document
                            else None
                        ),
                    )
                    for rec in raw_items
                ]
                return RAGRecordsResponse(
                    items=items,
                    total=total,
                    offset=int(offset),
                    limit=int(limit),
                    has_next=(offset + len(items) < total),
                )

            scan_offset = 0
            filtered: List[RAGRecordOut] = []
            while True:
                page = p.list_stored_page(
                    offset=scan_offset,
                    limit=MAX_LIST_PAGE_SIZE,
                    fetch_fields=fetch_fields,
                )
                for rec in page.items:
                    md = getattr(rec, "metadata", {}) or {}
                    if not isinstance(md, dict):
                        md = {}
                    if _record_matches_metadata(md, key, val):
                        filtered.append(
                            RAGRecordOut(
                                id=str(getattr(rec, "id", "") or ""),
                                metadata=md,
                                document=(
                                    str(getattr(rec, "document", "") or "")
                                    if include_document
                                    else None
                                ),
                            )
                        )
                if not page.has_next:
                    break
                if len(page.items) <= 0:
                    break
                scan_offset += len(page.items)

            total = len(filtered)
            sliced = filtered[offset : offset + limit]
            return RAGRecordsResponse(
                items=sliced,
                total=total,
                offset=int(offset),
                limit=int(limit),
                has_next=(offset + len(sliced) < total),
            )

        try:
            return await anyio.to_thread.run_sync(_work)
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.delete("/api/rag/records/{record_id}", response_model=RAGDeleteResponse)
    async def rag_delete_record_ep(record_id: str) -> RAGDeleteResponse:
        rid = (record_id or "").strip()
        if not rid:
            raise HTTPException(status_code=400, detail="record_id 不能为空")

        def _work() -> Tuple[int, int]:
            p = get_rag_pipeline()
            deleted = p.delete_chunks_by_ids([rid])
            return deleted, p.document_count()

        try:
            deleted, total = await anyio.to_thread.run_sync(_work)
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return RAGDeleteResponse(deleted=deleted, total=total, record_id=rid)

    @app.delete("/api/rag/records/by-source", response_model=RAGDeleteResponse)
    @app.delete("/api/rag/records/delete-by-source", response_model=RAGDeleteResponse)
    async def rag_delete_by_source_ep(
        source: str = Query(..., min_length=1, description="按 metadata.source 删除"),
    ) -> RAGDeleteResponse:
        src = source.strip()
        if not src:
            raise HTTPException(status_code=400, detail="source 不能为空")

        def _work() -> Tuple[int, int]:
            p = get_rag_pipeline()
            deleted = p.delete_by_source(src)
            return deleted, p.document_count()

        try:
            deleted, total = await anyio.to_thread.run_sync(_work)
        except ImportError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return RAGDeleteResponse(deleted=deleted, total=total, record_id=src)

    @app.get("/api/branches", response_model=BranchTreeOut)
    async def get_branches() -> BranchTreeOut:
        cli = get_cli()
        raw = await anyio.to_thread.run_sync(cli.get_branch_tree_for_api)
        return BranchTreeOut(
            current=str(raw.get("current") or "main"),
            nodes=[
                BranchNodeOut(
                    id=str(n["id"]),
                    parent=(None if n.get("parent") in (None, "") else str(n["parent"])),
                    size=int(n.get("size") or 0),
                    messages=int(n.get("messages") or 0),
                )
                for n in (raw.get("nodes") or [])
            ],
        )

    @app.post("/api/branches", response_model=BranchTreeOut, status_code=201)
    async def create_branch_ep(body: BranchCreateBody) -> BranchTreeOut:
        if not _BR_NAME.match(body.name) or not _BR_NAME.match(body.from_branch):
            raise HTTPException(
                status_code=400,
                detail="分支名仅允许字母、数字、下划线与连字符",
            )
        if body.name == "main":
            raise HTTPException(status_code=400, detail="不能覆盖主分支名称")

        def _work() -> bool:
            return get_cli().create_branch(
                body.name.strip(), body.from_branch.strip()
            )

        ok = await anyio.to_thread.run_sync(_work)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail="创建失败：名称已存在或父分支无效",
            )
        return await get_branches()

    @app.post("/api/branches/switch", response_model=BranchTreeOut)
    async def switch_branch_ep(body: BranchSwitchBody) -> BranchTreeOut:
        if not _BR_NAME.match(body.name):
            raise HTTPException(
                status_code=400,
                detail="分支名仅允许字母、数字、下划线与连字符",
            )

        def _work() -> bool:
            return get_cli().switch_branch(body.name.strip())

        ok = await anyio.to_thread.run_sync(_work)
        if not ok:
            raise HTTPException(status_code=404, detail="无此分支")
        return await get_branches()

    @app.get("/api/branches/history", response_model=BranchHistoryOut)
    async def get_branch_history_ep(
        branch: Optional[str] = Query(
            None,
            description="分支名；省略时为当前活动分支",
        ),
    ) -> BranchHistoryOut:
        """返回指定分支的服务端对话历史，供切换分支后刷新聊天区。"""

        def _work() -> BranchHistoryOut:
            cli = get_cli()
            name_q = (branch or cli.current_branch or "main").strip()
            if not _BR_NAME.match(name_q):
                raise ValueError("分支名无效")
            raw = cli.get_branch_chat_history_for_api(name_q)
            msgs = raw.get("messages") or []
            return BranchHistoryOut(
                branch=str(raw.get("branch") or name_q),
                messages=[
                    BranchHistoryMsgOut(
                        role=str(m.get("role") or "user"),
                        content=str(m.get("content") or ""),
                    )
                    for m in msgs
                    if isinstance(m, dict)
                ],
            )

        try:
            return await anyio.to_thread.run_sync(_work)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/api/workflow/draft", response_model=WorkflowDraftIn)
    async def get_workflow_draft() -> WorkflowDraftIn:
        cli = get_cli()
        wf = cli.web_workflow or {}
        return WorkflowDraftIn(
            nodes=list(wf.get("nodes") or []),
            edges=list(wf.get("edges") or []),
        )

    @app.put("/api/workflow/draft", response_model=WorkflowDraftIn)
    async def put_workflow_draft(body: WorkflowDraftIn) -> WorkflowDraftIn:
        def _work() -> WorkflowDraftIn:
            d: Dict[str, Any] = {
                "nodes": [dict(n) for n in body.nodes],
                "edges": [dict(n) for n in body.edges],
            }
            _validate_workflow_dict(d)
            get_cli().web_workflow = d
            return WorkflowDraftIn(nodes=d["nodes"], edges=d["edges"])

        try:
            return await anyio.to_thread.run_sync(_work)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/workflow/registry", response_model=WorkflowRegistryOut)
    async def get_workflow_registry() -> WorkflowRegistryOut:
        from workflow.workflow_registry import WorkflowRegistry

        return WorkflowRegistryOut(workflows=WorkflowRegistry().list_workflows())

    @app.get("/api/workflow/graph", response_model=WorkflowDraftIn)
    async def get_workflow_graph(name: str = Query(..., description="注册表中的工作流名称，如 default")) -> WorkflowDraftIn:
        """返回注册表工作流的 nodes/edges，供前端只读图示（与 plan/task 模式无关）。"""

        try:
            return await anyio.to_thread.run_sync(
                lambda: _registry_workflow_draft_sync(name)
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/tools/list", response_model=ToolsListOut)
    async def list_registered_tools() -> ToolsListOut:
        """供前端工作流编排下拉：与 tools/tool_list 一致。"""

        def _work() -> ToolsListOut:
            from tools.tool_list import tool_list

            return ToolsListOut(
                tools=[
                    ToolItemOut(
                        name=str(getattr(t, "name", "") or ""),
                        description=str(getattr(t, "description", "") or ""),
                    )
                    for t in tool_list
                    if getattr(t, "name", None)
                ]
            )

        return await anyio.to_thread.run_sync(_work)

    @app.get("/api/storage/pdfs", response_model=PdfListResponse)
    async def list_pdfs_ep() -> PdfListResponse:
        def _load() -> List[Dict[str, Any]]:
            return file_storage.list_files(file_storage.CATEGORY_PDFS)

        raw = await anyio.to_thread.run_sync(_load)
        return PdfListResponse(
            files=[PdfFileItem(**x) for x in raw],
        )

    @app.get("/api/storage/documents", response_model=PdfListResponse)
    async def list_documents_ep() -> PdfListResponse:
        def _load() -> List[Dict[str, Any]]:
            return file_storage.list_files(file_storage.CATEGORY_DOCUMENTS)

        raw = await anyio.to_thread.run_sync(_load)
        return PdfListResponse(
            files=[PdfFileItem(**x) for x in raw],
        )

    @app.get("/api/storage/skills", response_model=PdfListResponse)
    async def list_skills_ep() -> PdfListResponse:
        def _load() -> List[Dict[str, Any]]:
            return file_storage.list_files(file_storage.CATEGORY_SKILLS)

        raw = await anyio.to_thread.run_sync(_load)
        return PdfListResponse(
            files=[PdfFileItem(**x) for x in raw],
        )

    @app.get("/api/storage/checklists", response_model=PdfListResponse)
    async def list_checklists_ep() -> PdfListResponse:
        def _load() -> List[Dict[str, Any]]:
            return file_storage.list_files(file_storage.CATEGORY_CHECKLISTS)

        raw = await anyio.to_thread.run_sync(_load)
        return PdfListResponse(
            files=[PdfFileItem(**x) for x in raw],
        )

    @app.post("/api/storage/pdfs", response_model=PdfUploadResponse)
    async def upload_pdf_ep(
        file: UploadFile = File(..., description="PDF 文件"),
    ) -> PdfUploadResponse:
        return await _upload_to_category(file_storage.CATEGORY_PDFS, file)

    @app.post("/api/storage/documents", response_model=PdfUploadResponse)
    async def upload_document_ep(
        file: UploadFile = File(..., description="其他文档（见允许的扩展名）"),
    ) -> PdfUploadResponse:
        return await _upload_to_category(file_storage.CATEGORY_DOCUMENTS, file)

    @app.post("/api/storage/skills", response_model=PdfUploadResponse)
    async def upload_skill_ep(
        file: UploadFile = File(..., description="Skill 文件"),
    ) -> PdfUploadResponse:
        return await _upload_to_category(file_storage.CATEGORY_SKILLS, file)

    @app.post("/api/storage/checklists", response_model=PdfUploadResponse)
    async def upload_checklist_ep(
        file: UploadFile = File(..., description="Checklist 文件"),
    ) -> PdfUploadResponse:
        return await _upload_to_category(file_storage.CATEGORY_CHECKLISTS, file)

    @app.get("/api/storage/pdfs/{filename}/raw")
    async def download_pdf_ep(filename: str) -> FileResponse:
        p = file_storage.resolve_safe_path(file_storage.CATEGORY_PDFS, filename)
        if p is None:
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(
            p,
            media_type=file_storage.media_type_for_path(p),
            filename=p.name,
        )

    @app.get("/api/storage/documents/{filename}/raw")
    async def download_document_ep(filename: str) -> FileResponse:
        p = file_storage.resolve_safe_path(file_storage.CATEGORY_DOCUMENTS, filename)
        if p is None:
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(
            p,
            media_type=file_storage.media_type_for_path(p),
            filename=p.name,
        )

    @app.get("/api/storage/skills/{filename}/raw")
    async def download_skill_ep(filename: str) -> FileResponse:
        p = file_storage.resolve_safe_path(file_storage.CATEGORY_SKILLS, filename)
        if p is None:
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(
            p,
            media_type=file_storage.media_type_for_path(p),
            filename=p.name,
        )

    @app.get("/api/storage/checklists/{filename}/raw")
    async def download_checklist_ep(filename: str) -> FileResponse:
        p = file_storage.resolve_safe_path(file_storage.CATEGORY_CHECKLISTS, filename)
        if p is None:
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(
            p,
            media_type=file_storage.media_type_for_path(p),
            filename=p.name,
        )

    @app.get("/api/download/artifact")
    async def download_artifact_ep(
        token: str = Query(..., min_length=8, description="offer_artifact_download 工具返回的 download_token"),
    ) -> FileResponse:
        """工作流生成的文件经令牌登记后，供浏览器本地下载。"""

        def _resolve_path() -> Optional[Path]:
            from utils.web_artifact_registry import get_file_path

            raw = get_file_path(token)
            if not raw:
                return None
            return Path(raw)

        p = await anyio.to_thread.run_sync(_resolve_path)
        if p is None:
            raise HTTPException(status_code=404, detail="下载链接无效或已过期")
        if not p.is_file():
            raise HTTPException(status_code=404, detail="文件已不存在")
        return FileResponse(
            str(p),
            media_type=file_storage.media_type_for_path(p),
            filename=p.name,
            content_disposition_type="attachment",
        )

    @app.post("/api/chat")
    async def chat(body: ChatRequest):
        cli = get_cli()
        user_text = _augment_message_with_active_files(
            body.message.strip(), body
        )

        use_stream = body.stream or body.stream_plan

        if body.mode == "plan" and use_stream:

            async def ndjson_plan_stream() -> AsyncIterator[bytes]:
                clear_run_cancel()

                def _line(obj: Dict[str, Any]) -> bytes:
                    return (
                        json.dumps(obj, ensure_ascii=False) + "\n"
                    ).encode("utf-8")

                try:
                    nodes, edges, app = await anyio.to_thread.run_sync(
                        lambda: cli.build_plan_graph_and_app(user_text)
                    )
                except ValueError as e:
                    yield _line({"type": "error", "detail": str(e)})
                    return
                except Exception as e:  # noqa: BLE001
                    yield _line({"type": "error", "detail": str(e)})
                    return

                try:
                    plan_graph = _serialize_plan_graph_for_ui(nodes, edges)
                except Exception as e:  # noqa: BLE001
                    yield _line({"type": "error", "detail": str(e)})
                    return

                yield _line({"type": "plan_graph", "plan_graph": plan_graph})

                out_q: queue.Queue = queue.Queue()

                def _run_plan_execute() -> None:
                    def _emit_batch(node_ids: List[str]) -> None:
                        out_q.put(("exec", list(node_ids)))

                    try:
                        res = cli._execute_with_app(
                            user_text,
                            app,
                            "plan_dynamic",
                            use_loading=False,
                            on_graph_progress=_emit_batch,
                        )
                        out_q.put(("done", res))
                    except KeyboardInterrupt as ex:
                        out_q.put(("err", ex))
                    except Exception as ex:  # noqa: BLE001
                        out_q.put(("err", ex))

                threading.Thread(target=_run_plan_execute, daemon=True).start()
                result: Optional[Dict[str, Any]] = None
                try:
                    while True:
                        kind, payload = await _drain_worker_queue(out_q)
                        if kind == "exec":
                            yield _line({"type": "exec_nodes", "node_ids": payload})
                        elif kind == "done":
                            result = payload
                            break
                        elif kind == "err":
                            yield _line(
                                {
                                    "type": "result",
                                    "reply": "",
                                    "error": str(payload),
                                }
                            )
                            return
                        else:
                            break
                except KeyboardInterrupt:
                    yield _line(
                        {
                            "type": "result",
                            "reply": "",
                            "error": "已中断（Ctrl+C）",
                        }
                    )
                    return

                if not isinstance(result, dict):
                    yield _line(
                        {
                            "type": "result",
                            "reply": "",
                            "error": "执行未返回有效结果",
                        }
                    )
                    return

                try:
                    result.setdefault("metadata", {})["__plan_graph__"] = (
                        plan_graph
                    )
                except Exception:
                    pass
                err = result.get("error")
                text = _format_reply_from_result(result)
                yield _line(
                    {
                        "type": "result",
                        "reply": text,
                        "error": str(err) if err else None,
                    }
                )

            return StreamingResponse(
                ndjson_plan_stream(),
                media_type="application/x-ndjson",
            )

        if body.mode in ("task", "auto") and use_stream:

            async def ndjson_task_stream() -> AsyncIterator[bytes]:
                clear_run_cancel()

                def _line(obj: Dict[str, Any]) -> bytes:
                    return (
                        json.dumps(obj, ensure_ascii=False) + "\n"
                    ).encode("utf-8")

                if body.mode == "auto":
                    from config.auto_config import AUTO_WORKFLOW_LABEL

                    workflow_label = AUTO_WORKFLOW_LABEL
                else:
                    workflow_label = body.workflow or cli.DEFAULT_WORKFLOW

                try:
                    if body.mode == "auto":
                        def _build_auto_bundle():
                            n, e, a = cli.build_auto_graph_and_app(user_text)
                            return n, e, a

                        nodes, edges, app = await anyio.to_thread.run_sync(
                            _build_auto_bundle
                        )
                        graph_payload = _serialize_plan_graph_for_ui(nodes, edges)
                    else:
                        graph_payload = _workflow_stream_graph_payload(
                            cli, body.workflow
                        )
                        app = await anyio.to_thread.run_sync(
                            lambda: cli._build_app_for_workflow(body.workflow)
                        )
                except ValueError as e:
                    yield _line({"type": "error", "detail": str(e)})
                    return
                except Exception as e:  # noqa: BLE001
                    yield _line({"type": "error", "detail": str(e)})
                    return

                yield _line(
                    {
                        "type": "workflow_graph",
                        "workflow_graph": graph_payload,
                    }
                )

                out_q: queue.Queue = queue.Queue()

                def _run_task_execute() -> None:
                    def _emit_batch(node_ids: List[str]) -> None:
                        out_q.put(("exec", list(node_ids)))

                    try:
                        res = cli._execute_with_app(
                            user_text,
                            app,
                            workflow_label,
                            use_loading=False,
                            on_graph_progress=_emit_batch,
                        )
                        out_q.put(("done", res))
                    except KeyboardInterrupt as ex:
                        out_q.put(("err", ex))
                    except Exception as ex:  # noqa: BLE001
                        out_q.put(("err", ex))

                threading.Thread(
                    target=_run_task_execute, daemon=True
                ).start()
                result: Optional[Dict[str, Any]] = None
                try:
                    while True:
                        kind, payload = await _drain_worker_queue(out_q)
                        if kind == "exec":
                            yield _line({"type": "exec_nodes", "node_ids": payload})
                        elif kind == "done":
                            result = payload
                            break
                        elif kind == "err":
                            yield _line(
                                {
                                    "type": "result",
                                    "reply": "",
                                    "error": str(payload),
                                }
                            )
                            return
                        else:
                            break
                except KeyboardInterrupt:
                    yield _line(
                        {
                            "type": "result",
                            "reply": "",
                            "error": "已中断（Ctrl+C）",
                        }
                    )
                    return

                if not isinstance(result, dict):
                    yield _line(
                        {
                            "type": "result",
                            "reply": "",
                            "error": "执行未返回有效结果",
                        }
                    )
                    return

                err = result.get("error")
                text = _format_reply_from_result(result)
                yield _line(
                    {
                        "type": "result",
                        "reply": text,
                        "error": str(err) if err else None,
                    }
                )

            return StreamingResponse(
                ndjson_task_stream(),
                media_type="application/x-ndjson",
            )

        def run_sync() -> Dict[str, Any]:
            if body.mode == "plan":
                return cli.run_plan_task(user_text, use_loading=False)
            if body.mode == "auto":
                return cli.run_auto_task(user_text, use_loading=False)
            return cli.run_task(
                user_text,
                workflow_name=body.workflow,
                use_loading=False,
            )

        clear_run_cancel()
        try:
            result = await anyio.to_thread.run_sync(run_sync)
        except KeyboardInterrupt:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        err = result.get("error")
        text = _format_reply_from_result(result)
        plan_graph = None
        if body.mode == "plan":
            plan_graph = (result.get("metadata") or {}).get("__plan_graph__")
        elif body.mode == "auto":
            plan_graph = (result.get("metadata") or {}).get("__auto_graph__")
        return ChatResponse(
            reply=text,
            error=str(err) if err else None,
            plan_graph=plan_graph,
        )

    if STATIC_DIR.is_dir():
        index_path = STATIC_DIR / "index.html"

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            """禁用 index 强缓存，避免用户看不到新加的顶栏入口。"""
            if not index_path.is_file():
                raise HTTPException(status_code=404, detail="index.html not found")
            return FileResponse(
                index_path,
                media_type="text/html; charset=utf-8",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                },
            )

        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("TEX_AGENT_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("TEX_AGENT_WEB_PORT", "8765"))
    install_sigint_handler()
    uvicorn.run(
        "ui.web.server:app",
        host=host,
        port=port,
        reload=False,
        timeout_graceful_shutdown=3,
    )


if __name__ == "__main__":
    main()
