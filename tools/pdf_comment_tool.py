"""
PdfCommentTool：在 PDF 指定位置批量添加高亮和注释。

接口设计（已与 input_schema 对齐，可作为 workflow tool 节点使用）：

  run(pdf_path, annotations, output_path=None)
    - pdf_path:    原始 PDF 路径（绝对路径）
    - annotations: JSON 字符串 或 列表，每项含 text、comment，以及定位字段（1-based）：
                   - 推荐：page_start + page_end（闭区间），在该页码范围内检索 text；
                   - 兼容：仅 page_idx 时视为单页 [page_idx, page_idx]；单页未命中时在 ±5 页内扩展检索；
                   - 显式多页区间（page_end > page_start）不做 ±5 扩展。
                   同一 PDF 页的词向量解析结果会按页缓存，多批注共享同一页时不会重复 get_text。
    - 文本匹配：先 PyMuPDF 精确 search_for，再子串式窗口匹配；仍失败时对窗口文本与目标做相似度匹配
      （difflib.SequenceMatcher，默认 ratio≥0.9 视为命中），以容忍模型摘录与 PDF 原文的细微差异
    - output_path: 输出路径，默认覆盖原文件（与 pdf_path 相同）

上游 agent 节点只需在其 result 字段中输出 JSON 数组，即可通过
  tool_input: "${metadata.<agent_node>.result}"
直接驱动本工具。
"""

import ast
import difflib
import fitz
import json
import os
import re
import shutil
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

from tools.base_tool import BaseTool
from core.message import ToolResult
from config.settings import settings
from utils.logger import get_logger
import os
import tempfile
import traceback

logger = get_logger(__name__)


def _extract_items_from_parallel_join_blob(text: str) -> List[Any]:
    """
    从 merge_parallel_results 拼接的纯文本中提取各分支「输出:\\n[...]」后的 JSON 数组元素。

    典型形态（parallel_join + passthrough_join）：
        [[OK] abstract_checker]
        摘要: ...
        输出:
        [{...}, ...]

    用于直连 pdf_comment，避免上游 LLM 将超长合并结果再次 JSON 封装后被截断。
    """
    decoder = json.JSONDecoder()
    merged: List[Any] = []
    marker = "输出:"
    pos = 0
    while True:
        i = text.find(marker, pos)
        if i < 0:
            break
        bracket = text.find("[", i + len(marker))
        if bracket < 0:
            pos = i + len(marker)
            continue
        try:
            val, end = decoder.raw_decode(text, bracket)
        except json.JSONDecodeError:
            pos = bracket + 1
            continue
        if isinstance(val, list):
            merged.extend(val)
        pos = end if end > pos else bracket + 1
    return merged


# ---------------------------------------------------------------------------
# 颜色配置：按问题维度分色（RGB 浮点 0-1）
# ---------------------------------------------------------------------------

# 关键词 → 高亮颜色（RGBA）
_COLOR_MAP: List[Tuple[str, Tuple[float, float, float]]] = [
    # 摘要/绪论
    ("摘要",     (1.0, 0.95, 0.2)),   # 亮黄
    ("绪论",     (1.0, 0.95, 0.2)),
    ("abstract", (1.0, 0.95, 0.2)),
    # 章节结构
    ("结构",     (0.5, 0.85, 1.0)),   # 天蓝
    ("章节",     (0.5, 0.85, 1.0)),
    # 语言规范
    ("语言",     (0.5, 1.0, 0.6)),    # 草绿
    ("规范",     (0.5, 1.0, 0.6)),
    # 图表/引用
    ("图表",     (1.0, 0.65, 0.2)),   # 橙色
    ("引用",     (1.0, 0.65, 0.2)),
    # 实验
    ("实验",     (1.0, 0.55, 0.55)),  # 粉红/浅红
    ("experiment",(1.0, 0.55, 0.55)),
    # 排版/公式
    ("排版",     (0.75, 0.55, 1.0)),  # 紫色
    ("公式",     (0.75, 0.55, 1.0)),
    # 通用/其他
    ("参考文献", (1.0, 0.65, 0.2)),
    ("格式",     (0.75, 0.55, 1.0)),
]

_DEFAULT_COLOR = (1.0, 0.92, 0.23)  # 默认：经典黄


