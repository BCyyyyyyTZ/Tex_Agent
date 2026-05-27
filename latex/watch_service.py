"""
LaTeX 目录监视服务（阶段 8）。
"""
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
from latex.suggestion import (
    parse_llm_suggestions_from_agent_result,
    parse_polish_suggestion_json,
)
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
        self.idle_polish_sec = (
            idle_polish_sec
            if idle_polish_sec is not None
            else settings.latex_watch_idle_polish_sec
        )
        self.diagnose_debounce_ms = (
            diagnose_debounce_ms
            if diagnose_debounce_ms is not None
            else settings.latex_watch_diagnose_debounce_ms
        )
        self.enable_latexmk = (
            enable_latexmk
            if enable_latexmk is not None
            else settings.latex_watch_enable_latexmk
        )
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
        self._stop_timer = threading.Event()
        self._timer_thread: Optional[threading.Thread] = None

        self._last_change_time = 0.0
        self._last_diagnose_time = 0.0
        self._last_polish_time = 0.0
        self._active_file: Optional[Path] = None
        self._diag_running = False
        self._polish_running = False

    def start(self):
        if self.status == "running":
            return
        self.status = "running"
        self._stop_timer.clear()

        self._observer = Observer()
        handler = LatexWatchHandler(self)
        self._observer.schedule(handler, str(self.root_path), recursive=True)
        self._observer.start()

        self._timer_thread = threading.Thread(
            target=self._timer_loop,
            name=f"latex-watch-timer-{self.watch_id}",
            daemon=True,
        )
        self._timer_thread.start()

        # 启动后立即跑一次诊断，避免用户必须等第一次保存
        self._schedule_diagnostics()

    def stop(self):
        if self.status == "stopped":
            return
        self.status = "stopped"
        self._stop_timer.set()

        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=2.0)
        self._timer_thread = None

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

        self._emit_snapshot()

    def on_file_changed(self, path: Path):
        with self._lock:
            self._last_change_time = time.time()
            self._active_file = path

    def _timer_loop(self):
        while self.status == "running" and not self._stop_timer.is_set():
            time.sleep(0.1)
            now = time.time()

            with self._lock:
                last_change = self._last_change_time
                last_diag = self._last_diagnose_time
                last_polish = self._last_polish_time
                active_file = self._active_file

            if last_change > 0 and last_change > last_diag:
                if (now - last_change) * 1000 >= self.diagnose_debounce_ms:
                    with self._lock:
                        self._last_diagnose_time = now
                    self._schedule_diagnostics()

            if last_change > 0 and last_change > last_polish:
                if (now - last_change) >= self.idle_polish_sec:
                    with self._lock:
                        self._last_polish_time = now
                    if active_file is not None:
                        self._schedule_idle_polish(active_file)

    def _schedule_diagnostics(self):
        if self._diag_running:
            return
        threading.Thread(
            target=self._run_diagnostics,
            name=f"latex-watch-diag-{self.watch_id}",
            daemon=True,
        ).start()

    def _schedule_idle_polish(self, active_file: Path):
        if self._polish_running:
            return
        threading.Thread(
            target=self._run_idle_polish,
            args=(active_file,),
            name=f"latex-watch-polish-{self.watch_id}",
            daemon=True,
        ).start()

    def _run_diagnostics(self):
        self._diag_running = True
        try:
            rel_files = resolve_target_files(self.root_path, main_tex=self.main_tex)
            chk_res = run_chktex(self.root_path, rel_files)

            latexmk_issues = []
            if self.enable_latexmk and self.main_tex:
                lmk_res = run_latexmk(self.root_path, self.main_tex, mode="fast")
                latexmk_issues = lmk_res.issues

            merged = merge_issues(chk_res.issues, latexmk_issues)

            error_issues = [i for i in merged if i.severity == Severity.ERROR]
            suggestions: List[Suggestion] = []
            if error_issues:
                slices = slice_issues(error_issues, root=self.root_path)
                batch = build_fix_batch(merged, slices)
                if batch["task_count"] > 0:
                    agent = SimpleAgent(name="fix_agent", temperature=0.2)
                    msg = WorkflowMessage(role="user", content=batch["prompt_bundle"])
                    res = agent.run(msg)
                    issues_by_id = {i.id: i for i in error_issues}
                    suggestions = parse_llm_suggestions_from_agent_result(
                        res.content, issues_by_id=issues_by_id
                    )

            with self._lock:
                self.project_version += 1
                self.issues = merged
                self.suggestions = suggestions
                self.last_event_at = time.time()

            self._emit_event(
                "diagnostics_updated",
                {
                    "issues": [i.model_dump(mode="json") for i in merged],
                    "suggestions": [s.model_dump(mode="json") for s in suggestions],
                    "chktex_warnings": list(chk_res.warnings),
                },
            )
        except Exception as e:
            self.error_message = str(e)
            self._emit_event(
                "error",
                {
                    "stage": "diagnostics",
                    "error": "诊断流程执行失败",
                    "detail": str(e),
                },
            )
        finally:
            self._diag_running = False

    def _run_idle_polish(self, active_file: Path):
        self._polish_running = True
        try:
            content = active_file.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            # 优先取文件末尾片段（用户通常在文末编辑），最多 80 行
            tail = lines[-80:] if len(lines) > 80 else lines
            snippet = "\n".join(tail)
            if not snippet.strip():
                return

            rel_path = normalize_rel_path(str(active_file.relative_to(self.root_path)))
            prompt = build_polish_prompt(snippet, rel_path)

            agent = SimpleAgent(name="polish_agent", temperature=0.7)
            msg = WorkflowMessage(role="user", content=prompt)
            res = agent.run(msg)

            sug = parse_polish_suggestion_json(res.content, default_file=rel_path)
            if sug is None:
                self.error_message = (
                    "润色未产出可用建议（LLM 返回为空或无法解析 JSON）。"
                )
                return
            sug.source = IssueSource.LLM_POLISH
            with self._lock:
                self.project_version += 1
                self.polish_suggestions = [sug]
                self.last_event_at = time.time()

            self._emit_event(
                "polish_suggestions_updated",
                {"polish_suggestions": [sug.model_dump(mode="json")]},
            )
        except Exception as e:
            self.error_message = f"Polish error: {e}"
            self._emit_event(
                "error",
                {
                    "stage": "polish",
                    "error": "润色流程执行失败",
                    "detail": str(e),
                },
            )
        finally:
            self._polish_running = False

    def _emit_snapshot(self):
        self._emit_event("snapshot", self.get_snapshot().model_dump(mode="json"))

    def _emit_event(self, event_type: str, payload: dict):
        if self.on_event:
            ev = WatchEvent(
                event_type=event_type,
                watch_id=self.watch_id,
                project_version=self.project_version,
                timestamp=time.time(),
                payload=payload,
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
                error_message=self.error_message,
            )
