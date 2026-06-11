"""
LaTeX 目录监视服务（阶段 8）。
"""
import re
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
from latex.project_index import build_project_index
from latex.refs_index import iter_main_closure_files
from agents.simple_agent_new import SimpleAgent
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
        self._compile_running = False
        self._compile_state = "idle"
        self._compile_finished_at = 0.0
        self.error_signature = ""
        self.error_changed = False
        self._dismissed_issue_keys: set[str] = set()

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
        self._schedule_diagnostics(run_static=True, run_compile=self.enable_latexmk and bool(self.main_tex))

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

    def _schedule_diagnostics(self, *, run_static: bool = True, run_compile: bool = False) -> bool:
        if self._diag_running:
            return False
        threading.Thread(
            target=self._run_diagnostics,
            kwargs={"run_static": run_static, "run_compile": run_compile},
            name=f"latex-watch-diag-{self.watch_id}",
            daemon=True,
        ).start()
        return True

    def _schedule_idle_polish(self, active_file: Path):
        if self._polish_running:
            return
        threading.Thread(
            target=self._run_idle_polish,
            args=(active_file,),
            name=f"latex-watch-polish-{self.watch_id}",
            daemon=True,
        ).start()

    def _run_diagnostics(self, *, run_static: bool = True, run_compile: bool = False):
        self._diag_running = True
        try:
            chk_warnings: List[str] = []
            static_issues: List[DiagnosticIssue] = []
            if run_static:
                rel_files = self._resolve_chktex_files()
                chk_res = run_chktex(self.root_path, rel_files)
                static_issues = chk_res.issues
                chk_warnings = list(chk_res.warnings)

            latexmk_issues = []
            if run_compile and self.enable_latexmk and self.main_tex:
                self._set_compile_state("running")
                try:
                    lmk_res = run_latexmk(self.root_path, self.main_tex, mode="fast")
                    latexmk_issues = lmk_res.issues
                    self._set_compile_state("done")
                finally:
                    with self._lock:
                        self._compile_running = False

            merged = merge_issues(static_issues, latexmk_issues)
            merged = self._confirm_issue_positions(merged)

            error_issues = [i for i in merged if i.severity == Severity.ERROR]
            next_error_signature = self._build_error_signature(error_issues)
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
                prev_error_signature = self.error_signature
                self.project_version += 1
                self.issues = merged
                self.suggestions = suggestions
                self.error_signature = next_error_signature
                self.error_changed = next_error_signature != prev_error_signature
                self.last_event_at = time.time()

            self._emit_event(
                "diagnostics_updated",
                {
                    "issues": [i.model_dump(mode="json") for i in merged],
                    "suggestions": [s.model_dump(mode="json") for s in suggestions],
                    "chktex_warnings": chk_warnings,
                    "error_signature": next_error_signature,
                },
            )
        except Exception as e:
            self.error_message = str(e)
            if run_compile:
                self._set_compile_state("failed")
            self._emit_event(
                "error",
                {
                    "stage": "diagnostics",
                    "error": "诊断流程执行失败",
                    "detail": str(e),
                },
            )
        finally:
            with self._lock:
                self._compile_running = False
            self._diag_running = False

    def _resolve_chktex_files(self) -> List[str]:
        """
        计算本轮静态检查目标：
        - 有 main_tex 时：优先 main 闭包（含子 tex）；
        - 无 main_tex 时：检查 root 下全部 tex。
        """
        try:
            index = build_project_index(
                self.root_path,
                main_tex=self.main_tex,
                enrich=False,
            )
        except Exception:
            return [normalize_rel_path(self.main_tex)] if self.main_tex else []

        if index.main_tex:
            rel_files = iter_main_closure_files(index)
        else:
            rel_files = sorted(index.files.keys())

        if rel_files:
            return rel_files
        return [normalize_rel_path(self.main_tex)] if self.main_tex else []

    def request_compile_check(self) -> bool:
        """手动触发一次编译检查（不重复静态检查）。"""
        return self._schedule_diagnostics(run_static=False, run_compile=True)

    def dismiss_suggestion(self, suggestion: dict[str, Any]) -> None:
        """
        记录用户忽略的建议，后续同一行同一报错不再进入 LLM 并隐藏对应卡片。
        """
        issue_id = str(suggestion.get("issue_id") or "")
        message = str(suggestion.get("message") or "").strip()
        file_path = normalize_rel_path(str(suggestion.get("file") or ""))
        line = int((suggestion.get("range", {}).get("start", {}) or {}).get("line", 0)) + 1
        key = ""
        with self._lock:
            if issue_id:
                matched = next((i for i in self.issues if i.id == issue_id), None)
                if matched is not None:
                    key = self._issue_dismiss_key(matched.file, matched.line, matched.message)
            if not key and file_path and message:
                key = self._issue_dismiss_key(file_path, line, message)
            if key:
                self._dismissed_issue_keys.add(key)

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
            errors_by_file = self._group_suggestion_counts(self.suggestions)
            polish_by_file = self._group_suggestion_counts(self.polish_suggestions)
            return WatchSnapshot(
                watch_id=self.watch_id,
                root=str(self.root_path),
                main_tex=self.main_tex,
                status=self.status,
                project_version=self.project_version,
                issues=self.issues,
                suggestions=self.suggestions,
                polish_suggestions=self.polish_suggestions,
                error_signature=self.error_signature,
                error_changed=self.error_changed,
                compile_running=self._compile_running,
                compile_state=self._compile_state,
                compile_finished_at=self._compile_finished_at,
                errors_by_file=errors_by_file,
                polish_by_file=polish_by_file,
                last_event_at=self.last_event_at,
                error_message=self.error_message,
            )

    @staticmethod
    def _build_error_signature(issues: List[DiagnosticIssue]) -> str:
        """
        生成与 issue 顺序无关的 error 签名，供 Ghost UI 判断是否需要刷新卡片。
        """
        if not issues:
            return ""
        parts = []
        for issue in issues:
            file_path = normalize_rel_path(issue.file)
            parts.append(
                f"{file_path}:{issue.line}:{issue.column}:{issue.code}:{issue.message}"
            )
        return "|".join(sorted(parts))

    @staticmethod
    def _group_suggestion_counts(suggestions: List[Suggestion]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for suggestion in suggestions:
            rel = normalize_rel_path(suggestion.file)
            if not rel:
                continue
            counts[rel] = counts.get(rel, 0) + 1
        return counts

    @staticmethod
    def _issue_dismiss_key(file: str, line: int, message: str) -> str:
        return f"{normalize_rel_path(file)}:{max(1, int(line))}:{(message or '').strip()}"

    def _set_compile_state(self, state: str) -> None:
        with self._lock:
            self._compile_state = state
            self._compile_running = state == "running"
            if state in ("done", "failed"):
                self._compile_finished_at = time.time()

    def _confirm_issue_positions(self, issues: List[DiagnosticIssue]) -> List[DiagnosticIssue]:
        """
        在出卡前做一次轻量行号确认，缓解 log/解析导致的 ±1~2 行偏移。
        """
        cache: dict[str, list[str]] = {}
        out: List[DiagnosticIssue] = []
        for issue in issues:
            if issue.severity != Severity.ERROR:
                out.append(issue)
                continue
            rel = normalize_rel_path(issue.file)
            if not rel:
                out.append(issue)
                continue
            lines = cache.get(rel)
            if lines is None:
                path = self.root_path / rel
                if not path.is_file():
                    out.append(issue)
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                cache[rel] = lines
            if not lines:
                out.append(issue)
                continue

            cur = max(1, min(issue.line, len(lines)))
            anchor = self._extract_anchor_token(issue.message)
            new_line = cur
            if anchor:
                cur_line = lines[cur - 1] if 1 <= cur <= len(lines) else ""
                if anchor not in cur_line:
                    for cand in self._nearby_line_candidates(cur, len(lines), window=5):
                        if anchor in lines[cand - 1]:
                            new_line = cand
                            break
            elif not lines[cur - 1].strip():
                for cand in self._nearby_line_candidates(cur, len(lines), window=5):
                    if lines[cand - 1].strip():
                        new_line = cand
                        break

            if new_line != issue.line:
                issue.line = new_line
                issue.end_line = new_line
            out.append(issue)
        return out

    @staticmethod
    def _nearby_line_candidates(center: int, max_line: int, window: int = 2) -> List[int]:
        candidates: List[int] = []
        for delta in range(0, window + 1):
            for sign in (-1, 1):
                if delta == 0 and sign == 1:
                    continue
                line = center + (delta * sign)
                if 1 <= line <= max_line and line not in candidates:
                    candidates.append(line)
        return candidates

    @staticmethod
    def _extract_anchor_token(message: str) -> str:
        msg = message or ""
        command = re.search(r"(\\[A-Za-z@]+)", msg)
        if command:
            return command.group(1)
        return ""
