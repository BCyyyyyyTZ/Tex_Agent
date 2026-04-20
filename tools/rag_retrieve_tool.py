"""
RAGRetrieveTool：从本地向量知识库检索与查询语义相近的文档片段。

封装 RAGPipeline：查询自动经 embedding 后在向量库中做相似度检索，返回 top-k 条结果；
支持纯文本（与 Prompt 注入格式一致）或 JSON 结构化输出。
"""

import json
from typing import Any, Optional

from tools.base_tool import BaseTool
from core.message import ToolResult
from rag.rag_pipeline import RAGPipeline
from rag.base_retriever import BaseRAGPipeline, RetrievedDocument
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def _document_to_jsonable(doc: RetrievedDocument) -> dict[str, Any]:
    return {
        "content": doc.content,
        "source": doc.source,
        "score": doc.score,
        "metadata": doc.metadata or {},
    }


class RAGRetrieveTool(BaseTool):
    """
    向量知识库检索工具。

    使用与索引时相同的持久化目录（settings.rag_persist_directory）；
    若知识库为空，会返回说明性文案而非抛错。
    """

    def __init__(self, pipeline: Optional[BaseRAGPipeline] = None) -> None:
        super().__init__(
            name="rag_retrieve",
            description=(
                "从项目向量知识库中检索与用户问题相关的文档片段。"
                "输入自然语言查询即可，工具会自动做语义向量检索并返回最相关的若干条内容。"
                "适用于需要依据已索引资料（论文、笔记、项目文档等）回答问题的场景。"
            ),
            input_schema={
                "query": "必填，检索查询语句（自然语言）",
                "k": "可选，返回条数上限，默认使用系统配置 rag_top_k",
                "output_format": '可选，输出格式："text"（默认，适合直接阅读或拼进 Prompt）或 "json"（结构化，含 content/source/score/metadata）',
            },
        )
        self._pipeline = pipeline if pipeline is not None else RAGPipeline()

    def run(
        self,
        query: str,
        k: Optional[int] = None,
        output_format: str = "text",
    ) -> ToolResult:
        q = (query or "").strip()
        if not q:
            return ToolResult(
                success=False,
                output="",
                error="query 不能为空",
                metadata={"query": query},
            )

        fmt = (output_format or "text").strip().lower()
        if fmt not in ("text", "json"):
            return ToolResult(
                success=False,
                output="",
                error='output_format 仅支持 "text" 或 "json"',
                metadata={"query": q, "output_format": output_format},
            )

        try:
            if not self._pipeline.is_ready():
                msg = "当前向量知识库为空，暂无已索引文档可检索。请先通过索引流程导入文本或文件。"
                logger.info("RAGRetrieveTool: 知识库为空")
                return ToolResult(
                    success=True,
                    output=msg,
                    metadata={"query": q, "hits": 0, "empty_kb": True},
                )

            actual_k = k if k is not None else settings.rag_top_k

            if fmt == "text":
                text_out = self._pipeline.retrieve(q, k=actual_k)
                if not text_out:
                    text_out = "未检索到与查询相关的片段（或相似度过低）。可尝试改写查询或确认资料已入库。"
                logger.info(
                    "RAGRetrieveTool: text 检索完成 | k=%s | len=%s",
                    actual_k,
                    len(text_out),
                )
                return ToolResult(
                    success=True,
                    output=text_out,
                    metadata={"query": q, "k": actual_k, "output_format": "text"},
                )

            docs = self._pipeline.retrieve_documents(q, k=actual_k)
            payload = {
                "query": q,
                "k": actual_k,
                "count": len(docs),
                "hits": [_document_to_jsonable(d) for d in docs],
            }
            json_out = json.dumps(payload, ensure_ascii=False, indent=2)
            logger.info(
                "RAGRetrieveTool: json 检索完成 | hits=%s",
                len(docs),
            )
            return ToolResult(
                success=True,
                output=json_out,
                metadata={"query": q, "k": actual_k, "output_format": "json", "hit_count": len(docs)},
            )

        except Exception as e:
            logger.exception("RAGRetrieveTool 执行失败: %s", e)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                metadata={"query": q},
            )