def _infer_color(comment: str, color_hint: Optional[str] = None) -> Tuple[float, float, float]:
    """
    从 comment 内容或 color_hint 字段推断高亮颜色。
    优先使用 color_hint（直接颜色名或 RGB），其次按 comment 关键词匹配。
    """
    # 1. 直接 RGB 元组（如 [1.0, 0.5, 0.5]）
    if color_hint:
        try:
            parsed = json.loads(color_hint)
            if isinstance(parsed, (list, tuple)) and len(parsed) == 3:
                return tuple(float(x) for x in parsed)
        except Exception:
            pass
        # 颜色名称
        color_hint_lower = color_hint.lower().strip()
        named = {
            "yellow": (1.0, 0.92, 0.23), "red": (1.0, 0.4, 0.4),
            "green": (0.5, 1.0, 0.6),    "blue": (0.5, 0.85, 1.0),
            "orange": (1.0, 0.65, 0.2),  "purple": (0.75, 0.55, 1.0),
            "pink": (1.0, 0.75, 0.8),    "cyan": (0.4, 0.9, 0.9),
        }
        if color_hint_lower in named:
            return named[color_hint_lower]

    # 2. 按 comment 关键词匹配
    comment_lower = comment.lower()
    for kw, color in _COLOR_MAP:
        if kw.lower() in comment_lower:
            return color

    return _DEFAULT_COLOR


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _has_cjk(s: str) -> bool:
    if not s:
        return False
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def _rects_overlap(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not (a.x1 <= b.x0 or a.x0 >= b.x1 or a.y1 <= b.y0 or a.y0 >= b.y1)


def _inflate_rect(r: fitz.Rect, pad: float) -> fitz.Rect:
    return fitz.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)


def _clamp_rect_on_page(page: fitz.Page, r: fitz.Rect, margin: float = 6.0) -> fitz.Rect:
    pr = page.rect
    x0, y0, x1, y1 = r
    bw, bh = x1 - x0, y1 - y0
    bw = min(bw, pr.width - 2 * margin)
    bh = min(bh, pr.height - 2 * margin)
    x0 = max(margin, min(x0, pr.width - margin - bw))
    y0 = max(margin, min(y0, pr.height - margin - bh))
    return fitz.Rect(x0, y0, x0 + bw, y0 + bh)


def _freetext_font_for_body(text: str) -> str:
    return "china-s" if _has_cjk(text) else "helv"


def _margin_column_width(page: fitz.Page) -> float:
    """正文与纸边之间的窄条宽度（批注只放在此宽度内）。"""
    pr = page.rect
    return min(300.0, max(130.0, pr.width * 0.17))


