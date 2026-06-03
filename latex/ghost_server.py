"""
独立幽灵窗口 HTTP 服务（阶段 10）：浏览器内行间建议卡片，不依赖 VS Code 扩展。
"""
from __future__ import annotations

import json
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from latex.apply_compare import apply_suggestion_compare_to_file
from latex.apply_edit import apply_suggestion_to_file
from latex.constants import IssueSource, Severity
from latex.ghost_polish_prompt import build_ghost_polish_prompt
from latex.ghost_watch_policy import GhostWatchPolicy
from latex.models import Position, Suggestion, TextRange
from latex.paths import normalize_rel_path
from latex.suggestion import _extract_json_candidates
from latex.watch_service import WatchService
from agents.simple_agent import SimpleAgent
from core.message import WorkflowMessage

_GHOST_DIR = Path(__file__).resolve().parents[1] / "ui" / "ghost"
_service: Optional[WatchService] = None


class ApplyBody(BaseModel):
    suggestion: Dict[str, Any] = Field(default_factory=dict)
    mode: Literal["replace", "compare"] = "replace"


class PolishBody(BaseModel):
    query: str = ""
    target_file: str = ""
    context_file: str = ""


def get_service() -> WatchService:
    if _service is None or _service.status != "running":
        raise HTTPException(status_code=503, detail="监视服务未启动")
    return _service


def create_ghost_app() -> FastAPI:
    app = FastAPI(title="TeX Agent Ghost UI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_GHOST_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok", "mode": "ghost"}

    @app.get("/api/snapshot")
    async def snapshot() -> Dict[str, Any]:
        svc = get_service()
        snap = svc.get_snapshot()
        return snap.model_dump(mode="json")

    @app.get("/api/file")
    async def read_file(path: str) -> Dict[str, Any]:
        svc = get_service()
        rel = normalize_rel_path(path)
        target = svc.root_path / rel
        if not target.is_file():
            raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return {
            "file": rel,
            "line_count": len(lines),
            "lines": lines,
        }

    @app.post("/api/apply")
    async def apply_suggestion(body: ApplyBody) -> Dict[str, Any]:
        svc = get_service()
        if not body.suggestion:
            raise HTTPException(status_code=400, detail="缺少 suggestion")
        try:
            if body.mode == "compare":
                written = apply_suggestion_compare_to_file(svc.root_path, body.suggestion)
            else:
                written = apply_suggestion_to_file(svc.root_path, body.suggestion)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        rel = normalize_rel_path(str(body.suggestion.get("file", "")))
        svc.on_file_changed(written)
        return {"ok": True, "file": rel, "mode": body.mode}

    @app.post("/api/ghost/polish")
    async def polish(body: PolishBody) -> Dict[str, Any]:
        svc = get_service()
        query = (body.query or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query 不能为空")
        target_rel = normalize_rel_path(body.target_file or "")
        if not target_rel:
            raise HTTPException(status_code=400, detail="target_file 不能为空")
        context_rel = normalize_rel_path(body.context_file or target_rel)

        target_path = svc.root_path / target_rel
        context_path = svc.root_path / context_rel
        if not target_path.is_file():
            raise HTTPException(status_code=404, detail=f"文件不存在: {target_rel}")
        if not context_path.is_file():
            raise HTTPException(status_code=404, detail=f"文件不存在: {context_rel}")

        target_text = target_path.read_text(encoding="utf-8", errors="replace")
        context_text = context_path.read_text(encoding="utf-8", errors="replace")

        prompt = build_ghost_polish_prompt(
            query=query,
            target_file=target_rel,
            target_text=target_text,
            context_file=context_rel,
            context_text=context_text,
        )
        agent = SimpleAgent(name="ghost_polish_agent", temperature=0.4)
        msg = WorkflowMessage(role="user", content=prompt)
        res = agent.run(msg)
        sug = _build_polish_suggestion_from_agent_result(
            raw=res.content,
            target_file=target_rel,
            target_text=target_text,
        )
        if sug is None:
            raise HTTPException(status_code=400, detail="润色结果无法解析")

        with svc._lock:  # noqa: SLF001 - Ghost 与 WatchService 共享状态
            svc.project_version += 1
            existing = [
                s
                for s in svc.polish_suggestions
                if not (
                    s.file == sug.file
                    and s.range.start.line == sug.range.start.line
                    and s.range.start.character == sug.range.start.character
                )
            ]
            existing.append(sug)
            svc.polish_suggestions = existing[-20:]
            svc.last_event_at = time.time()

        svc._emit_event(  # noqa: SLF001 - 复用既有事件通道
            "polish_suggestions_updated",
            {"polish_suggestions": [s.model_dump(mode="json") for s in svc.polish_suggestions]},
        )
        return {"ok": True, "suggestion": sug.model_dump(mode="json")}

    if _GHOST_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_GHOST_DIR)), name="ghost_static")

    return app


