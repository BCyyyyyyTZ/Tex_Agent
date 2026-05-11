from __future__ import annotations

from pathlib import Path

from tools.preflight_inputs_tool import PreflightInputsTool


def _repo_root() -> Path:
    # tests/test_tools/test_preflight_inputs_tool.py -> repo root
    return Path(__file__).resolve().parents[2]


def test_preflight_extracts_cross_platform_paths_and_slots() -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_checklist_multi_v1.json"

    user_input = (
        "请按 checklist 审查。\n"
        "- [PDF] C:\\研究资料\\论文\\中文 文件.pdf\n"
        "- [Checklist] /home/yt/checklists/论文审查清单.md\n"
    )

    result = tool.run(
        {
            "user_input": user_input,
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
        }
    )

    assert result.success is True
    meta = result.metadata
    assert isinstance(meta, dict)

    analysis = meta.get("analysis", {})
    slots = analysis.get("user_required_slots", [])
    slot_names = {s.get("slot") for s in slots if isinstance(s, dict)}
    assert "pdf_path" in slot_names
    assert "checklist_path" in slot_names

    normalized = meta.get("normalized_inputs", {})
    assert normalized.get("pdf_path", "").lower().endswith("中文 文件.pdf".lower())
    assert normalized.get("checklist_path", "") == "/home/yt/checklists/论文审查清单.md"


def test_preflight_payload_fallback_to_raw_input_when_unresolved() -> None:
    tool = PreflightInputsTool()
    user_input = "帮我看一下论文内容，但我没给具体路径。"
    result = tool.run({"user_input": user_input, "use_llm": False})

    assert result.success is True
    payload = result.metadata.get("payload_for_register_inputs")
    assert payload == user_input


def test_preflight_merges_context_text_paths(tmp_path: Path) -> None:
    """路径仅出现在 context_text 时也应被抽取；run_register 写出与 register_inputs 一致的绝对路径字段。"""
    tool = PreflightInputsTool()
    pdf = tmp_path / "上下文论文.pdf"
    cl = tmp_path / "清单.md"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    cl.write_text("# checklist", encoding="utf-8")

    context = f"- [PDF] {pdf}\n- [Checklist] {cl}\n"
    result = tool.run(
        {
            "user_input": "请按上文的文件继续审查。",
            "context_text": context,
            "use_llm": False,
            "run_register": True,
        }
    )
    assert result.success is True, result.metadata
    meta = result.metadata
    assert meta.get("pdf_abs_path")
    assert meta.get("checklist_abs_path")
    assert Path(meta["pdf_abs_path"]).resolve() == pdf.resolve()
    assert Path(meta["checklist_abs_path"]).resolve() == cl.resolve()


def test_preflight_strict_mode_fails_when_required_slots_missing() -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_checklist_multi_v4.json"

    result = tool.run(
        {
            "user_input": "请帮我审查论文，但是路径我稍后再补。",
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
            "run_register": False,
        }
    )

    assert result.success is False
    assert "缺少工作流必填路径参数" in str(result.error or "")
    meta = result.metadata or {}
    assert "slot_contract" in meta


def test_preflight_auto_fills_output_path_when_missing(tmp_path: Path) -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_checklist_multi_v4.json"
    pdf = tmp_path / "paper.pdf"
    checklist = tmp_path / "checklist.md"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    checklist.write_text("# checklist", encoding="utf-8")

    result = tool.run(
        {
            "user_input": f'- [PDF] "{pdf}"\n- [Checklist] "{checklist}"',
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
            "run_register": False,
        }
    )

    assert result.success is True
    normalized = (result.metadata or {}).get("normalized_inputs", {})
    output_path = str(normalized.get("output_path", ""))
    assert output_path
    assert output_path.lower().endswith("-checked.pdf")
