from __future__ import annotations

from workflow.parallel_merger import JoinPolicy, merge_parallel_results


def test_merge_parallel_results__all_success_ok() -> None:
    state = {
        "metadata": {
            "b1": {"status": "pass", "result": "r1", "summary": "s1"},
            "b2": {"status": "pass", "result": "r2"},
        }
    }
    m = merge_parallel_results(state, ["b1", "b2"], policy=JoinPolicy.ALL_SUCCESS)
    assert m.success is True
    assert m.total_branches == 2
    assert m.succeeded_branches == 2
    assert m.failed_branch_ids == []
    assert "[OK" in m.combined_result


def test_merge_parallel_results__all_success_fail_when_any_failed() -> None:
    state = {
        "metadata": {
            "b1": {"status": "fail", "result": "", "metadata": {"error": "boom"}},
            "b2": {"status": "pass", "result": "r2"},
        }
    }
    m = merge_parallel_results(state, ["b1", "b2"], policy=JoinPolicy.ALL_SUCCESS)
    assert m.success is False
    assert m.failed_branch_ids == ["b1"]
    assert "boom" in m.error_summary
    assert "[FAIL" in m.combined_result


def test_merge_parallel_results__partial_success_ok_if_any_ok() -> None:
    state = {"metadata": {"b1": {"status": "fail"}, "b2": {"status": "pass", "result": "ok"}}}
    m = merge_parallel_results(state, ["b1", "b2"], policy=JoinPolicy.PARTIAL)
    assert m.success is True


def test_merge_parallel_results__first_success_uses_first_success_result() -> None:
    state = {"metadata": {"b1": {"status": "pass", "result": "r1"}, "b2": {"status": "pass", "result": "r2"}}}
    m = merge_parallel_results(state, ["b1", "b2"], policy=JoinPolicy.FIRST_SUCCESS)
    assert m.success is True
    assert m.combined_result == "r1"

