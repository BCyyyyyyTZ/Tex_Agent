"""
DoclingSearchTool：在 Docling 解析的 JSON 文件中本地搜索文本，返回精确页码。

设计目标：
  - checklist 检查节点只需输出 {text_quote, comment}，无需猜测页码
  - 本工具在本地 JSON 中模糊匹配，返回 {page_idx, text, comment}
  - 全程不发送 PDF 或文档内容给 LLM API

搜索算法：
  1. 对 JSON 中每个文本块（texts 数组 + 表格 caption）计算词级相似度
  2. 取相似度最高的匹配，返回其 page_no
  3. 支持批量搜索（candidates 列表）
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger
from utils.text_normalize import normalize, normalize_for_search

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 文本相似度计算（纯本地，无外部依赖）
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """简单分词：Unicode规范化后英文按空格+标点分，中文按字分。"""
    text = normalize(text).lower()
    tokens = re.findall(r'[a-z0-9]+|[\u4e00-\u9fff\u3400-\u4DBF]', text)
    return tokens


def _word_overlap_score(query: str, candidate: str) -> float:
    """
    词级重叠率（Jaccard-like）。
    返回 [0, 1]，1 表示完全匹配。
    """
    q_tokens = set(_tokenize(query))
    c_tokens = set(_tokenize(candidate))
    if not q_tokens:
        return 0.0
    overlap = len(q_tokens & c_tokens)
    union = len(q_tokens | c_tokens)
    return overlap / union if union else 0.0


def _substring_bonus(query: str, candidate: str) -> float:
    """
    子串加分：
    - query 去空格后的前20字符出现在 candidate 中 → +0.3
    - 两者规范化后去空格完全包含 → +0.2
    """
    bonus = 0.0
    q_norm = normalize_for_search(query, strip_spaces=True)
    c_norm = normalize_for_search(candidate, strip_spaces=True)
    if not q_norm or not c_norm:
        return 0.0
    prefix = q_norm[:20]
    if prefix and prefix in c_norm:
        bonus += 0.3
    # 长度差异不大时，完全包含给更高加分
    if len(q_norm) >= 6 and q_norm in c_norm:
        bonus += 0.2
    return min(bonus, 0.4)


def _score(query: str, candidate: str) -> float:
    base = _word_overlap_score(query, candidate)
    bonus = _substring_bonus(query, candidate)
    return min(1.0, base + bonus)


# ---------------------------------------------------------------------------
# JSON 文本块提取
# ---------------------------------------------------------------------------

def _extract_text_nodes(data: dict) -> List[Dict[str, Any]]:
    """
    从 docling JSON 中提取所有文本块，返回格式：
    [{"text": str, "page_no": int, "label": str}, ...]
    """
    nodes = []

    # 1. texts 数组（段落、标题、列表等）
    for item in data.get("texts", []):
        text = str(item.get("text", "")).strip()
        prov_list = item.get("prov", [])
        if text and prov_list:
            page_no = prov_list[0].get("page_no", 0)
            nodes.append({
                "text": text,
                "page_no": page_no,
                "label": item.get("label", "text"),
            })

    # 2. 表格 caption
    for table in data.get("tables", []):
        for cap in table.get("captions", []):
            text = str(cap.get("text", "")).strip()
            prov_list = table.get("prov", [])
            if text and prov_list:
                page_no = prov_list[0].get("page_no", 0)
                nodes.append({
                    "text": text,
                    "page_no": page_no,
                    "label": "table_caption",
                })

    # 3. 图片 caption
    for pic in data.get("pictures", []):
        for cap in pic.get("captions", []):
            text = str(cap.get("text", "")).strip()
            prov_list = pic.get("prov", [])
            if text and prov_list:
                page_no = prov_list[0].get("page_no", 0)
                nodes.append({
                    "text": text,
                    "page_no": page_no,
                    "label": "figure_caption",
                })

    return nodes


# ---------------------------------------------------------------------------
# DoclingSearchTool
# ---------------------------------------------------------------------------

class DoclingSearchTool(BaseTool):
    """
    在 Docling JSON 文件中本地搜索文本，返回精确页码（page_idx）。

    用途：
      - checklist 检查 agent 输出 [{text_quote, comment}, ...]
      - 本工具在 JSON 中模糊匹配 text_quote，找到 page_idx
      - 返回 [{page_idx, text, comment}, ...] 供 pdf_comment 使用

    workflow 用法示例：
      {
        "node_type": "tool",
        "tool_name": "docling_search",
        "config": {
          "tool_input": {
            "json_path": "${metadata.parse_paper.metadata.json_path}",
            "candidates": "${metadata.annotation_formatter.result}"
          }
        }
      }

    candidates 格式（JSON 数组或 Python 列表）：
      [{"text_quote": "要定位的原文片段", "comment": "注释说明"}, ...]
    或已有 page_idx 的格式（原样保留，只补全缺失的）：
      [{"text": "...", "comment": "...", "page_idx": 0}]  ← page_idx=0 表示待定位
    """

    def __init__(self):
        super().__init__(
            name="docling_search",
            description=(
                "在 Docling 解析的 JSON 文件中本地模糊搜索文本，返回每条文本对应的精确页码（page_idx）。\n"
                "支持两种模式（mode 参数）：\n"
                "  'search'（默认）：输入 candidates（注释列表），模糊匹配后填充 page_idx，供 pdf_comment 使用。\n"
                "  'export'：不需要 candidates，直接返回文档所有文本块（按页整理），供 checker agent 选取 text_quote。\n"
                "全程不发送文档内容给 LLM API，搜索在本地完成。"
            ),
            input_schema={
                "json_path": "必填，Docling 解析输出的 document.json 路径",
                "mode": "可选，'search'（默认，填充页码）或 'export'（导出文本块供LLM选取）",
                "candidates": (
                    "search 模式下必填，JSON 数组（或 Python 列表字符串），每项包含 text_quote（原文片段）和 comment（注释说明）。"
                    "也支持已含 page_idx 字段的格式（page_idx=0 视为待定位）。"
                ),
                "min_score": "可选，最低相似度阈值 [0, 1]，低于此值则将该条归入未定位，默认 0.25",
                "top_k": "可选，每次查询返回最多前 k 个候选，默认 1（只取最佳匹配）",
                "max_chars": "export 模式下可选，每个文本块最多截取的字符数，默认 200（避免长段占用太多 token）",
            }
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def run(
        self,
        json_path: str,
        mode: str = "search",
        candidates: Any = None,
        min_score: float = 0.25,
        top_k: int = 1,
        max_chars: int = 200,
    ) -> ToolResult:
        """
        在 JSON 文本库中搜索 candidates 中的每段文本，填充 page_idx。

        Args:
            json_path:   Docling document.json 路径
            mode:        'search'（默认）或 'export'
            candidates:  search 模式下必填，注释候选列表
            min_score:   最低相似度阈值（search 模式）
            top_k:       每次查询最多返回几个候选（search 模式，一般取 1）
            max_chars:   export 模式下每块文本的最大截取长度

        Returns:
            ToolResult，output 为：
              - search 模式：已填充 page_idx 的注释数组（JSON 字符串）
              - export 模式：按页整理的文本块（JSON 字符串），供 LLM 选 text_quote
        """
        logger.info(f"DoclingSearchTool | json={json_path!r}")

        # ── export 模式：直接导出文本库 ─────────────────────────────────
        if mode == "export":
            return self._export_texts(json_path, max_chars)

        # 1. 解析 candidates
        items, err = _parse_candidates(candidates)
        if err:
            return ToolResult(
                success=False, output="", error=f"candidates 解析失败: {err}",
                metadata={"json_path": json_path},
            )
        if not items:
            return ToolResult(
                success=False, output="", error="candidates 为空",
                metadata={"json_path": json_path},
            )

        # 2. 加载 JSON 文本库
        try:
            data = json.load(open(json_path, encoding="utf-8"))
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"JSON 加载失败: {e}",
                metadata={"json_path": json_path},
            )

        text_nodes = _extract_text_nodes(data)
        logger.info(f"文本库大小: {len(text_nodes)} 个块")

        # 3. 逐条搜索
        located: List[Dict] = []
        unfound: List[str] = []
        stats = {"total": len(items), "located": 0, "unfound": 0}

        for item in items:
            # 兼容两种输入格式
            query = str(item.get("text_quote") or item.get("text") or "").strip()
            comment = str(item.get("comment", "")).strip()
            existing_page = item.get("page_idx", 0)

            # 如果已经有有效 page_idx，直接保留
            if existing_page and isinstance(existing_page, int) and existing_page > 0:
                located.append({
                    "page_idx": existing_page,
                    "text": query,
                    "comment": comment,
                })
                stats["located"] += 1
                continue

            if not query:
                unfound.append(f"(空文本): {comment[:30]}")
                stats["unfound"] += 1
                continue

            # 搜索最佳匹配
            best = self._search(query, text_nodes, min_score, top_k)
            if best:
                page_no = best[0]["page_no"]
                located.append({
                    "page_idx": page_no,
                    "text": query[:200],   # 限制长度，fitz 搜索性能
                    "comment": comment,
                    "_score": round(best[0]["score"], 3),
                })
                stats["located"] += 1
                logger.debug(f"定位成功: page={page_no} score={best[0]['score']:.2f} text={query[:40]!r}")
            else:
                unfound.append(f"page=? text={query[:40]!r}")
                stats["unfound"] += 1
                logger.warning(f"未定位: {query[:50]!r}")

        output_json = json.dumps(located, ensure_ascii=False, indent=2)
        summary = (
            f"共 {stats['total']} 条，"
            f"定位成功 {stats['located']} 条，"
            f"未定位 {stats['unfound']} 条"
        )
        if unfound:
            summary += f"\n未定位条目:\n" + "\n".join(f"  - {u}" for u in unfound[:5])

        logger.info(summary)
        return ToolResult(
            success=stats["located"] > 0,
            output=output_json,
            metadata={
                "json_path": json_path,
                "total": stats["total"],
                "located_count": stats["located"],
                "unfound_count": stats["unfound"],
                "unfound_items": unfound[:10],
            },
        )

    # ------------------------------------------------------------------
    # export 模式：输出文本块供 LLM 选 text_quote
    # ------------------------------------------------------------------

    def _export_texts(self, json_path: str, max_chars: int) -> ToolResult:
        """
        将文档文本块按页整理，输出结构化 JSON，让 checker agent 直接从中选取
        text_quote（保证与 JSON 库内容完全一致，大幅提升后续搜索命中率）。

        输出格式（JSON 字符串）：
          {
            "pages": {
              "1": [
                {"text": "原文片段...（≤max_chars字符）", "label": "section_header"},
                ...
              ],
              "2": [...]
            },
            "total_blocks": 129
          }
        """
        try:
            data = json.load(open(json_path, encoding="utf-8"))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"JSON 加载失败: {e}",
                              metadata={"json_path": json_path})

        nodes = _extract_text_nodes(data)
        # 按页分组
        pages: Dict[int, List[Dict]] = {}
        for node in nodes:
            pg = node["page_no"]
            if pg not in pages:
                pages[pg] = []
            # 文本截取 + Unicode 规范化（与搜索时一致）
            text = normalize(node["text"])
            if len(text) > max_chars:
                text = text[:max_chars] + "…"
            pages[pg].append({"text": text, "label": node.get("label", "text")})

        # 按页码排序
        ordered = {str(pg): pages[pg] for pg in sorted(pages)}
        result = {"pages": ordered, "total_blocks": len(nodes)}
        output_json = json.dumps(result, ensure_ascii=False, indent=2)

        logger.info(f"export_texts: {len(nodes)} 块 / {len(pages)} 页 → json_path={json_path!r}")
        return ToolResult(
            success=True,
            output=output_json,
            metadata={"json_path": json_path, "total_blocks": len(nodes), "total_pages": len(pages)},
        )

    # ------------------------------------------------------------------
    # 内部搜索
    # ------------------------------------------------------------------

    def _search(
        self,
        query: str,
        nodes: List[Dict],
        min_score: float,
        top_k: int,
    ) -> List[Dict]:
        """对 query 在 nodes 中打分，返回最佳 top_k 匹配（score >= min_score）。"""
        scored = []
        for node in nodes:
            s = _score(query, node["text"])
            if s >= min_score:
                scored.append({**node, "score": s})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# 辅助：解析 candidates
# ---------------------------------------------------------------------------

import ast as _ast


def _parse_candidates(raw: Any) -> Tuple[List[Dict], Optional[str]]:
    """将 raw 解析为 [{text_quote, comment}, ...] 列表。"""
    if isinstance(raw, list):
        return raw, None
    if not isinstance(raw, str):
        return [], f"类型不支持: {type(raw)}"

    text = raw.strip()
    # 剥除 markdown 代码块
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(inner).strip()

    # 找 [...]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        text = text[start: end + 1]

    # 尝试 JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed, None
    except json.JSONDecodeError:
        pass

    # 尝试 Python literal（LLM 有时用单引号）
    try:
        parsed = _ast.literal_eval(text)
        if isinstance(parsed, list):
            return parsed, None
    except Exception as e:
        return [], f"解析失败: {e}"

    return [], "未找到有效列表结构"
