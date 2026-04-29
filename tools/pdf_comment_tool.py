"""
PdfCommentTool：在 PDF 指定位置批量添加高亮和注释。

接口设计（已与 input_schema 对齐，可作为 workflow tool 节点使用）：

  run(pdf_path, annotations, output_path=None)
    - pdf_path:    原始 PDF 路径（绝对路径）
    - annotations: JSON 字符串 或 列表，每项 {page_idx:int, text:str, comment:str}
                   page_idx 从 1 开始（面向用户），内部自动减 1
    - output_path: 输出路径，默认覆盖原文件（与 pdf_path 相同）

上游 agent 节点只需在其 result 字段中输出 JSON 数组，即可通过
  tool_input: "${metadata.<agent_node>.result}"
直接驱动本工具。
"""

import ast
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
from utils.logger import get_logger
from utils.text_normalize import normalize, normalize_for_search

logger = get_logger(__name__)


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


def _fuzzy_search(page, target_text: str) -> list:
    """
    模糊搜索：将页面所有单词提取出来，通过滑动窗口匹配目标文本。
    支持：大小写不敏感 + 去空格字符匹配（解决 OCR 多余空格问题）。
    """
    words = page.get_text("words")   # (x0, y0, x1, y1, word, ...)
    target_words = target_text.split()
    if not target_words:
        return []
    # 去空格后做字符级匹配（对中文最有效）
    target_nospace = re.sub(r'\s+', '', target_text).lower()
    results = []

    # 滑动窗口大小：从 1 到 n，取能覆盖目标长度的最小窗口
    n_words = len(words)
    target_len = len(target_nospace)
    if not target_len:
        return []

    for win_size in range(max(1, len(target_words) - 2), min(n_words, len(target_words) + 6)):
        for i in range(n_words - win_size + 1):
            window_text = re.sub(r'\s+', '', "".join(w[4] for w in words[i: i + win_size])).lower()
            # 目标字符串包含在窗口中 或 窗口包含在目标中（处理长目标被截断的情形）
            if target_nospace in window_text or (
                len(target_nospace) > 6 and window_text in target_nospace and len(window_text) >= len(target_nospace) * 0.7
            ):
                rect = fitz.Rect(words[i][0:4])
                for j in range(i + 1, i + win_size):
                    rect = rect | fitz.Rect(words[j][0:4])
                results.append(rect)
        if results:
            break   # 找到就停，不再扩大窗口

    return results


