"""
ArxivSearchTool：调用 arXiv 官方 HTTP API（Atom），不依赖 arxiv PyPI 包。

API 说明：https://info.arxiv.org/help/api/basics.html
  GET https://export.arxiv.org/api/query?search_query=all:关键词&start=0&max_results=N
"""
from __future__ import annotations

import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tools.base_tool import BaseTool
from core.message import ToolResult
from config.settings import settings
from utils.logger import get_logger
from utils.run_cancel import check_run_cancelled, interruptible_sleep

logger = get_logger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_LOCK = threading.Lock()
_ARXIV_LAST_DONE = 0.0
# 官方 ToU：≥3 秒/次、单连接；略放宽并配合 429 退避
_MIN_GAP_SEC = 4.0
_HTTP_TIMEOUT = 60.0
_429_BACKOFF_SEC = (20.0, 45.0)
_QUERY_MAX = 120
_DEFAULT_QUERY = "LLM autonomous agent"

_FW_PUNCT = re.compile(r"[\u3000-\u303f\uff01-\uffef、，。；：]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN_PHRASE = re.compile(
    r"[A-Za-z][A-Za-z0-9+\-]*(?:\s+[A-Za-z][A-Za-z0-9+\-]*){0,5}"
)


@dataclass(frozen=True)
class ArxivPaper:
    title: str
    abstract: str
    url: str


# ---------- Plan 脏入参清洗（两月前「没问题」因多为用户短句；Plan 会塞 summary） ----------


def _unwrap_json(text: str) -> str:
    body = (text or "").strip()
    if not body.startswith("{"):
        return body
    try:
        obj = json.loads(body)
        if isinstance(obj, dict):
            for k in ("query", "result", "summary"):
                v = obj.get(k)
                if v is not None and str(v).strip():
                    return str(v).strip()
    except json.JSONDecodeError:
        pass
    m = re.search(r'"query"\s*:\s*"(.*)"\s*\}\s*$', body, flags=re.DOTALL)
    if m:
        return m.group(1).replace('\\"', '"').strip()
    return body


def _clean_query(text: str) -> bool:
    q = (text or "").strip()
    if not q or len(q) > _QUERY_MAX or _CJK.search(q) or _FW_PUNCT.search(q):
        return False
    if len(re.findall(r"[A-Za-z]{2,}", q)) > 6 or re.search(r"Agent\s*\d+", q, re.I):
        return False
    return bool(re.search(r"[A-Za-z]{3,}", q))


def _extract_english_segment(text: str) -> str:
    """从「中文（English）」取英文；供 workflow.nodes 解析方向 JSON。"""
    body = (text or "").strip()
    if not body:
        return ""
    m = re.search(r"[（(]([^）)]{3,160})[）)]", body)
    if m and re.search(r"[A-Za-z]", m.group(1)):
        return re.sub(r"\s+", " ", _FW_PUNCT.sub(" ", _CJK.sub(" ", m.group(1)))).strip()
    latin = re.sub(r"\s+", " ", _FW_PUNCT.sub(" ", _CJK.sub(" ", body))).strip(" ,;:")
    return latin if re.search(r"[A-Za-z]", latin) else ""


def _latin_phrases(text: str) -> str:
    for pat in (r'"([^"]{2,60})"', r"'([^']{2,60})'"):
        q = re.findall(pat, text)
        if q:
            return " ".join(q[:4])[:_QUERY_MAX]
    norm = _FW_PUNCT.sub(" ", text)
    skip = {"agent", "use", "memory", "rag", "the", "and", "or"}
    out: List[str] = []
    for c in _LATIN_PHRASE.findall(re.sub(r"\s+", " ", norm)):
        c = c.strip()
        if len(c) < 4 or re.match(r"^Agent\s*\d+\s*$", c, re.I) or re.fullmatch(r"Agent", c, re.I):
            continue
        if c.lower() in skip and " " not in c:
            continue
        if c not in out:
            out.append(c)
    return " ".join(out[:5])[:_QUERY_MAX] if out else ""


