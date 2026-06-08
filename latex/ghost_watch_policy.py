"""
Ghost UI 专用监视策略（PR-10a）。

目标：
1) 目录变更后 1s 静默再诊断；
2) 默认关闭自动空闲润色；
3) 若 error 集合未变化，沿用旧 suggestions，减少 UI 重绘抖动。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from config.settings import settings
from agents.simple_agent import SimpleAgent
from core.message import WorkflowMessage
from latex.constants import Severity
from latex.fix_batch import build_fix_batch
from latex.slice import slice_issues
from latex.suggestion import parse_llm_suggestions_from_agent_result
from latex.watch_service import WatchService
from latex.chktex_runner import run_chktex
from latex.issues import merge_issues
from latex.latexmk_runner import run_latexmk
from latex.models import DiagnosticIssue, Suggestion


class GhostWatchPolicy(WatchService):
    """Ghost 页面的 watch 策略，兼容 WatchService 接口。"""

    def __init__(
        self,
        *,
        watch_id: str,
        root: str,
        main_tex: Optional[str] = None,
        quiet_sec: Optional[float] = None,
        auto_polish: Optional[bool] = None,
        idle_polish_sec: Optional[float] = None,
        diagnose_debounce_ms: Optional[int] = None,
        enable_latexmk: Optional[bool] = None,
        on_event=None,
    ):
        self.quiet_sec = (
            quiet_sec if quiet_sec is not None else settings.latex_ghost_quiet_sec
        )
        debounce_ms = (
            diagnose_debounce_ms
            if diagnose_debounce_ms is not None
            else max(100, int(self.quiet_sec * 1000))
        )
        self.auto_polish = (
            auto_polish
            if auto_polish is not None
            else settings.latex_ghost_auto_polish
        )
        super().__init__(
            watch_id=watch_id,
            root=root,
            main_tex=main_tex,
            idle_polish_sec=idle_polish_sec,
            diagnose_debounce_ms=debounce_ms,
            enable_latexmk=enable_latexmk,
            on_event=on_event,
        )

    def _schedule_idle_polish(self, active_file: Path):
        if not self.auto_polish:
            return
        super()._schedule_idle_polish(active_file)

    def start(self):
        if self.status == "running":
            return
        self.status = "running"
        self._stop_timer.clear()

        from watchdog.observers import Observer
        from latex.watch_service import LatexWatchHandler

        self._observer = Observer()
        handler = LatexWatchHandler(self)
        self._observer.schedule(handler, str(self.root_path), recursive=True)
        self._observer.start()

        import threading

        self._timer_thread = threading.Thread(
            target=self._timer_loop,
            name=f"latex-watch-timer-{self.watch_id}",
            daemon=True,
        )
        self._timer_thread.start()

        # Ghost 启动时只做一次编译检查；静态检查等待用户改动后触发。
        if self.enable_latexmk and self.main_tex:
            self._schedule_diagnostics(run_static=False, run_compile=True)

    def _timer_loop(self):
        # 与基类一致，但 Ghost 场景改为“仅静态检查”；编译由用户手动触发。
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
                    self._schedule_diagnostics(run_static=True, run_compile=False)

            if last_change > 0 and last_change > last_polish:
                if (now - last_change) >= self.idle_polish_sec:
                    with self._lock:
                        self._last_polish_time = now
                    if active_file is not None:
                        self._schedule_idle_polish(active_file)

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
            with self._lock:
                dismissed_keys = set(self._dismissed_issue_keys)
            eligible_error_issues = [
                i
                for i in error_issues
                if self._issue_dismiss_key(i.file, i.line, i.message) not in dismissed_keys
            ]
            next_error_signature = self._build_error_signature(error_issues)

            with self._lock:
                prev_error_signature = self.error_signature
                prev_suggestions = list(self.suggestions)
                prev_issues = list(self.issues)
            error_changed = next_error_signature != prev_error_signature

            suggestions: List[Suggestion]
            if not error_changed:
                suggestions = prev_suggestions
            elif eligible_error_issues:
                suggestions = []
                slices = slice_issues(eligible_error_issues, root=self.root_path)
                batch = build_fix_batch(merged, slices)
                if batch["task_count"] > 0:
                    agent = SimpleAgent(name="fix_agent", temperature=0.2)
                    msg = WorkflowMessage(role="user", content=batch["prompt_bundle"])
                    res = agent.run(msg)
                    issues_by_id = {i.id: i for i in eligible_error_issues}
                    suggestions = parse_llm_suggestions_from_agent_result(
                        res.content, issues_by_id=issues_by_id
                    )
                    suggestions = self._enrich_fix_suggestions(
                        suggestions, issues_by_id=issues_by_id
                    )
            else:
                suggestions = []

            changed = (
                [i.model_dump(mode="json") for i in prev_issues]
                != [i.model_dump(mode="json") for i in merged]
                or [s.model_dump(mode="json") for s in prev_suggestions]
                != [s.model_dump(mode="json") for s in suggestions]
                or next_error_signature != prev_error_signature
            )
            with self._lock:
                if changed:
                    self.project_version += 1
                    self.issues = merged
                    self.suggestions = suggestions
                    self.last_event_at = time.time()
                self.error_signature = next_error_signature
                self.error_changed = error_changed

            self._emit_event(
                "diagnostics_updated",
                {
                    "issues": [i.model_dump(mode="json") for i in merged],
                    "suggestions": [s.model_dump(mode="json") for s in suggestions],
                    "chktex_warnings": chk_warnings,
                    "error_signature": next_error_signature,
                    "error_changed": error_changed,
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

    @staticmethod
    def _enrich_fix_suggestions(
        suggestions: List[Suggestion],
        *,
        issues_by_id: dict[str, DiagnosticIssue],
    ) -> List[Suggestion]:
        """
        对 LLM 返回做兜底补全，保证 PR-10b 卡片字段可展示。
        """
        out: List[Suggestion] = []
        for sug in suggestions:
            issue = issues_by_id.get(sug.issue_id or "")
            if issue is not None:
                if not sug.message.strip():
                    sug.message = issue.message
                if (
                    sug.range.start.line == 0
                    and sug.range.start.character == 0
                    and sug.range.end.line == 0
                    and sug.range.end.character == 0
                    and issue.line > 0
                ):
                    line0 = max(0, issue.line - 1)
                    col0 = max(0, issue.column)
                    sug.range.start.line = line0
                    sug.range.start.character = col0
                    sug.range.end.line = line0
                    sug.range.end.character = max(col0 + 1, issue.end_column or col0 + 1)
                if not sug.cause_zh.strip():
                    sug.cause_zh = sug.rationale_zh
                if not sug.advice_zh.strip():
                    sug.advice_zh = "将定位范围替换为建议文本，消除当前错误。"
            out.append(sug)
        return out