def _estimate_freetext_height(text: str, box_w: float, fontsize: float) -> float:
    if box_w <= 0:
        return 40.0
    cjk = _has_cjk(text)
    char_w = fontsize * (1.02 if cjk else 0.48)
    cpl = max(5, int(box_w / char_w))
    lines = 0
    for block in text.split("\n"):
        b = block.strip()
        if not b:
            lines += 1
            continue
        lines += max(1, (len(b) + cpl - 1) // cpl)
    return max(26.0, lines * fontsize * 1.36 + 10.0)


class _MarginLayout:
    """记录每页已占用的页边批注框，避免互相遮挡。"""

    def __init__(self) -> None:
        self._occupied: Dict[int, List[fitz.Rect]] = {}

    def _lst(self, page_0: int) -> List[fitz.Rect]:
        if page_0 not in self._occupied:
            self._occupied[page_0] = []
        return self._occupied[page_0]

    def register(self, page_0: int, rect: fitz.Rect, gap: float = 5.0) -> None:
        self._lst(page_0).append(_inflate_rect(rect, gap))

    def conflicts(self, page_0: int, rect: fitz.Rect) -> bool:
        ir = _inflate_rect(rect, 2.0)
        for o in self._lst(page_0):
            if _rects_overlap(ir, o):
                return True
        return False


def _hl_avoid_rect(hl: Optional[fitz.Rect]) -> Optional[fitz.Rect]:
    """与高亮保持间距，批注框不得与此矩形相交。"""
    if hl is None:
        return None
    if (hl.x1 - hl.x0) < 0.5 or (hl.y1 - hl.y0) < 0.5:
        return None
    return _inflate_rect(hl, 6.0)


def _allocate_margin_freetext_rect(
    page: fitz.Page,
    layout: _MarginLayout,
    page_0: int,
    body: str,
    hl_union: Optional[fitz.Rect],
    preferred_y: float,
    slot_index: int,
) -> Tuple[fitz.Rect, float]:
    """
    在左或右页边留白处分配 FreeText 矩形，不压高亮、不与已有页边批注重叠。
    返回 (rect, fontsize)。
    """
    pr = page.rect
    m = 8.0
    bw = _margin_column_width(page)
    bw = min(bw, pr.width * 0.22)
    avoid = _hl_avoid_rect(hl_union)

    center_left = hl_union is not None and hl_union.x0 + hl_union.width * 0.5 < pr.width * 0.48
    sides = ("right", "left") if center_left else ("left", "right")
    if slot_index % 2 == 1:
        sides = (sides[1], sides[0])

    fontsize = 8.6
    for _fs_round in range(14):
        bh = min(pr.height - 2 * m, _estimate_freetext_height(body, bw, fontsize))
        bh = max(bh, 28.0)

        def try_side(side: str) -> Optional[fitz.Rect]:
            x0 = m if side == "left" else pr.width - m - bw

            def bad(r: fitz.Rect) -> bool:
                if layout.conflicts(page_0, r):
                    return True
                if avoid is not None and _rects_overlap(r, avoid):
                    return True
                return False

            y0 = max(m, min(preferred_y, pr.height - m - bh))
            order: List[float] = [y0]
            step = 11.0
            for k in range(1, 100):
                order.append(min(pr.height - m - bh, y0 + k * step))
            for k in range(1, 60):
                yy = y0 - k * step
                if yy >= m:
                    order.append(yy)

            seen_y = set()
            for y in order:
                y = round(max(m, min(y, pr.height - m - bh)), 2)
                if y in seen_y:
                    continue
                seen_y.add(y)
                r = fitz.Rect(x0, y, x0 + bw, y + bh)
                r = _clamp_rect_on_page(page, r, margin=m)
                if not bad(r):
                    return r
            return None

        for side in sides:
            got = try_side(side)
            if got is not None:
                return got, fontsize
        fontsize -= 0.55
        if fontsize < 6.0:
            break

    x0 = m if sides[0] == "left" else pr.width - m - bw
    y0 = m + (slot_index % 7) * 18.0
    r = _clamp_rect_on_page(page, fitz.Rect(x0, y0, x0 + bw, min(bh, pr.height - m - y0)), margin=m)
    return r, max(6.0, fontsize)


def _draw_freetext_in_rect(page: fitz.Page, rect: fitz.Rect, body: str, fontsize: float) -> None:
    """在矩形内写入可见批注（FreeText + china-s；失败则 insert_textbox）。"""
    if not (body or "").strip():
        return
    fontname = _freetext_font_for_body(body)
    try:
        annot = page.add_freetext_annot(
            rect,
            body,
            fontsize=fontsize,
            fontname=fontname,
            text_color=(0.06, 0.06, 0.06),
            fill_color=(0.97, 0.97, 0.82),
            border_width=0.45,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        annot.set_border(width=0.45)
        annot.update()
        return
    except Exception as e:
        logger.warning("add_freetext_annot 失败，尝试 insert_textbox: %s", e)
    try:
        page.draw_rect(rect, color=(0.32, 0.32, 0.32), fill=(0.97, 0.97, 0.82), width=0.4)
        pad = fitz.Rect(rect.x0 + 2, rect.y0 + 2, rect.x1 - 2, rect.y1 - 2)
        page.insert_textbox(
            pad,
            body,
            fontname=fontname,
            fontsize=fontsize,
            color=(0.06, 0.06, 0.06),
            align=fitz.TEXT_ALIGN_LEFT,
        )
    except Exception as e2:
        logger.warning("insert_textbox 回退失败: %s", e2)


def _add_margin_freetext(
    page: fitz.Page,
    layout: _MarginLayout,
    page_0: int,
    body: str,
    hl_union: Optional[fitz.Rect],
    preferred_y: float,
    slot_index: int,
) -> None:
    if not (body or "").strip():
        return
    r, fs = _allocate_margin_freetext_rect(
        page, layout, page_0, body, hl_union, preferred_y, slot_index
    )
    _draw_freetext_in_rect(page, r, body, fs)
    layout.register(page_0, r)


def _add_margin_note(
    page: fitz.Page,
    layout: _MarginLayout,
    page_0: int,
    comment: str,
    anchor: str,
    idx: int,
) -> None:
    """无高亮：批注写在页边留白，纵向错开。"""
    ph = page.rect.height
    if anchor == "bottom":
        py = max(40.0, ph * 0.62)
    elif anchor == "margin":
        py = 48.0 + idx * 36.0
    elif anchor == "right":
        py = 52.0 + idx * 36.0
    else:
        py = 36.0 + idx * 32.0
    _add_margin_freetext(page, layout, page_0, comment, None, py, idx)


# 仅「单页」搜索区间（page_start==page_end 或仅提供 page_idx）未命中时，向两侧扩展的半径
SINGLE_PAGE_FALLBACK_RADIUS = 5

# 精确 search_for 与「子串式」模糊均未命中时，按字符级相似度接受高亮（SequenceMatcher.ratio）
FUZZY_TEXT_MATCH_MIN_RATIO = 0.9


def _union_word_rects(words: List[Any], i: int, win_size: int) -> fitz.Rect:
    rect = fitz.Rect(words[i][0:4])
    for j in range(i + 1, i + win_size):
        rect = rect | fitz.Rect(words[j][0:4])
    return rect


def _fuzzy_search(
    page: fitz.Page,
    target_text: str,
    *,
    min_ratio: float = FUZZY_TEXT_MATCH_MIN_RATIO,
    words: Optional[List[Any]] = None,
) -> list:
    """
    模糊搜索：将页面所有单词提取出来，通过滑动窗口匹配目标文本。
    支持：大小写不敏感 + 去空格字符匹配（解决 OCR 多余空格问题）；
    若仍无子串命中，则用 SequenceMatcher.ratio >= min_ratio（默认 0.9）接受「足够接近」的窗口，
    解决模型摘录与 PDF 原文仅有细微差异时无法高亮的问题。
    """
    if words is None:
        words = page.get_text("words")  # (x0, y0, x1, y1, word, ...)
    else:
        words = words or []
    if not words:
        return []

    target_words = target_text.split()
    target_nospace = re.sub(r"\s+", "", str(target_text)).lower()
    target_len = len(target_nospace)
    if not target_len:
        return []

    n_words = len(words)
    tw = len(target_words)

    # 无空格中文等：split 后只有 1 段，原逻辑窗口过小；按目标字符量扩大窗口上界
    if tw <= 1:
        est = min(n_words, max(6, target_len))
        win_lo = max(1, est // 4)
        win_hi = min(n_words, max(est + 8, target_len + 12), win_lo + 180)
    else:
        win_lo = max(1, tw - 2)
        win_hi = min(n_words, tw + 8)

    # ── 阶段 A：子串 / 长目标截断相容（保持原有行为）────────────────
    for win_size in range(win_lo, win_hi + 1):
        for i in range(n_words - win_size + 1):
            window_text = re.sub(r"\s+", "", "".join(str(w[4]) for w in words[i : i + win_size])).lower()
            if target_nospace in window_text or (
                target_len > 6
                and window_text in target_nospace
                and len(window_text) >= target_len * 0.7
            ):
                return [_union_word_rects(words, i, win_size)]

    # ── 阶段 B：相似度（默认 ratio >= 0.9）───────────────────────────
    if target_len < 6:
        return []

    best_ratio = 0.0
    best_pair: Optional[Tuple[int, int]] = None
    max_len_delta = max(5, int(target_len * 0.38))
    # 大页略降步长，避免极端 PDF 上卡顿
    i_step = 2 if n_words > 900 else 1
    quick_floor = max(0.0, min_ratio - 0.08)

    for win_size in range(win_lo, win_hi + 1):
        upper = n_words - win_size
        if upper < 0:
            continue
        for i in range(0, upper + 1, i_step):
            window_text = re.sub(r"\s+", "", "".join(str(w[4]) for w in words[i : i + win_size])).lower()
            if not window_text:
                continue
            if abs(len(window_text) - target_len) > max_len_delta:
                continue
            sm = difflib.SequenceMatcher(None, target_nospace, window_text)
            if sm.quick_ratio() < quick_floor:
                continue
            r = sm.ratio()
            if r > best_ratio:
                best_ratio = r
                best_pair = (i, win_size)

    if best_pair is not None and best_ratio >= min_ratio:
        i, win_size = best_pair
        logger.debug(
            "pdf_comment 模糊相似度命中 ratio=%.3f win=%d (min=%.2f)",
            best_ratio,
            win_size,
            min_ratio,
        )
        return [_union_word_rects(words, i, win_size)]

    return []


def _page_indices_near_hint(center_0: int, total_pages: int, radius: int) -> List[int]:
    """从 center_0 起由近及远排序的页下标（0-based），含 [center-radius, center+radius] 与文档边界求交。"""
    if total_pages <= 0:
        return []
    lo = max(0, center_0 - radius)
    hi = min(total_pages - 1, center_0 + radius)
    idxs = list(range(lo, hi + 1))
    idxs.sort(key=lambda p: (abs(p - center_0), p))
    return idxs


def _neighbor_pages_excluding_center(center_0: int, total_pages: int, radius: int) -> List[int]:
    """单页检索失败时，在 ±radius 内由近及远扩展的页下标（不含 center 自身）。"""
    return [p for p in _page_indices_near_hint(center_0, total_pages, radius) if p != center_0]


def _clamp_page_span_0(lo0: int, hi0: int, total_pages: int) -> Tuple[int, int]:
    if total_pages <= 0:
        return 0, -1
    lo0 = max(0, min(lo0, total_pages - 1))
    hi0 = max(0, min(hi0, total_pages - 1))
    if lo0 > hi0:
        lo0, hi0 = hi0, lo0
    return lo0, hi0


def _search_text_instances_on_page(
    page: fitz.Page,
    final_candidates: List[str],
    words: Optional[List[Any]] = None,
) -> List[Any]:
    """在给定页上按 final_candidates 依次尝试精确 + 模糊搜索，返回首个非空命中（矩形列表）。"""
    for cand in final_candidates[:8]:
        instances = page.search_for(cand)
        if not instances:
            instances = _fuzzy_search(page, cand, words=words)
        if instances:
            return instances
    return []


def _get_cached_page_words(doc: fitz.Document, page_0: int, cache: Dict[int, List[Any]]) -> List[Any]:
    if page_0 not in cache:
        cache[page_0] = doc[page_0].get_text("words") or []
    return cache[page_0]


def _parse_page_span_from_item(item: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """
    从单条标注 dict 解析 PDF 页码闭区间（1-based inclusive）。
    支持 page_start+page_end、page_range [a,b]、或仅 page_idx（视为单页）。
    """
    pr = item.get("page_range")
    if isinstance(pr, (list, tuple)) and len(pr) >= 2:
        try:
            a, b = int(pr[0]), int(pr[1])
            if a > b:
                a, b = b, a
            return a, b
        except Exception:
            pass
    ps, pe = item.get("page_start"), item.get("page_end")
    if ps is not None and pe is not None:
        try:
            a, b = int(ps), int(pe)
            if a > b:
                a, b = b, a
            return a, b
        except Exception:
            pass
    pi = item.get("page_idx")
    if pi is not None:
        try:
            p = int(pi)
            return p, p
        except Exception:
            pass
    return None


def _margin_body_for_unfound(comment: str, excerpt: str) -> str:
    """未在 PDF 中精确定位原文时：审查意见 + 所针对的摘录文本。"""
    c = (comment or "").strip()
    ex = (excerpt or "").strip()
    if len(ex) > 400:
        ex = ex[:400] + "…"
    if c and ex:
        return f"{c}\n\n针对摘录：{ex}"
    if c:
        return c
    return f"针对摘录：{ex}" if ex else ""


def _parse_annotations(raw: Any) -> tuple[List[Dict], Optional[str]]:
    """
    将 raw 解析为标注 dict 列表（含 page_idx / page_start+page_end 等）。
    支持：list / JSON 字符串 / 带 ```json 包裹的字符串。
    返回 (items, error_msg)，成功时 error_msg=None。
    """
    if isinstance(raw, list):
        return raw, None

    if not isinstance(raw, str):
        return [], f"annotations 类型不支持: {type(raw)}"

    text = raw.strip()
    # 剥除 markdown 代码块标记
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首行 ```json / ``` 和末行 ```
        inner = []
        skip_first = True
        for line in lines:
            if skip_first:
                skip_first = False
                continue
            if line.strip() == "```":
                break
            inner.append(line)
        text = "\n".join(inner).strip()

    # 尝试找到第一个 [ ... ] 块
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start: end + 1]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed, None
        # 有时 LLM 输出 {"annotations": [...]}
        for v in parsed.values():
            if isinstance(v, list):
                return v, None
        return [], "JSON 已解析但未找到列表结构"
    except json.JSONDecodeError:
        pass

    # LLM 有时输出 Python 字面量（单引号 dict），用 ast.literal_eval 兜底
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return parsed, None
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v, None
        return [], "ast.literal_eval 解析成功但未找到列表结构"
    except Exception as e:
        return [], f"JSON 解析失败: {e}"


# ---------------------------------------------------------------------------
# PdfCommentTool
# ---------------------------------------------------------------------------

class PdfCommentTool(BaseTool):
    """
    pdf 注释工具。

    workflow 用法示例（tool 节点配置）：
      {
        "node_type": "tool",
        "tool_name": "pdf_comment",
        "config": {
          "tool_input": {
            "pdf_path":    "E:/path/to/paper.pdf",
            "annotations": "${metadata.checklist_agent.result}",
            "output_path": "E:/path/to/paper_annotated.pdf"
          }
        }
      }

    annotations 格式（由上游 agent 输出的 JSON 数组）：
      [
        {"page_start": 3, "page_end": 12, "text": "要高亮的文本片段", "comment": "检查问题说明"},
        {"page_idx": 5, "text": "另一段文本", "comment": "另一个问题"}
      ]
      page_start/page_end 为 1-based 闭区间；仅 page_idx 时等价于单页区间。
    """

    def __init__(self):
        super().__init__(
            name="pdf_comment",
            description=(
                "在 PDF 中批量添加高亮和注释。"
                "annotations 为 JSON 数组，每项须含 text（要高亮的片段）、comment（审查意见），"
                "以及页码定位：推荐 page_start 与 page_end（1-based 闭区间，在该范围内检索 text）；"
                "或仅 page_idx（视为单页；未命中时向 ±5 页扩展一次）。"
                "显式多页区间（page_end > page_start）不做 ±5 扩展。"
                "output_path 为可选输出路径，不填则覆盖原文件。"
            ),
            input_schema={
                "pdf_path":    "必填，原始 PDF 文件的绝对路径",
                "annotations": (
                    "必填，JSON 数组字符串，每项含 text、comment，及 "
                    "page_start+page_end（1-based 闭区间，检索范围）或 page_idx（单页，兼容旧数据）。"
                    "可选 page_range: [start,end]、color（颜色名或 RGB）、anchor。"
                ),
                "output_path": "可选，带注释的 PDF 输出路径，不填则覆盖原文件",
            }
        )

    # 辅助函数
    def _coerce_question_list(self, question_list):
        """
        兼容：
        - list[dict]
        - JSON 字符串（数组或 {"result":[...]} 或 {"result":"[...]"}）
        - Python 字面量字符串（兜底 ast.literal_eval）
        并将 text_quote 自动映射到 text。
        """
        data = question_list

        def _try_parse_obj(raw):
            try:
                return json.loads(raw)
            except Exception:
                try:
                    return ast.literal_eval(raw)
                except Exception:
                    return None

        def _clean_comment(c):
            if c is None:
                return ""
            s = str(c).strip()
            if not s:
                return ""

            # 整条 comment 被二次 JSON 编码成字符串时，优先 json.loads
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                try:
                    dec = json.loads(s)
                    if isinstance(dec, str):
                        s = dec.strip()
                except json.JSONDecodeError:
                    s = s[1:-1].strip()

            # 仅当尚无 CJK 且含字面量 \\u 转义时再 unicode_escape，避免误伤已是 UTF-8 的中文
            if "\\u" in s and not _has_cjk(s):
                try:
                    s = s.encode("utf-8").decode("unicode_escape")
                except Exception:
                    pass

            s = s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            s = s.replace("\x00", "")
            return s.strip()

        # 1) 首轮解析
        if isinstance(data, str):
            raw = data.strip()
            if not raw:
                return []
            # 并行 join 纯拼接：各分支「输出:」后为合法 JSON 数组，避免再走 LLM 二次封装导致截断
            if "输出:" in raw and ("[[OK]" in raw or "[[FAIL]" in raw):
                blob_items = _extract_items_from_parallel_join_blob(raw)
                if blob_items:
                    data = blob_items
                else:
                    parsed = _try_parse_obj(raw)
                    if parsed is None:
                        return []
                    data = parsed
            else:
                parsed = _try_parse_obj(raw)
                if parsed is None:
                    return []
                data = parsed

        # 2) 若是 dict，优先取 result 字段
        if isinstance(data, dict):
            data = data.get("result", [])

        # 3) result 可能仍是字符串化数组，再解析一次
        if isinstance(data, str):
            parsed2 = _try_parse_obj(data.strip())
            if parsed2 is None:
                return []
            data = parsed2

        if not isinstance(data, list):
            return []

        normalized = []
        for item in data:
            if not isinstance(item, dict):
                continue

            text = item.get("text")
            if text is None:
                text = item.get("text_quote")
            if text is not None:
                text = str(text).strip()
            else:
                text = ""
            comment = _clean_comment(item.get("comment"))

            span = _parse_page_span_from_item(item)
            if span is None:
                continue
            ps, pe = span

            if not text and not comment:
                continue

            normalized.append(
                {
                    "page_start": ps,
                    "page_end": pe,
                    "page_idx": ps,
                    "text": text,
                    "comment": comment,
                    "anchor": str(item.get("anchor", "top")).lower(),
                    "color": item.get("color") or item.get("color_hint"),
                }
            )
        return normalized

    # ------------------------------------------------------------------
    # 公开接口（workflow tool 节点 / 直接调用 均可用）
    # ------------------------------------------------------------------

    def run(
        self,
        pdf_path: str,
        output_path: Optional[str] = None,
        question_list=None,
        author=None,
        annotations: Union[str, List[Dict]] = None,
    ) -> ToolResult:
        """
        批量高亮 PDF 文本并添加注释。

        Args:
            pdf_path:    原始 PDF 路径。
            question_list: 与 annotations 二选一或同时提供；字符串/列表，每项含
                page_start+page_end（闭区间）或 page_idx（单页）、text/text_quote、comment。
            annotations: 同上；工作流里可只传 question_list，此时仅用 coerce 结果标注。
            页码均为 1-based。
            output_path: 输出路径，None 表示覆盖原文件。

        Returns:
            ToolResult，output 包含成功/失败统计和输出路径。
        """
        logger.info(f"PdfCommentTool 执行 | pdf={pdf_path!r}")
        if question_list is None and annotations is not None:
            question_list = annotations
        coerced = self._coerce_question_list(question_list)
        if not coerced:
            err = "question_list 为空或格式非法，期望为列表或可解析 JSON"
            if isinstance(question_list, str) and len(question_list) > 6000:
                err += "。若输入为超长字符串，常见原因是上游格式化节点 LLM 输出被截断（JSON 不完整）；请增大该节点的 max_tokens 或缩短合并列表。"
            return ToolResult(
                success=False,
                output="处理失败",
                error=err,
            )
        items: List[Dict] = []
        if annotations is not None:
            parsed, parse_err = _parse_annotations(annotations)
            if not parse_err and parsed:
                items = self._coerce_question_list(parsed)
        if not items:
            items = coerced
        if not items:
            return ToolResult(
                success=False,
                output="处理失败",
                error="无法得到有效的标注列表",
                metadata={"pdf_path": pdf_path},
            )
        if not output_path:
            output_path = pdf_path

        # 执行批量注释
        return self._batch_annotate(pdf_path, output_path, items)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _batch_annotate(
        self,
        pdf_path: str,
        output_path: str,
        items: List[Dict],
    ) -> ToolResult:
        same_file = os.path.abspath(pdf_path) == os.path.abspath(output_path)
        temp_path = None
        
        try:
            # 如果是同一个文件，创建临时文件
            if same_file:
                temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf')
                os.close(temp_fd)
                save_path = temp_path
            else:
                save_path = output_path
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            layout = _MarginLayout()
            success_count = 0
            errors: List[str] = []
            page_fallback: Dict[int, List[str]] = {}
            words_cache: Dict[int, List[Any]] = {}

            for i, item in enumerate(items, 1):
                try:
                    span = _parse_page_span_from_item(item)
                    if span is None:
                        errors.append(f"[{i}] 缺少有效页码（page_start/page_end、page_range 或 page_idx）")
                        continue
                    ps, pe = span
                    raw_text = item.get("text") or item.get("text_quote") or ""
                    text = str(raw_text).strip()
                    comment = str(item.get("comment", "")).strip()
                    anchor = str(item.get("anchor", "top")).lower()

                    lo0, hi0 = _clamp_page_span_0(ps - 1, pe - 1, total_pages)
                    if lo0 > hi0:
                        errors.append(f"[{i}] 页码区间无效")
                        continue
                    if not comment:
                        errors.append(f"[{i}] 缺少 comment")
                        continue

                    single_page_span = ps == pe
                    anchor_page_0 = lo0
                    page = doc[anchor_page_0]
                    color_hint = item.get("color") or item.get("color_hint")
                    hl_color = _infer_color(comment, color_hint)

                    if not text:
                        _add_margin_note(page, layout, anchor_page_0, comment, anchor, i)
                        success_count += 1
                        continue

                    norm_text = normalize(text)
                    clean_text = re.sub(r'^#{1,6}\s*', '', norm_text)
                    clean_text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', clean_text)
                    clean_text = re.sub(r'`[^`]*`', '', clean_text).strip()

                    base_text = clean_text if clean_text else norm_text
                    base_text = re.sub(r'\s+', ' ', base_text).strip()

                    segs = [base_text]
                    segs.extend([s.strip() for s in re.split(r"[，。；：,.!?！？\n]", base_text) if s.strip()])
                    candidates = []
                    for s in segs:
                        if len(s) >= 8:
                            candidates.append(s)
                            if len(s) > 80:
                                mid = len(s) // 2
                                candidates.append(s[max(0, mid - 35): mid + 35])
                    seen = set()
                    final_candidates = []
                    for c in sorted(candidates, key=len, reverse=True):
                        key = normalize_for_search(c)
                        if key and key not in seen:
                            seen.add(key)
                            final_candidates.append(c)
                    instances: List[Any] = []
                    draw_page_0 = anchor_page_0

                    def try_pages(pages_list: List[int]) -> bool:
                        nonlocal instances, draw_page_0, page
                        for pg in pages_list:
                            if not (0 <= pg < total_pages):
                                continue
                            probe = doc[pg]
                            w = _get_cached_page_words(doc, pg, words_cache)
                            found = _search_text_instances_on_page(probe, final_candidates, words=w)
                            if found:
                                instances = found
                                draw_page_0 = pg
                                page = probe
                                return True
                        return False

                    primary_pages = list(range(lo0, hi0 + 1))
                    try_pages(primary_pages)

                    if not instances and single_page_span:
                        try_pages(
                            _neighbor_pages_excluding_center(
                                lo0, total_pages, SINGLE_PAGE_FALLBACK_RADIUS
                            )
                        )

                    if instances:
                        note_text = comment.strip() or "发现潜在问题，建议复核。"
                        hl_union: Optional[fitz.Rect] = None
                        for rect in instances:
                            hl = page.add_highlight_annot(rect)
                            hl.set_colors(stroke=hl_color)
                            hl.update()
                            hl_union = rect if hl_union is None else (hl_union | rect)
                        pref_y = hl_union.y0 if hl_union is not None else 40.0
                        _add_margin_freetext(page, layout, draw_page_0, note_text, hl_union, pref_y, i)
                        logger.debug(
                            "[%s] 高亮(%s) %r @ page %s",
                            i,
                            hl_color,
                            norm_text[:30],
                            draw_page_0 + 1,
                        )
                    else:
                        if anchor_page_0 not in page_fallback:
                            page_fallback[anchor_page_0] = []
                        page_fallback[anchor_page_0].append(_margin_body_for_unfound(comment, text))
                        logger.warning(
                            "[%s] 页码区间 %s–%s 内未找到文本: %r",
                            i,
                            ps,
                            pe,
                            text[:60],
                        )

                    success_count += 1
                    commented_pages.add(page_idx + 1)
                    print(f"✅ 已处理问题 {i+1}")
                    
                except Exception as e:
                    errors.append(f"[{i}] 处理异常: {e}")

            # 为找不到文本的条目在页面右上角统一添加汇总便签
            for fb_i, (page_0, comments) in enumerate(page_fallback.items()):
                page = doc[page_0]
                combined = "\n\n".join(comments)
                _add_margin_freetext(page, layout, page_0, combined, None, 32.0, 900 + fb_i)

            doc.save(save_path, garbage=4, deflate=True, clean=True)
            doc.close()
            
            # 如果是同一个文件，用临时文件替换原文件
            if same_file:
                os.remove(pdf_path)
                shutil.move(temp_path, pdf_path)   # shutil.move 支持跨驱动器
                final_path = pdf_path
            else:
                final_path = output_path

            unfound_total = sum(len(v) for v in page_fallback.values())
            summary = (
                f"已处理 {success_count}/{len(items)} 条注释，"
                f"{unfound_total} 条文本未在给定页码范围内精确定位（已添加页边汇总批注），"
                f"{len(errors)} 条跳过。\n"
                f"输出文件: {final_path}"
            )
            logger.info(summary)

            return ToolResult(
                success=success_count > 0,
                output=output_message,
                metadata={
                    "success_count": success_count,
                    "unfound_count": unfound_total,
                    "error_count": len(errors),
                    "errors": errors[:10],   # 最多返回前10条
                },
            )
            
        except Exception as e:
            traceback.print_exc()
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return ToolResult(
                success=False,
                output="处理失败",
                error=f"批量处理 PDF 时出错: {str(e)}",
            )


if __name__ == "__main__":
    tool = PdfCommentTool()
    
    # 测试单个标注
    # tool.run(
    #     pdf_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
    #     output_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
    #     page_idx=0,
    #     text="AutoGen",
    #     comment="这是一个注释",
    #     author="TestUser",
    # )
    
    # 测试批量标注
    question_list = [
        {
            "page_idx": 0,
            "text": "TEST",
            "comment": "这是第一个注释"
        },
        {
            "page_idx": 0,
            "text": "Framework",
            "comment": "这是第二个注释"
        }
    ]
    
    tool.run(
        pdf_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
        output_path=r"C:/Users/86138/Downloads/AutoGen Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework_copy.pdf",
        question_list=question_list,
        author="TestUser"
    )
