from __future__ import annotations

from pathlib import Path

from tools.preflight_inputs_tool import PreflightInputsTool


def _repo_root() -> Path:
    # tests/test_tools/test_preflight_inputs_tool.py -> repo root
    return Path(__file__).resolve().parents[2]


def test_preflight_extracts_linux_posix_and_tilde_paths() -> None:
    """Linux/POSIX：`/`、`~/`、`~其他用户/` 与 Windows 路径可同时出现在一段文本中并被抽出。"""
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_checklist_multi_v1.json"

    user_input = (
        "双路径对照:\n"
        "- [PDF] /var/thesis/论文.pdf\n"
        '- [Checklist] "~/checklists/review.md"\n'
        "~alice/projects/paper.pdf 与 D:\\\\share\\\\draft.pdf\n"
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
    paths = result.metadata.get("extracted_paths") or {}
    all_paths = paths.get("all_paths") or []
    joined = "\n".join(all_paths)
    assert "/var/thesis/论文.pdf" in joined
    assert "~/checklists/review.md" in joined or "checklists/review.md" in joined
    assert "alice/projects/paper.pdf" in joined or "~alice/projects/paper.pdf" in joined
    assert "draft.pdf" in joined


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
    assert "缺少工作流必填参数" in str(result.error or "")
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


def test_preflight_extracts_chapter_selection_for_new_tool(tmp_path: Path) -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    result = tool.run(
        {
            "user_input": f'请解析 "{pdf}" 的第3章和3.2-3.4，再加Chapter 5。',
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )

    assert result.success is True, result.error
    meta = result.metadata or {}
    contract = meta.get("slot_contract", [])
    contract_map = {c.get("slot"): c for c in contract if isinstance(c, dict)}
    assert "chapter_selection" in contract_map
    assert contract_map["chapter_selection"].get("slot_kind") == "value"

    extra_slots = meta.get("extra_slots", {})
    chapter_sel = str(extra_slots.get("chapter_selection", ""))
    assert chapter_sel
    assert "3" in chapter_sel
    assert "3.2-3.4" in chapter_sel
    assert "Chapter 5" in chapter_sel


def test_preflight_extracts_section_keywords_and_title_alias(tmp_path: Path) -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    result = tool.run(
        {
            "user_input": f'请解析 "{pdf}" 的摘要、英文摘要，以及“研究背景”这一小节，再看1.1小节。',
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )

    assert result.success is True, result.error
    extra_slots = (result.metadata or {}).get("extra_slots", {})
    chapter_sel = str(extra_slots.get("chapter_selection", ""))
    assert "摘要" in chapter_sel
    assert "英文摘要" in chapter_sel
    assert "研究背景" in chapter_sel
    assert "1.1" in chapter_sel


def test_preflight_extracts_full_text_request(tmp_path: Path) -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    for phrase in (
        "帮我解析全文",
        "请处理全篇",
        "通篇都要",
        "请处理整篇论文",
        "我想看 full text",
        "整本文档都要",
    ):
        result = tool.run(
            {
                "user_input": f'{phrase}，文件是 "{pdf}"。',
                "workflow_path": str(workflow_path),
                "current_node_id": "preflight_inputs",
                "use_llm": False,
                "strict_mode": True,
            }
        )
        assert result.success is True, (phrase, result.error)
        extra_slots = (result.metadata or {}).get("extra_slots", {})
        chapter_sel = str(extra_slots.get("chapter_selection", ""))
        assert chapter_sel == "全文", (phrase, chapter_sel)


def test_preflight_user_chapter_overrides_context_memory(tmp_path: Path) -> None:
    """记忆中是第3章，本轮明确说全文/通篇时，章节选择必须以本轮为准。"""
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf_new = tmp_path / "new.pdf"
    pdf_new.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    context = f'之前让你解析第3章，文件是 "{pdf_new}"\n'
    result = tool.run(
        {
            "user_input": "这次我要全文，不要第三章了。",
            "context_text": context,
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )
    assert result.success is True, result.error
    mm = (result.metadata or {}).get("memory_merge") or {}
    assert mm.get("chapter_priority_user") is True
    extra_slots = (result.metadata or {}).get("extra_slots", {})
    assert str(extra_slots.get("chapter_selection", "")) == "全文"


def test_preflight_user_path_overrides_context_memory(tmp_path: Path) -> None:
    """记忆中是文件 A，本轮给出另一路径时以本轮为准。"""
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf_old = tmp_path / "old.pdf"
    pdf_new = tmp_path / "new.pdf"
    pdf_old.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
    pdf_new.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    context = f'- [PDF] "{pdf_old}"\n'
    result = tool.run(
        {
            "user_input": f'请解析这份 "{pdf_new}" 的第1章',
            "context_text": context,
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )
    assert result.success is True, result.error
    mm = (result.metadata or {}).get("memory_merge") or {}
    assert mm.get("path_priority_user") is True
    normalized = (result.metadata or {}).get("normalized_inputs") or {}
    assert Path(normalized.get("pdf_path", "")).resolve() == pdf_new.resolve()


def test_preflight_uses_context_path_when_user_has_no_new_path(tmp_path: Path) -> None:
    """本轮未贴路径时，仍可沿用记忆中的 PDF 路径。"""
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf_ctx = tmp_path / "ctx.pdf"
    pdf_ctx.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    context = f'- [PDF] "{pdf_ctx}"\n'
    result = tool.run(
        {
            "user_input": "按上文路径解析第2章即可。",
            "context_text": context,
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )
    assert result.success is True, result.error
    mm = (result.metadata or {}).get("memory_merge") or {}
    assert mm.get("path_priority_user") is False
    normalized = (result.metadata or {}).get("normalized_inputs") or {}
    assert Path(normalized.get("pdf_path", "")).resolve() == pdf_ctx.resolve()
    extra_slots = (result.metadata or {}).get("extra_slots", {})
    assert "2" in str(extra_slots.get("chapter_selection", ""))


def test_preflight_windows_drive_not_extracted_as_chapter_token(tmp_path: Path) -> None:
    """Windows 路径 C:\\ 中的 C 不应被当成罗马数字章节 token。"""
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    result = tool.run(
        {
            "user_input": f'请解析 "{pdf}"，路径示例 C:\\\\研究\\\\论文.pdf',
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )
    assert result.success is True, result.error
    ev = (result.metadata or {}).get("extracted_values") or {}
    assert "C" not in (ev.get("chapter_tokens") or []), ev


def test_preflight_extracts_roman_and_fullwidth_chapters(tmp_path: Path) -> None:
    tool = PreflightInputsTool()
    workflow_path = _repo_root() / "config" / "workflow" / "workflow_thesis_chapter_extract.json"
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

    result = tool.run(
        {
            "user_input": f'解析 "{pdf}" 的 Chapter III、第Ⅳ章，再看 A. 引言。',
            "workflow_path": str(workflow_path),
            "current_node_id": "preflight_inputs",
            "use_llm": False,
            "strict_mode": True,
        }
    )
    assert result.success is True, result.error
    extra_slots = (result.metadata or {}).get("extra_slots", {})
    chapter_sel = str(extra_slots.get("chapter_selection", ""))
    assert chapter_sel, "应从混合编号中至少抽取到一个章节 token"
    # 至少包含罗马数字或归一化后的章节信息之一
    assert any(tok in chapter_sel for tok in ("III", "Ⅳ", "第Ⅳ章", "Chapter III", "A. 引言", "A"))
