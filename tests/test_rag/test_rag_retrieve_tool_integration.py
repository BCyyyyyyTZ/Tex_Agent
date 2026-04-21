"""
RAGRetrieveTool 真实向量库集成测试（无 Mock）。

使用 tmp_path 下独立 Chroma 持久化目录 + 真实 embedding，索引固定文本后调用工具，
在终端打印完整 ToolResult，并写入 tests/test_rag/_rag_tool_output/ 便于打开查看。

运行（需已安装 chromadb 与 embedding 依赖，且勿设 SKIP_CHROMA_INTEGRATION=1）：

    cd Tex_Agent
    pytest tests/test_rag/test_rag_retrieve_tool_integration.py -v -m integration -s
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from rag.rag_pipeline import RAGPipeline
from tools.rag_retrieve_tool import RAGRetrieveTool

pytestmark = pytest.mark.integration

OUTPUT_DIR = Path(__file__).resolve().parent / "_rag_tool_output"
# 与 config/settings._project_root 一致：含 rag/、tests/、knowledge_base/ 的包根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_BASE_DIR = _PROJECT_ROOT / "knowledge_base"

INDEX_BODY = (
    "RAGRetrieveTool 集成测试专用段落。"
    "关键词：紫杉醇测试标记 ALPHA_RAG_TOOL_7721。"
    "Transformer 使用自注意力机制连接编码器与解码器。"
)


def _skip_if_disabled() -> None:
    if os.getenv("SKIP_CHROMA_INTEGRATION", "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_CHROMA_INTEGRATION is set")


def _require_chromadb() -> None:
    pytest.importorskip("chromadb")


def _make_pipeline(tmp_path: Path) -> RAGPipeline:
    _skip_if_disabled()
    _require_chromadb()
    db_dir = tmp_path / f"chroma_tool_{uuid.uuid4().hex}"
    db_dir.mkdir(parents=True, exist_ok=True)
    return RAGPipeline(persist_directory=str(db_dir), chunk_size=200, chunk_overlap=20)

def _tool_result_block(label: str, result, output_kind: str) -> str:
    """与落盘文件一致的人类可读块（含 success / metadata / output）。"""
    return (
        f"========== {label} ==========\n"
        f"success: {result.success}\n"
        f"error: {result.error!r}\n"
        f"metadata: {json.dumps(result.metadata, ensure_ascii=False, indent=2)}\n"
        f"---------- output ({output_kind}) ----------\n"
        f"{result.output}\n"
        f"========== end ==========\n"
    )

def _print_and_save(label: str, result, suffix: str) -> None:
    """终端打印 + 落盘，便于肉眼查看工具返回形态。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"last_{suffix}"
    block = _tool_result_block(label, result, suffix)
    print("\n" + block, flush=True)
    path.write_text(block, encoding="utf-8")
    print(f"[已写入] {path}", flush=True)


def test_rag_retrieve_tool_text_output(tmp_path: Path) -> None:
    pipe = _make_pipeline(tmp_path)
    n = pipe.index_text(INDEX_BODY, source="tool_integration_fixture.txt")
    assert n >= 1

    tool = RAGRetrieveTool(pipeline=pipe)
    result = tool.run(
        query="紫杉醇测试标记与 Transformer 注意力",
        k=3,
        output_format="text",
    )

    assert result.success is True
    assert "ALPHA_RAG_TOOL_7721" in result.output or "注意力" in result.output or "相关片段" in result.output

    _print_and_save("RAGRetrieveTool text", result, "text.txt")


def test_rag_retrieve_tool_json_output(tmp_path: Path) -> None:
    pipe = _make_pipeline(tmp_path)
    pipe.index_text(INDEX_BODY, source="tool_integration_fixture.txt")

    tool = RAGRetrieveTool(pipeline=pipe)
    result = tool.run(
        query="ALPHA_RAG_TOOL_7721 关键词检索",
        k=2,
        output_format="json",
    )

    assert result.success is True
    data = json.loads(result.output)
    assert data["query"]
    assert "hits" in data
    assert isinstance(data["hits"], list)

    _print_and_save("RAGRetrieveTool json", result, "json.txt")


def test_rag_retrieve_tool_empty_kb_prints_message(tmp_path: Path) -> None:
    """空库：工具不报错，返回说明文案；同样打印便于对照边界行为。"""
    pipe = _make_pipeline(tmp_path)
    assert pipe.is_ready() is False

    tool = RAGRetrieveTool(pipeline=pipe)
    result = tool.run(query="任意查询", output_format="text")

    assert result.success is True
    assert "空" in result.output or "索引" in result.output

    _print_and_save("RAGRetrieveTool empty_kb", result, "empty_kb.txt")

def test_rag_retrieve_lora_keyword_text_and_json() -> None:
    """
    关键词「LoRA」：直接使用包根下 knowledge_base 的持久化向量库，
    不做临时库、不在此用例中写入索引。text / json 结果写入 _rag_tool_output。
    库为空或无命中时仍 success=True，落盘便于人工核对。
    """
    _skip_if_disabled()
    _require_chromadb()
    kb = KNOWLEDGE_BASE_DIR.resolve()
    kb.mkdir(parents=True, exist_ok=True)
    print(f"[LoRA 真实库] persist_directory={kb}", flush=True)
    pipe = RAGPipeline(persist_directory=str(kb))
    tool = RAGRetrieveTool(pipeline=pipe)
    res_text = tool.run(query="LoRA", k=4, output_format="text")
    res_json = tool.run(query="LoRA", k=4, output_format="json")
    assert res_text.success is True
    assert res_json.success is True
    data = json.loads(res_json.output)
    assert data.get("query") == "LoRA"
    assert "hits" in data
    assert isinstance(data["hits"], list)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    text_path = OUTPUT_DIR / "lora_retrieve.text.txt"
    json_path = OUTPUT_DIR / "lora_retrieve.hits.json"
    header = f"persist_directory: {kb}\nready(document_count>0): {pipe.is_ready()}\n\n"
    text_block = header + _tool_result_block(
        "RAGRetrieveTool LoRA 真实库 (output_format=text)", res_text, "text"
    )
    print("\n" + text_block, flush=True)
    text_path.write_text(text_block, encoding="utf-8")
    print(f"[已写入] {text_path}", flush=True)
    json_block = header + _tool_result_block(
        "RAGRetrieveTool LoRA 真实库 (output_format=json)", res_json, "json"
    )
    print("\n" + json_block, flush=True)
    json_path.write_text(res_json.output, encoding="utf-8")
    print(f"[已写入] {json_path}", flush=True)