def _parse_annotations(raw: Any) -> tuple[List[Dict], Optional[str]]:
    """
    将 raw 解析为 [{page_idx, text, comment}] 列表。
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
    PDF 批量注释工具。

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
        {"page_idx": 1, "text": "要高亮的文本片段", "comment": "检查问题说明"},
        {"page_idx": 3, "text": "另一段文本",        "comment": "另一个问题"}
      ]
    注意：page_idx 从 1 开始。
    """

    def __init__(self):
        super().__init__(
            name="pdf_comment",
            description=(
                "在 PDF 中批量添加高亮和注释。"
                "annotations 为 JSON 数组，每项包含 page_idx（从1开始）、"
                "text（要高亮的文本片段）、comment（注释内容）。"
                "output_path 为可选输出路径，不填则覆盖原文件。"
            ),
            input_schema={
                "pdf_path":    "必填，原始 PDF 文件的绝对路径",
                "annotations": (
                    "必填，JSON 数组字符串，每项 {page_idx:int(从1开始), text:str, comment:str, color?:str}。"
                    "color 可选，支持颜色名（yellow/red/green/blue/orange/purple/pink）"
                    "或自动按 comment 中的关键词推断（摘要→黄, 结构→蓝, 语言→绿, 图表→橙, 实验→浅红, 排版→紫）。"
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

            page_idx = item.get("page_idx")
            text = item.get("text")
            if text is None:
                text = item.get("text_quote")
            comment = _clean_comment(item.get("comment"))

            if page_idx is None or text is None:
                continue

            try:
                page_idx = int(page_idx)
            except Exception:
                continue

            text = str(text).strip()
            if not text and not comment:
                continue

            normalized.append(
                {
                    "page_idx": page_idx,
                    "text": text,
                    "comment": comment,
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
            question_list: 与 annotations 二选一或同时提供；字符串/列表，每项含 page_idx、text/text_quote、comment。
            annotations: 同上；工作流里可只传 question_list，此时仅用 coerce 结果标注。
            page_idx 从 1 开始。
            output_path: 输出路径，None 表示覆盖原文件。

        Returns:
            ToolResult，output 包含成功/失败统计和输出路径。
        """
        logger.info(f"PdfCommentTool 执行 | pdf={pdf_path!r}")
        if question_list is None and annotations is not None:
            question_list = annotations
        coerced = self._coerce_question_list(question_list)
        if not coerced:
            return ToolResult(
                success=False,
                output="处理失败",
                error="question_list 为空或格式非法，期望为列表或可解析 JSON",
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
            if same_file:
                temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
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
            # page_idx → [comments] for unfound texts
            page_fallback: Dict[int, List[str]] = {}

            for i, item in enumerate(items, 1):
                try:
                    raw_page = item.get("page_idx")
                    raw_text = item.get("text") or item.get("text_quote") or ""
                    text = str(raw_text).strip()
                    comment = str(item.get("comment", "")).strip()
                    anchor = str(item.get("anchor", "top")).lower()  # top / bottom / margin

                    if raw_page is None or not comment:
                        errors.append(f"[{i}] 缺少必要字段 page_idx/comment")
                        continue

                    # page_idx 从 1 开始 → 内部从 0 开始
                    page_0 = int(raw_page) - 1
                    if not (0 <= page_0 < total_pages):
                        errors.append(f"[{i}] page_idx={raw_page} 超出范围 (共 {total_pages} 页)")
                        continue

                    page = doc[page_0]
                    color_hint = item.get("color") or item.get("color_hint")
                    hl_color = _infer_color(comment, color_hint)

                    # ── 空文本：页边 FreeText（不需要高亮）──────────────────
                    if not text:
                        _add_margin_note(page, layout, page_0, comment, anchor, i)
                        success_count += 1
                        continue

                    # ── Unicode 规范化 + 剔除 Markdown 语法 ──────────────
                    norm_text = normalize(text)
                    # 剔除 docling 生成的 Markdown 标记（## / # / ** / * / ` 等）
                    clean_text = re.sub(r'^#{1,6}\s*', '', norm_text)  # 行首 # 标题
                    clean_text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', clean_text)  # **bold** / *italic*
                    clean_text = re.sub(r'`[^`]*`', '', clean_text).strip()  # `code`
                    
                    # 如果剔除后文本变短，取最长可搜索的核心片段
                    base_text = clean_text if clean_text else norm_text
                    base_text = re.sub(r'\s+', ' ', base_text).strip()

                    # ── 文本搜索（先精确，再模糊）─────────────────────────
                    # 候选策略：整句 + 按标点切分 + 中间片段，减少跨行导致的失败
                    segs = [base_text]
                    segs.extend([s.strip() for s in re.split(r"[，。；：,.!?！？\n]", base_text) if s.strip()])
                    candidates = []
                    for s in segs:
                        if len(s) >= 8:
                            candidates.append(s)
                            # 超长文本截取中段更容易命中
                            if len(s) > 80:
                                mid = len(s) // 2
                                candidates.append(s[max(0, mid - 35): mid + 35])
                    # 去重且按长度降序（先试信息量大的）
                    seen = set()
                    final_candidates = []
                    for c in sorted(candidates, key=len, reverse=True):
                        key = normalize_for_search(c)
                        if key and key not in seen:
                            seen.add(key)
                            final_candidates.append(c)
                    instances = []
                    for cand in final_candidates[:8]:
                        instances = page.search_for(cand)
                        if not instances:
                            instances = _fuzzy_search(page, cand)
                        if instances:
                            search_text = cand  # 仅用于日志
                            break

                    if instances:
                        # 全部命中处高亮；说明合并为一条页边 FreeText，避免重复且不占正文区。
                        note_text = f"[{i}] {comment}".strip() or f"[{i}] 发现潜在问题，建议复核。"
                        hl_union: Optional[fitz.Rect] = None
                        for rect in instances:
                            hl = page.add_highlight_annot(rect)
                            hl.set_colors(stroke=hl_color)
                            hl.update()
                            hl_union = rect if hl_union is None else (hl_union | rect)
                        pref_y = hl_union.y0 if hl_union is not None else 40.0
                        _add_margin_freetext(page, layout, page_0, note_text, hl_union, pref_y, i)
                        logger.debug(f"[{i}] 高亮({hl_color}) '{norm_text[:30]}' @ page {raw_page}")
                    else:
                        # 文本未找到 → 收集到 fallback，页面边角集中注释
                        if page_0 not in page_fallback:
                            page_fallback[page_0] = []
                        page_fallback[page_0].append(f"[{i}] (未找到原文)\n文本: {text!r}\n注释: {comment}")
                        logger.warning(f"[{i}] 未在 page {raw_page} 找到文本: {text[:40]!r}")

                    success_count += 1

                except Exception as e:
                    errors.append(f"[{i}] 处理异常: {e}")

            # 为找不到文本的条目在页面右上角统一添加汇总便签
            for fb_i, (page_0, comments) in enumerate(page_fallback.items()):
                page = doc[page_0]
                combined = "\n\n".join(comments)
                _add_margin_freetext(page, layout, page_0, combined, None, 32.0, 900 + fb_i)

            doc.save(save_path, garbage=4, deflate=True, clean=True)
            doc.close()

            if same_file:
                os.remove(pdf_path)
                shutil.move(temp_path, pdf_path)   # shutil.move 支持跨驱动器
                final_path = pdf_path
            else:
                final_path = output_path

            unfound_total = sum(len(v) for v in page_fallback.values())
            summary = (
                f"已处理 {success_count}/{len(items)} 条注释，"
                f"{unfound_total} 条文本未精确定位（已添加页边汇总批注），"
                f"{len(errors)} 条跳过。\n"
                f"输出文件: {final_path}"
            )
            logger.info(summary)

            return ToolResult(
                success=success_count > 0,
                output=summary,
                metadata={
                    "pdf_path": pdf_path,
                    "output_path": final_path,
                    "total": len(items),
                    "success_count": success_count,
                    "unfound_count": unfound_total,
                    "error_count": len(errors),
                    "errors": errors[:10],   # 最多返回前10条
                },
            )

        except Exception as e:
            traceback.print_exc()
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return ToolResult(
                success=False,
                output="",
                error=f"PDF 处理异常: {e}",
                metadata={"pdf_path": pdf_path},
            )

    # ------------------------------------------------------------------
    # 兼容旧接口（向后兼容，不推荐在 workflow 中使用）
    # ------------------------------------------------------------------

    def run_batch_legacy(
        self,
        pdf_path: str,
        output_path: str,
        question_list: List[Dict],
        author: Optional[str] = None,
    ) -> ToolResult:
        """旧批量接口（向后兼容），内部直接委托给 run()。"""
        return self.run(pdf_path=pdf_path, annotations=question_list, output_path=output_path)