def _build_polish_suggestion_from_agent_result(
    *,
    raw: Any,
    target_file: str,
    target_text: str,
) -> Optional[Suggestion]:
    data = _coerce_polish_payload(raw)
    if not data:
        return None

    original_text = str(data.get("original_text", "") or "")
    polished_text = str(data.get("polished_text", "") or "")
    problem_zh = str(data.get("problem_zh", "") or "")
    advice_zh = str(data.get("advice_zh", data.get("advice", "")) or "")
    if not polished_text and not problem_zh:
        return None

    rng = _locate_text_range(target_text, original_text)
    return Suggestion(
        request_id=str(uuid.uuid4()),
        file=target_file,
        range=rng,
        severity=Severity.INFO,
        source=IssueSource.LLM_POLISH,
        message=problem_zh,
        replacement=polished_text,
        rationale_zh=problem_zh,
        cause_zh=problem_zh,
        advice_zh=advice_zh,
        issue_id=None,
    )


def _coerce_polish_payload(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return None
    for candidate in (text, *_extract_json_candidates(text)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _locate_text_range(file_text: str, original_text: str) -> TextRange:
    if not file_text:
        return TextRange(start=Position(line=0, character=0), end=Position(line=0, character=0))
    if not original_text:
        return TextRange(start=Position(line=0, character=0), end=Position(line=0, character=0))

    start = file_text.find(original_text)
    if start < 0:
        return TextRange(start=Position(line=0, character=0), end=Position(line=0, character=0))

    end = start + len(original_text)
    return TextRange(
        start=_offset_to_position(file_text, start),
        end=_offset_to_position(file_text, end),
    )


def _offset_to_position(text: str, offset: int) -> Position:
    offset = max(0, min(offset, len(text)))
    before = text[:offset]
    line = before.count("\n")
    last_nl = before.rfind("\n")
    if last_nl < 0:
        char = len(before)
    else:
        char = len(before) - last_nl - 1
    return Position(line=line, character=char)


def run_ghost_server(
    *,
    root: str,
    main_tex: Optional[str] = None,
    quiet_sec: float = 1.0,
    auto_polish: bool = False,
    idle_polish_sec: float = 2.0,
    host: str = "127.0.0.1",
    port: int = 8771,
    open_browser: bool = True,
) -> None:
    """启动 watch + 幽灵窗口 HTTP 服务（阻塞）。"""
    global _service

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise FileNotFoundError(f"目录不存在: {root}")

    _service = GhostWatchPolicy(
        watch_id="ghost_ui",
        root=str(root_path),
        main_tex=main_tex,
        quiet_sec=quiet_sec,
        auto_polish=auto_polish,
        idle_polish_sec=idle_polish_sec,
    )
    _service.start()

    import uvicorn

    app = create_ghost_app()
    url = f"http://{host}:{port}/"
    if open_browser:
        webbrowser.open(url)

    print(f"[Ghost UI] {url}")
    print(f"[Ghost UI] 监视目录: {root_path}")
    if main_tex:
        print(f"[Ghost UI] main_tex: {main_tex}")
    print(
        f"[Ghost UI] 监视策略: quiet={quiet_sec:.2f}s, auto_polish={'on' if auto_polish else 'off'}"
    )
    print("[Ghost UI] 在浏览器中查看行间建议；Ctrl+C 停止。")

    uvicorn.run(app, host=host, port=port, log_level="info")
