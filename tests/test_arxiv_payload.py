"""arxiv_search 入参规范化（不调用 arXiv API）。"""
from datetime import datetime
from types import SimpleNamespace

from tools.arxiv_tool import ArxivSearchTool, prepare_arxiv_query
from workflow.nodes import _normalize_arxiv_tool_payload


def _fake_paper(title: str, summary: str) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        summary=summary,
        authors=[SimpleNamespace(name="Alice Smith")],
        published=datetime(2024, 1, 2),
        entry_id="https://arxiv.org/abs/2401.00001",
    )


def test_format_abstract_only_omits_authors():
    from tools.arxiv_tool import ArxivPaper

    tool = ArxivSearchTool(max_results=1)
    text = tool._format(
        [ArxivPaper(title="Agentic RAG Survey", abstract="A " * 200, url="https://arxiv.org/abs/1")]
    )
    assert "摘要：" in text
    assert "作者：" not in text
    assert "发表：" not in text
    assert "Agentic RAG Survey" in text


def test_search_query_param_quotes_multiword():
    from tools.arxiv_tool import _search_query_param

    assert _search_query_param("Agentic RAG") == 'all:"Agentic RAG"'
    assert _search_query_param("electron") == "all:electron"


def test_coerce_json_string_query():
    raw = '{"query":"embodied agent robotics"}'
    assert prepare_arxiv_query(raw) == "embodied agent robotics"


def test_normalize_dict_nested_json_query():
    payload = {"query": '{"query":"multi-agent systems"}'}
    assert _normalize_arxiv_tool_payload(payload) == "multi-agent systems"


def test_normalize_plain_string_unchanged():
    assert _normalize_arxiv_tool_payload("machine learning") == "machine learning"


def test_normalize_dict_query():
    assert _normalize_arxiv_tool_payload({"query": "LLM agent"}) == "LLM agent"


def test_malformed_json_wrapper_still_unwraps():
    raw = '{"query": "multi-agent collaboration", "extra": broken'
    assert "multi-agent" in prepare_arxiv_query(raw)


def test_fallback_parallel_branch_picks_direction():
    from workflow.nodes import _fallback_arxiv_query

    state = {
        "input": "你好，请你为我查询 agent 研究方向",
        "metadata": {
            "mas_trend_analysis": {
                "result": (
                    '{"协作": "multi-agent cooperation CTDE", '
                    '"强化学习": "multi-agent reinforcement learning"}'
                ),
            },
        },
    }
    q = _fallback_arxiv_query(state, "search_direction_2", [])
    assert "reinforcement" in q.lower()


def test_summary_mash_extracts_english_phrases():
    raw = (
        "Agent 8 ：Agent 、Tool Use、 、Agent Memory、Agentic RAG、 、Agent 。"
        " Agentic RAG、Long-Horizon Agent、Multi-Agent Memory 1-2 。 、"
    )
    q = prepare_arxiv_query(raw)
    assert "Agentic RAG" in q
    assert "：" not in q
    assert "、" not in q
    assert len(q) <= 120


def test_parenthetical_chinese_title_extracts_english():
    q = prepare_arxiv_query("多智能体强化学习（Multi-Agent Reinforcement Learning, MARL）")
    assert "Multi-Agent" in q
    assert "MARL" in q
    assert "多智能体" not in q


def test_compress_long_chinese_report_extracts_english():
    report = (
        "1. 多智能体协作\n"
        '   - arXiv 检索关键词："multi-agent systems", "collaborative agents"\n'
        "2. 其他方向…"
    )
    q = prepare_arxiv_query({"query": report})
    assert "multi-agent" in q
    assert len(q) <= 220