def _compress_query(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return _DEFAULT_QUERY
    if _clean_query(body):
        return body
    for line in body.splitlines():
        if "arxiv" in line.lower() or "检索关键词" in line or "检索词" in line:
            q = re.findall(r'"([^"]{2,80})"', line)
            if q:
                return " ".join(q[:4])[:_QUERY_MAX]
    m = re.search(r"[（(]([^）)]{3,160})[）)]", body)
    if m and re.search(r"[A-Za-z]", m.group(1)):
        seg = re.sub(r"\s+", " ", _FW_PUNCT.sub(" ", _CJK.sub(" ", m.group(1)))).strip()
        if _clean_query(seg):
            return seg[:_QUERY_MAX]
        p = _latin_phrases(body)
        if p:
            return p
    p = _latin_phrases(body)
    return p or _DEFAULT_QUERY


def prepare_arxiv_query(raw: Any) -> str:
    if isinstance(raw, dict):
        text = _unwrap_json(str(raw.get("query") or raw.get("result") or raw.get("summary") or ""))
    else:
        text = _unwrap_json(str(raw or ""))
    q = _compress_query(text)
    q = re.sub(r"\s+", " ", _FW_PUNCT.sub(" ", q)).strip()
    if _CJK.search(q):
        q = _latin_phrases(q) or _DEFAULT_QUERY
    return q[:_QUERY_MAX]


# ---------- 官方 API：单次 HTTP，解析 Atom ----------


def _http_get(url: str) -> bytes:
    check_run_cancelled()
    req = Request(url, headers={"User-Agent": "TexAgent/1.0 (arxiv_search; +https://arxiv.org)"})
    with urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read()


def _parse_atom(xml_bytes: bytes) -> List[ArxivPaper]:
    root = ET.fromstring(xml_bytes)
    papers: List[ArxivPaper] = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        title_el = entry.find(f"{{{_ATOM_NS}}}title")
        sum_el = entry.find(f"{{{_ATOM_NS}}}summary")
        id_el = entry.find(f"{{{_ATOM_NS}}}id")
        title = (title_el.text if title_el is not None else "").replace("\n", " ").strip()
        abstract = (sum_el.text if sum_el is not None else "").replace("\n", " ").strip()
        url = (id_el.text if id_el is not None else "").strip()
        if not url:
            for link in entry.findall(f"{{{_ATOM_NS}}}link"):
                if link.get("rel") == "alternate" and link.get("href"):
                    url = link.get("href", "")
                    break
        if title or abstract:
            papers.append(ArxivPaper(title=title, abstract=abstract, url=url))
    return papers


def _search_query_param(words: str) -> str:
    """构造 search_query（官方语法：单词 all:term，短语 all:\"phrase\"）。"""
    w = (words or "").strip() or _DEFAULT_QUERY
    safe = w.replace('"', "").strip()
    if re.search(r"\s", safe):
        return f'all:"{safe}"'
    return f"all:{safe}"


def _api_url(search_words: str, max_results: int) -> str:
    params = {
        "search_query": _search_query_param(search_words),
        "start": 0,
        "max_results": max(1, min(int(max_results), 25)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    return f"{_ARXIV_API}?{urlencode(params)}"


def fetch_arxiv_papers(query: str, max_results: int) -> List[ArxivPaper]:
    """调用 export.arxiv.org，进程内串行 + 最短间隔。query 应为已 prepare 的字符串。"""
    global _ARXIV_LAST_DONE
    words = (query or "").strip() or _DEFAULT_QUERY
    url = _api_url(words, max_results)

    def _once() -> List[ArxivPaper]:
        raw = _http_get(url)
        papers = _parse_atom(raw)
        if not papers:
            raise RuntimeError("未找到相关论文。")
        return papers[:max_results]

    with _ARXIV_LOCK:
        gap = _MIN_GAP_SEC - (time.monotonic() - _ARXIV_LAST_DONE)
        if _ARXIV_LAST_DONE > 0 and gap > 0:
            interruptible_sleep(gap)
        try:
            last_err: Optional[HTTPError] = None
            for attempt in range(1 + len(_429_BACKOFF_SEC)):
                try:
                    return _once()
                except HTTPError as e:
                    if e.code != 429:
                        raise
                    last_err = e
                    if attempt >= len(_429_BACKOFF_SEC):
                        break
                    wait = _429_BACKOFF_SEC[attempt]
                    logger.warning("arXiv 429 限流，%.0fs 后重试 (%s/%s)", wait, attempt + 1, len(_429_BACKOFF_SEC))
                    interruptible_sleep(wait)
            assert last_err is not None
            raise last_err
        finally:
            _ARXIV_LAST_DONE = time.monotonic()


class ArxivSearchTool(BaseTool):
    """arXiv 检索：返回标题、链接、摘要。"""

    def __init__(self, max_results: Optional[int] = None):
        super().__init__(
            name="arxiv_search",
            description=(
                "在 arXiv 检索论文。输入短英文关键词（2~8 词），"
                "返回标题、链接与摘要。同一任务建议只调用一次。"
            ),
            input_schema={
                "query": "关键词或主题（中文请先转为英文）",
            },
        )
        self._max_results = max_results if max_results is not None else settings.arxiv_max_results

    def _brief(self, p: ArxivPaper) -> Dict[str, str]:
        cap = max(80, int(settings.arxiv_abstract_max_chars))
        ab = p.abstract if len(p.abstract) <= cap else p.abstract[:cap] + "..."
        title = p.title[:160] + "..." if len(p.title) > 160 else p.title
        return {"title": title, "url": p.url, "abstract": ab}

    def _format(self, papers: List[ArxivPaper]) -> str:
        lines = [f"共检索到 {len(papers)} 篇（摘要供归纳推荐）：\n"]
        for i, p in enumerate(papers, 1):
            b = self._brief(p)
            lines.append(f"【{i}】{b['title']}")
            if b["url"]:
                lines.append(f"链接：{b['url']}")
            lines.append(f"摘要：{b['abstract']}")
            lines.append("")
        return "\n".join(lines)

    def _format_results(self, papers: List[Any]) -> str:
        """兼容单测：接受 ArxivPaper 或带 title/abstract/url 的对象。"""
        norm = [
            p if isinstance(p, ArxivPaper) else ArxivPaper(
                title=str(getattr(p, "title", "")),
                abstract=str(getattr(p, "summary", getattr(p, "abstract", ""))),
                url=str(getattr(p, "entry_id", getattr(p, "url", ""))),
            )
            for p in papers
        ]
        return self._format(norm)

    def run(self, query: str) -> ToolResult:
        q = prepare_arxiv_query(query)
        logger.info("arXiv 检索 | query=%r | n=%s", q, self._max_results)
        try:
            papers = fetch_arxiv_papers(q, self._max_results)
            out = self._format(papers)
            logger.info("arXiv 完成，%s 篇", len(papers))
            return ToolResult(
                success=True,
                output=out,
                metadata={"query": q, "result_num": len(papers), "papers": [self._brief(p) for p in papers]},
            )
        except KeyboardInterrupt:
            logger.warning("arXiv 检索被用户中断")
            raise
        except (HTTPError, URLError, TimeoutError, RuntimeError, ET.ParseError) as e:
            logger.error("arXiv 检索失败: %s", e)
            hint = ""
            if isinstance(e, HTTPError) and e.code == 429:
                hint = (
                    "（arXiv 官方按 IP 限流：≥3 秒/次。请间隔 2~5 分钟再试；"
                    "勿连点任务。若开 VPN，可换节点或暂时关闭——热门 VPN 出口 IP 更易 429）"
                )
            elif isinstance(e, URLError):
                hint = "（无法连通 export.arxiv.org，检查网络/VPN/防火墙，或稍后重试）"
            return ToolResult(success=False, output="", error=f"{e}{hint}", metadata={"query": q})
