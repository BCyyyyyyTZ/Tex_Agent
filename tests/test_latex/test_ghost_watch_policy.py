import time
from pathlib import Path
from types import SimpleNamespace

from latex.constants import IssueSource, Severity
from latex.ghost_watch_policy import GhostWatchPolicy
from latex.models import DiagnosticIssue


def _wait_until(predicate, timeout_sec: float = 2.5, interval_sec: float = 0.05) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_sec)
    return False


def test_ghost_watch_policy_uses_quiet_window_and_disables_auto_polish(
    tmp_path, monkeypatch
):
    root = tmp_path / "proj"
    root.mkdir()
    tex_file = root / "main.tex"
    tex_file.write_text("hello", encoding="utf-8")

    call_times = []
    events = []

    def _mock_chktex(*_args, **_kwargs):
        call_times.append(time.time())
        return SimpleNamespace(issues=[], warnings=[])

    monkeypatch.setattr("latex.ghost_watch_policy.run_chktex", _mock_chktex)

    service = GhostWatchPolicy(
        watch_id="ghost_policy_test",
        root=str(root),
        main_tex="main.tex",
        quiet_sec=0.2,
        auto_polish=False,
        idle_polish_sec=0.1,
        enable_latexmk=False,
        on_event=lambda ev: events.append(ev),
    )
    service.start()
    try:
        time.sleep(0.25)
        assert len(call_times) == 0, "启动后不应自动触发静态检查"
        prev_calls = 0

        change_t0 = time.time()
        service.on_file_changed(tex_file)
        time.sleep(0.1)
        assert len(call_times) == prev_calls, "静默窗口内不应触发诊断"
        assert _wait_until(lambda: len(call_times) >= prev_calls + 1), "应在静默后触发诊断"
        assert call_times[-1] - change_t0 >= 0.18

        time.sleep(0.3)
        event_types = [ev.event_type for ev in events]
        assert "polish_suggestions_updated" not in event_types
    finally:
        service.stop()


def test_ghost_watch_policy_skips_llm_when_error_signature_unchanged(
    tmp_path, monkeypatch
):
    root = tmp_path / "proj"
    root.mkdir()
    tex_file = root / "main.tex"
    tex_file.write_text("hello", encoding="utf-8")

    issue = DiagnosticIssue.build(
        file="main.tex",
        line=1,
        message="Undefined control sequence",
        source=IssueSource.CHKTEX,
        severity=Severity.ERROR,
        code="E001",
        column=1,
    )

    monkeypatch.setattr(
        "latex.ghost_watch_policy.run_chktex",
        lambda *_args, **_kwargs: SimpleNamespace(issues=[issue], warnings=[]),
    )
    monkeypatch.setattr(
        "latex.ghost_watch_policy.parse_llm_suggestions_from_agent_result",
        lambda *_args, **_kwargs: [],
    )

    agent_run_count = {"n": 0}

    class _FakeAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, _msg):
            agent_run_count["n"] += 1
            return SimpleNamespace(content="[]")

    monkeypatch.setattr("latex.ghost_watch_policy.SimpleAgent", _FakeAgent)

    service = GhostWatchPolicy(
        watch_id="ghost_policy_error_sig",
        root=str(root),
        main_tex="main.tex",
        quiet_sec=0.15,
        auto_polish=False,
        enable_latexmk=False,
    )
    service.start()
    try:
        service.on_file_changed(tex_file)
        assert _wait_until(lambda: agent_run_count["n"] == 1), "首次 error 应触发一次 LLM"
        first_diag_time = service._last_diagnose_time  # noqa: SLF001
        service.on_file_changed(tex_file)
        assert _wait_until(
            lambda: service._last_diagnose_time > first_diag_time  # noqa: SLF001
        ), "应完成第二轮诊断"
        assert agent_run_count["n"] == 1, "error 未变化时不应重复调用 LLM"
        snap = service.get_snapshot()
        assert snap.error_signature
    finally:
        service.stop()


def test_ghost_watch_policy_warning_only_does_not_call_llm(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    tex_file = root / "main.tex"
    tex_file.write_text("hello", encoding="utf-8")

    warning = DiagnosticIssue.build(
        file="main.tex",
        line=1,
        message="Command terminated with space.",
        source=IssueSource.CHKTEX,
        severity=Severity.WARNING,
        code="1",
        column=1,
    )

    monkeypatch.setattr(
        "latex.ghost_watch_policy.run_chktex",
        lambda *_args, **_kwargs: SimpleNamespace(issues=[warning], warnings=[]),
    )

    called = {"n": 0}

    class _FakeAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, _msg):
            called["n"] += 1
            return SimpleNamespace(content="[]")

    monkeypatch.setattr("latex.ghost_watch_policy.SimpleAgent", _FakeAgent)

    service = GhostWatchPolicy(
        watch_id="ghost_policy_warn_only",
        root=str(root),
        main_tex="main.tex",
        quiet_sec=0.15,
        auto_polish=False,
        enable_latexmk=False,
    )
    service.start()
    try:
        service.on_file_changed(tex_file)
        assert _wait_until(lambda: service.project_version >= 1), "应在文件修改后完成诊断"
        assert called["n"] == 0
        snap = service.get_snapshot()
        assert len(snap.suggestions) == 0
    finally:
        service.stop()
