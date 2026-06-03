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
from latex.chktex_runner import run_chktex, resolve_target_files
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
            next_error_signature = self._build_error_signature(error_issues)

            with self._lock:
                prev_error_signature = self.error_signature
                prev_suggestions = list(self.suggestions)
            error_changed = next_error_signature != prev_error_signature

            suggestions: List[Suggestion]
            if not error_changed:
                suggestions = prev_suggestions
            elif error_issues:
                suggestions = []
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
                    suggestions = self._enrich_fix_suggestions(
                        suggestions, issues_by_id=issues_by_id
                    )
            else:
                suggestions = []

            with self._lock:
                self.project_version += 1
                self.issues = merged
                self.suggestions = suggestions
                self.error_signature = next_error_signature
                self.error_changed = error_changed
                self.last_event_at = time.time()

            self._emit_event(
                "diagnostics_updated",
                {
                    "issues": [i.model_dump(mode="json") for i in merged],
                    "suggestions": [s.model_dump(mode="json") for s in suggestions],
                    "chktex_warnings": list(chk_res.warnings),
                    "error_signature": next_error_signature,
                    "error_changed": error_changed,
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
