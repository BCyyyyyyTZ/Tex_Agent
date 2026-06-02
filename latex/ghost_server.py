"""
独立幽灵窗口 HTTP 服务（阶段 10）：浏览器内行间建议卡片，不依赖 VS Code 扩展。
"""
from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from latex.apply_edit import apply_suggestion_to_file
from latex.paths import normalize_rel_path
from latex.watch_service import WatchService

_GHOST_DIR = Path(__file__).resolve().parents[1] / "ui" / "ghost"
_service: Optional[WatchService] = None


class ApplyBody(BaseModel):
    suggestion: Dict[str, Any] = Field(default_factory=dict)


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
            written = apply_suggestion_to_file(svc.root_path, body.suggestion)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        rel = normalize_rel_path(str(body.suggestion.get("file", "")))
        svc.on_file_changed(written)
        return {"ok": True, "file": rel}

    if _GHOST_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_GHOST_DIR)), name="ghost_static")

    return app


def run_ghost_server(
    *,
    root: str,
    main_tex: Optional[str] = None,
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

    _service = WatchService(
        watch_id="ghost_ui",
        root=str(root_path),
        main_tex=main_tex,
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
    print("[Ghost UI] 在浏览器中查看行间建议；Ctrl+C 停止。")

    uvicorn.run(app, host=host, port=port, log_level="info")
