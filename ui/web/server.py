"""
TeX Agent Web UI：FastAPI 服务 + 静态页面（Cursor 风格聊天 + Markdown）。

启动：
  uvicorn ui.web.server:app --host 127.0.0.1 --port 8765
或：
  python -m ui.web.server
"""
from __future__ import annotations

import copy
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from collections import deque
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Set, Tuple

import anyio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.agent_cli import TeXAgentCLI
from ui.web import file_storage

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


def _format_reply_from_result(result: Dict[str, Any]) -> str:
    """
    从工作流 state 中只取「最后一处节点产物」的文本，原样给前端做 Markdown 渲染。

    优先顺序与 workflow/state 一致：
    1) state.output — 由末端交付节点写入的终端输出
    2) metadata[__execution_order__] 中最后一个 node_id 的 result（NodeOutput）
    3) 退化为最后一条含内容的 assistant 消息（极少情况下 output / 元数据未写）
    """
    err = result.get("error")
    if err:
        return f"**执行出错**\n\n```\n{err}\n```"

    out = str(result.get("output") or "").strip()
    if out:
        return out

    meta: Dict[str, Any] = result.get("metadata") or {}
    order = meta.get("__execution_order__")
    if isinstance(order, list) and order:
        last_id = str(order[-1])
        if last_id:
            node_data = meta.get(last_id)
            if isinstance(node_data, dict):
                r = str(node_data.get("result") or "").strip()
                if r:
                    return r

    messages: List[Any] = result.get("messages") or []
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "") != "assistant":
            continue
        content = str(m.get("content") or "").strip()
        if content:
            return content

    return "（本轮无有效输出。）"


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
    mode: Literal["task", "plan"] = "task"
    workflow: Optional[str] = Field(
        None,
        description="工作流名称；填 __web__ 使用左侧自组工作流，否则为 registry 中的名称，默认 default",
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


class WorkflowDraftIn(BaseModel):
    """与 ``config/workflow_*.json`` 同构的 ``nodes`` / ``edges``。"""

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)


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


def get_cli() -> TeXAgentWebUI:
    global _cli
    if _cli is None:
        _cli = TeXAgentWebUI(use_branch=True)
    return _cli


@asynccontextmanager
async def _app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from ui.web.ide_launch import schedule_open_ide

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

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest) -> ChatResponse:
        cli = get_cli()
        user_text = _augment_message_with_active_files(
            body.message.strip(), body
        )

        def run_sync() -> Dict[str, Any]:
            if body.mode == "plan":
                return cli.run_plan_task(user_text, use_loading=False)
            return cli.run_task(
                user_text,
                workflow_name=body.workflow,
                use_loading=False,
            )

        try:
            result = await anyio.to_thread.run_sync(run_sync)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        err = result.get("error")
        text = _format_reply_from_result(result)
        return ChatResponse(reply=text, error=str(err) if err else None)

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("TEX_AGENT_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("TEX_AGENT_WEB_PORT", "8765"))
    uvicorn.run("ui.web.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
