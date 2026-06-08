"""回复展示整理（不调用 LLM）。"""
from utils.reply_format import normalize_reply_display, strip_citation_artifacts


def test_strip_citation_artifacts():
    raw = "剧情很好。\ue000cite\ue001turn0search0\ue001turn0search4\ue001\n\n下一段。"
    out = strip_citation_artifacts(raw)
    assert "cite" not in out
    assert "turn0search" not in out


def test_merge_short_paragraphs():
    raw = "他是典型的失权王子。\n\n身份高贵却缺乏自由。\n\n拥有王室头衔却无法掌控命运。\n\n二、人物塑造"
    out = normalize_reply_display(raw, short_para_chars=80)
    assert "二、人物塑造" in out
    assert out.count("\n\n") <= 2
    assert "身份高贵却缺乏自由" in out
    assert "他是典型的失权王子" in out.split("二、")[0]


def test_preserves_markdown_headers():
    raw = (
        "## 方向1: Agent Memory\n"
        "研究长期记忆与上下文窗口。\n"
        "## 方向2: Multi-Agent\n"
        "协作与任务分配。"
    )
    out = normalize_reply_display(raw)
    assert "## 方向1: Agent Memory" in out
    assert "## 方向2: Multi-Agent" in out
    assert "\n\n" in out
    assert "## 方向1" in out.split("## 方向2")[0]


def test_dense_single_line_gets_section_breaks():
    raw = (
        "一、Agent研究全景图 Agent = LLM + Memory + Planning。"
        "二、建议阅读顺序 先读 ReAct。"
        "三、研究方向 ## 方向1: Memory"
    )
    out = normalize_reply_display(raw)
    assert "一、Agent研究全景图" in out
    assert "\n\n二、" in out or out.startswith("一、")
    assert "二、建议阅读顺序" in out


def test_list_lines_not_merged_into_previous():
    raw = "要点如下：\n- 记忆模块\n- 规划模块\n- 工具调用"
    out = normalize_reply_display(raw)
    assert "- 记忆模块" in out
    assert "- 规划模块" in out
    assert out.count("- ") >= 2


def test_single_newline_short_fragments_merge():
    raw = "他是典型的失权王子。\n身份高贵却缺乏自由。\n拥有王室头衔却无法掌控命运。"
    out = normalize_reply_display(raw, short_para_chars=80)
    assert out.count("\n\n") <= 1
    assert "他是典型的失权王子" in out
    assert "身份高贵却缺乏自由" in out
