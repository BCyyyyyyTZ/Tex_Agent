"""
tools.docling_search_tool 的单元测试（纯本地、无网络）。

覆盖点：
1) candidates 解析：JSON / Python literal / Markdown 代码块包裹等；
2) 文本节点抽取：texts / tables.captions / pictures.captions；
3) 搜索评分：词级重叠 + 子串加分；
4) tool.run 的两种模式：
   - search：为候选注释列表填充 page_idx；
   - export：导出按页分组的文本块供 LLM 选择 text_quote。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.docling_search_tool import (
    DoclingSearchTool,
    _extract_text_nodes,
    _parse_candidates,
    _score,
    _substring_bonus,
    _tokenize,
    _word_overlap_score,
)


def _write_docling_json(tmp_path: Path) -> Path:
    """
    构造一个最小可用的 docling document.json（只包含本工具需要的字段）。
    page_no 使用 1-based（与工具输出 page_idx 的语义一致）。
    """
    data = {
        "texts": [
            {"text": "This is an introduction.", "prov": [{"page_no": 1}], "label": "paragraph"},
            {"text": "方法：我们提出一种新方法。", "prov": [{"page_no": 2}], "label": "paragraph"},
        ],
        "tables": [
            {
                "prov": [{"page_no": 3}],
                "captions": [{"text": "Table 1: Ablation study."}],
            }
        ],
        "pictures": [
            {
                "prov": [{"page_no": 4}],
                "captions": [{"text": "Figure 2: System overview."}],
            }
        ],
    }
    p = tmp_path / "document.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def test_tokenize_handles_english_and_chinese() -> None:
    """
    _tokenize 的输出用于相似度计算：
    - 英文应按单词/数字分割；
    - 中文应按字（汉字字符）拆分；
    - 输出统一小写。
    """
    tokens = _tokenize("Hello 世界 2026!")
    assert "hello" in tokens
    assert "世" in tokens and "界" in tokens
    assert "2026" in tokens


def test_word_overlap_score_basic_properties() -> None:
    """
    词级重叠率应满足：
    - 空 query → 0；
    - 完全相同 → 1；
    - 部分重叠 → (0,1)。
    """
    assert _word_overlap_score("", "anything") == 0.0
    assert _word_overlap_score("a b", "a b") == 1.0
    s = _word_overlap_score("a b", "a c")
    assert 0.0 < s < 1.0


def test_substring_bonus_gives_reasonable_bonus() -> None:
    """
    子串加分是为了提升“摘录片段”被命中的概率：
    - 前缀出现应加分；
    - 完全包含应进一步加分；
    - 总加分上限为 0.4。
    """
    b1 = _substring_bonus("introduction", "This is an introduction.")
    assert 0.0 < b1 <= 0.4
    b2 = _substring_bonus("This is an introduction.", "This is an introduction.")
    assert b2 >= b1
    assert b2 <= 0.4


def test_score_is_capped_to_1() -> None:
    """
    综合得分 base+bonus 应被 cap 到 1.0。
    """
    s = _score("a b c d e f", "a b c d e f")
    assert 0.0 <= s <= 1.0
    assert s == 1.0


def test_extract_text_nodes_collects_texts_tables_pictures() -> None:
    """
    确认 _extract_text_nodes 能从三个位置抽取文本块：
    - texts
    - tables.captions
    - pictures.captions
    """
    data = {
        "texts": [{"text": "T", "prov": [{"page_no": 1}], "label": "p"}],
        "tables": [{"prov": [{"page_no": 2}], "captions": [{"text": "C"}]}],
        "pictures": [{"prov": [{"page_no": 3}], "captions": [{"text": "P"}]}],
    }
    nodes = _extract_text_nodes(data)
    assert len(nodes) == 3
    assert {n["page_no"] for n in nodes} == {1, 2, 3}
    assert {n["label"] for n in nodes} >= {"p", "table_caption", "figure_caption"}


def test_parse_candidates_accepts_json_and_python_literal_and_codeblock() -> None:
    """
    candidates 可能来自 LLM 输出，常见非规范形态：
    - JSON 数组字符串
    - Python 字面量（单引号）
    - Markdown 代码块包裹
    """
    raw_json = '[{"text_quote":"a","comment":"c"}]'
    items, err = _parse_candidates(raw_json)
    assert err is None and isinstance(items, list) and items[0]["text_quote"] == "a"

    raw_py = "[{'text_quote': 'b', 'comment': 'd'}]"
    items, err = _parse_candidates(raw_py)
    assert err is None and items[0]["text_quote"] == "b"

    raw_cb = "```json\n" + raw_json + "\n```"
    items, err = _parse_candidates(raw_cb)
    assert err is None and items[0]["text_quote"] == "a"


def test_docling_search_tool_export_mode(tmp_path: Path) -> None:
    """
    export 模式用于让 LLM 直接从文档库中挑选 text_quote：
    - output 为 JSON 字符串，包含 pages 与 total_blocks；
    - pages 的 key 为字符串页码，值为列表；
    - 每块文本应按 max_chars 截断。
    """
    json_path = _write_docling_json(tmp_path)
    tool = DoclingSearchTool()
    r = tool.run(json_path=str(json_path), mode="export", max_chars=10)
    assert r.success is True
    payload = json.loads(r.output)
    assert "pages" in payload and "total_blocks" in payload
    assert payload["total_blocks"] >= 1
    # 页面 key 应为字符串
    assert all(isinstance(k, str) for k in payload["pages"].keys())
    # 截断：至少有一条带省略号
    any_truncated = any("…" in blk["text"] for pg in payload["pages"].values() for blk in pg)
    assert any_truncated is True


def test_docling_search_tool_search_mode_fills_page_idx(tmp_path: Path) -> None:
    """
    search 模式应为 candidates 填充 page_idx：
    - 对能命中的 text_quote 返回 page_idx；
    - 对空文本/低相似度条目可不返回（并计入 unfound）。
    """
    json_path = _write_docling_json(tmp_path)
    tool = DoclingSearchTool()

    candidates = [
        {"text_quote": "introduction", "comment": "should be on page 1"},
        {"text_quote": "Ablation study", "comment": "should be on page 3"},
        {"text_quote": "", "comment": "empty should be unfound"},
    ]
    r = tool.run(json_path=str(json_path), mode="search", candidates=candidates, min_score=0.1, top_k=1)
    assert r.success is True
    out = json.loads(r.output)
    assert isinstance(out, list)
    # 只断言“能定位到的条目”存在，并且页码正确；未定位条目允许被过滤掉
    by_comment = {x["comment"]: x for x in out}
    assert by_comment["should be on page 1"]["page_idx"] == 1
    assert by_comment["should be on page 3"]["page_idx"] == 3


def test_docling_search_tool_rejects_bad_candidates(tmp_path: Path) -> None:
    """
    candidates 解析失败或为空时，应返回 success=False，且 error 含可读原因。
    """
    json_path = _write_docling_json(tmp_path)
    tool = DoclingSearchTool()

    r1 = tool.run(json_path=str(json_path), mode="search", candidates=123)
    assert r1.success is False
    assert "解析失败" in (r1.error or "")

    r2 = tool.run(json_path=str(json_path), mode="search", candidates="[]")
    assert r2.success is False
    assert "candidates 为空" in (r2.error or "")

