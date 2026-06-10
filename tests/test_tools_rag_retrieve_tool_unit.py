"""
tools.rag_retrieve_tool 的单元测试。

说明：
- 本文件聚焦于 RAGRetrieveTool 的接口契约与输出协议；
- 为保证测试稳定性，使用一个“最小可用的检索管线实现”提供 is_ready/retrieve/retrieve_documents 行为。

覆盖点：
1) query 为空与 output_format 非法的输入校验；
2) 知识库为空（pipeline.is_ready=False）时的说明性输出；
3) text/json 两种输出格式的行为与结构。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from tools.rag_retrieve_tool import RAGRetrieveTool


@dataclass
class _RetrievedDoc:
    content: str
    source: str
    score: float
    metadata: dict


class _MinimalPipeline:
    """
    供测试使用的最小检索管线实现：
    - is_ready(): 知识库是否可检索
    - retrieve(): 返回拼接好的文本
    - retrieve_documents(): 返回结构化文档列表
    """

    def __init__(self, *, ready: bool = True, text: str = "", docs: list[_RetrievedDoc] | None = None):
        self._ready = ready
        self._text = text
        self._docs = docs or []
        self.calls: list[tuple[str, dict]] = []

    def is_ready(self) -> bool:
        return self._ready

    def retrieve(self, query: str, k: int):
        self.calls.append(("retrieve", {"query": query, "k": k}))
        return self._text

    def retrieve_documents(self, query: str, k: int):
        self.calls.append(("retrieve_documents", {"query": query, "k": k}))
        return self._docs[:k]


def test_rejects_empty_query() -> None:
    tool = RAGRetrieveTool(pipeline=_MinimalPipeline())
    r = tool.run(query="")
    assert r.success is False
    assert "query 不能为空" in (r.error or "")


def test_rejects_invalid_output_format() -> None:
    tool = RAGRetrieveTool(pipeline=_MinimalPipeline())
    r = tool.run(query="q", output_format="xml")
    assert r.success is False
    assert "output_format" in (r.error or "")


def test_empty_kb_returns_explanatory_text() -> None:
    tool = RAGRetrieveTool(pipeline=_MinimalPipeline(ready=False))
    r = tool.run(query="q")
    assert r.success is True
    assert "知识库为空" in r.output
    assert r.metadata.get("empty_kb") is True


def test_text_output_fallback_when_pipeline_returns_empty() -> None:
    tool = RAGRetrieveTool(pipeline=_MinimalPipeline(ready=True, text=""))
    r = tool.run(query="q", k=3, output_format="text")
    assert r.success is True
    assert "未检索到" in r.output


def test_json_output_contains_expected_schema() -> None:
    docs = [
        _RetrievedDoc(content="c1", source="s1", score=0.9, metadata={"a": 1}),
        _RetrievedDoc(content="c2", source="s2", score=0.8, metadata={}),
    ]
    tool = RAGRetrieveTool(pipeline=_MinimalPipeline(ready=True, docs=docs))
    r = tool.run(query="q", k=1, output_format="json")
    assert r.success is True
    payload = json.loads(r.output)
    assert payload["query"] == "q"
    assert payload["k"] == 1
    assert payload["count"] == 1
    assert isinstance(payload["hits"], list) and len(payload["hits"]) == 1
    hit = payload["hits"][0]
    assert hit["content"] == "c1"
    assert hit["source"] == "s1"
    assert hit["metadata"]["a"] == 1
