"""
LaTeX 目录监视服务（阶段 8）。
"""
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from config.settings import settings
from latex.constants import IssueSource, Severity
from latex.models import DiagnosticIssue, Suggestion
from latex.watch_events import WatchSnapshot, WatchEvent
from latex.chktex_runner import run_chktex, resolve_target_files
from latex.latexmk_runner import run_latexmk
from latex.issues import merge_issues
from latex.slice import slice_issues
from latex.fix_batch import build_fix_batch
from latex.polish_prompt import build_polish_prompt
from agents.simple_agent import SimpleAgent
from core.message import WorkflowMessage
from latex.suggestion import parse_llm_suggestions_from_agent_result, parse_llm_suggestion_json
from latex.paths import normalize_rel_path


class LatexWatchHandler(FileSystemEventHandler):
    def __init__(self, service: "WatchService"):
        self.service = service

    def on_modified(self, event: Any):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix in (".tex", ".bib"):
            self.service.on_file_changed(path)


class WatchService:
    """
    后台监视服务。
    管理防抖、增量诊断、空闲润色触发。
    """
    def __init__(
        self,
        watch_id: str,
        root: str,
        main_tex: Optional[str] = None,
        idle_polish_sec: Optional[float] = None,
        diagnose_debounce_ms: Optional[int] = None,
        enable_latexmk: Optional[bool] = None,
        on_event: Optional[Callable[[WatchEvent], None]] = None,
    ):
        self.watch_id = watch_id
        self.root_path = Path(root).expanduser().resolve()
        self.main_tex = main_tex
        self.idle_polish_sec = idle_polish_sec if idle_polish_sec is not None else settings.latex_watch_idle_polish_sec
        self.diagnose_debounce_ms = diagnose_debounce_ms if diagnose_debounce_ms is not None else settings.latex_watch_diagnose_debounce_ms
        self.enable_latexmk = enable_latexmk if enable_latexmk is not None else settings.latex_watch_enable_latexmk
        self.on_event = on_event

        self.project_version = 0
        self.status = "stopped"
        
        self.issues: List[DiagnosticIssue] = []
        self.suggestions: List[Suggestion] = []
        self.polish_suggestions: List[Suggestion] = []
        self.last_event_at: float = time.time()
        self.error_message = ""
        
        self._observer: Optional[Observer] = None
        self._lock = threading.Lock()
        
        self._last_change_time = 0.0
        self._last_diagnose_time = 0.0
        self._last_polish_time = 0.0
        self._active_file: Optional[Path] = None
        
        self._timer_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self):
        if self.status == "running":
            return
        self.status = "running"
        self._observer = Observer()
        handler = LatexWatchHandler(self)
        self._observer.schedule(handler, str(self.root_path), recursive=True)
        self._observer.start()
        
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
        self._timer_task = self._loop.create_task(self._timer_loop())
        self._emit_snapshot()

    def stop(self):
        if self.status == "stopped":
            return
        self.status = "stopped"
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        self._emit_snapshot()

    def on_file_changed(self, path: Path):
        with self._lock:
            self._last_change_time = time.time()
            self._active_file = path

    async def _timer_loop(self):
        while self.status == "running":
            await asyncio.sleep(0.1)
            now = time.time()
            
            with self._lock:
                last_change = self._last_change_time
                last_diag = self._last_diagnose_time
                last_polish = self._last_polish_time
                active_file = self._active_file
                
            # 触发诊断防抖
            if last_change > last_diag and (now - last_change) * 1000 >= self.diagnose_debounce_ms:
                with self._lock:
                    self._last_diagnose_time = now
                self._run_diagnostics()
                
            # 触发空闲润色
            if last_change > last_polish and (now - last_change) >= self.idle_polish_sec:
                with self._lock:
                    self._last_polish_time = now
                if active_file:
                    self._run_idle_polish(active_file)

    def _run_diagnostics(self):
        try:
            rel_files = resolve_target_files(self.root_path, main_tex=self.main_tex)
            chk_res = run_chktex(self.root_path, rel_files)
            
            latexmk_issues = []
            if self.enable_latexmk and self.main_tex:
                lmk_res = run_latexmk(self.root_path, self.main_tex, mode="fast")
                latexmk_issues = lmk_res.issues
                
            merged = merge_issues(chk_res.issues, latexmk_issues)
            
            # 跑 LLM 修复
            error_issues = [i for i in merged if i.severity == Severity.ERROR]
            suggestions = []
            if error_issues:
                slices = slice_issues(self.root_path, error_issues)
                batch = build_fix_batch(merged, slices)
                if batch["task_count"] > 0:
                    agent = SimpleAgent(name="fix_agent", temperature=0.2)
                    msg = WorkflowMessage(role="user", content=batch["prompt_bundle"])
                    res = agent.run(msg)
                    issues_by_id = {i.id: i for i in error_issues}
                    suggestions = parse_llm_suggestions_from_agent_result(res.content, issues_by_id=issues_by_id)
            
            with self._lock:
                self.project_version += 1
                self.issues = merged
                self.suggestions = suggestions
                self.last_event_at = time.time()
                
            self._emit_event("diagnostics_updated", {
                "issues": [i.model_dump(mode="json") for i in merged],
                "suggestions": [s.model_dump(mode="json") for s in suggestions]
            })
        except Exception as e:
            self.error_message = str(e)
            self._emit_event("error", {"error": str(e)})

    def _run_idle_polish(self, active_file: Path):
        try:
            # 简单实现：读取活跃文件前 50 行进行润色（MVP）
            content = active_file.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            snippet = "\n".join(lines[:50])
            if not snippet.strip():
                return
                
            rel_path = normalize_rel_path(str(active_file.relative_to(self.root_path)))
            prompt = build_polish_prompt(snippet, rel_path)
            
            agent = SimpleAgent(name="polish_agent", temperature=0.7)
            msg = WorkflowMessage(role="user", content=prompt)
            res = agent.run(msg)
            
            sug = parse_llm_suggestion_json(res.content, default_file=rel_path)
            if sug:
                sug.source = IssueSource.LLM_POLISH
                with self._lock:
                    self.project_version += 1
                    self.polish_suggestions = [sug]
                    self.last_event_at = time.time()
                    
                self._emit_event("polish_suggestions_updated", {
                    "polish_suggestions": [sug.model_dump(mode="json")]
                })
        except Exception as e:
            self.error_message = f"Polish error: {e}"
            self._emit_event("error", {"error": self.error_message})

    def _emit_snapshot(self):
        self._emit_event("snapshot", self.get_snapshot().model_dump(mode="json"))

    def _emit_event(self, event_type: str, payload: dict):
        if self.on_event:
            ev = WatchEvent(
                event_type=event_type,
                watch_id=self.watch_id,
                project_version=self.project_version,
                timestamp=time.time(),
                payload=payload
            )
            self.on_event(ev)

    def get_snapshot(self) -> WatchSnapshot:
        with self._lock:
            return WatchSnapshot(
                watch_id=self.watch_id,
                root=str(self.root_path),
                main_tex=self.main_tex,
                status=self.status,
                project_version=self.project_version,
                issues=self.issues,
                suggestions=self.suggestions,
                polish_suggestions=self.polish_suggestions,
                last_event_at=self.last_event_at,
                error_message=self.error_message
            )
