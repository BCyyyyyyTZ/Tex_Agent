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
from datetime import datetime
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

_ANCHOR_POSITIONS = {
    "top":    (30, 40),
    "bottom": (30, -60),    # 相对于页面底部（在 _add_margin_note 中特殊处理）
    "margin": (-20, 200),   # 页面左侧页边
    "right":  (1000, 200),  # 页面右侧（大数值，会被 _add_margin_note 修正到页面右边）
}


def _add_margin_note(page, comment: str, anchor: str = "top", idx: int = 0) -> None:
    """在页面边角/空白处添加文本便签（不含高亮）。"""
    pw, ph = page.rect.width, page.rect.height
    if anchor == "bottom":
        x, y = 30, ph - 60
    elif anchor == "margin":
        x, y = 8, min(200 + idx * 25, ph - 30)
    elif anchor == "right":
        x, y = pw - 30, min(200 + idx * 25, ph - 30)
    else:  # top
        x, y = 30, min(40 + idx * 20, ph // 2)
    pt = fitz.Point(x, y)
    note = page.add_text_annot(pt, comment, icon="Comment")
    note.set_info(content=comment)
    note.update()


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

    # ------------------------------------------------------------------
    # 公开接口（workflow tool 节点 / 直接调用 均可用）
    # ------------------------------------------------------------------

    def run(
        self,
        pdf_path: str,
        annotations: Union[str, List[Dict]],
        output_path: Optional[str] = None,
    ) -> ToolResult:
        """
        批量高亮 PDF 文本并添加注释。

        Args:
            pdf_path:    原始 PDF 路径。
            annotations: JSON 数组或 Python 列表，每项 {page_idx, text, comment}。
                         page_idx 从 1 开始。
            output_path: 输出路径，None 表示覆盖原文件。

        Returns:
            ToolResult，output 包含成功/失败统计和输出路径。
        """
        logger.info(f"PdfCommentTool 执行 | pdf={pdf_path!r}")

        # 1. 解析 annotations
        items, parse_err = _parse_annotations(annotations)
        if parse_err:
            return ToolResult(
                success=False,
                output="",
                error=f"annotations 解析失败: {parse_err}",
                metadata={"pdf_path": pdf_path},
            )
        if not items:
            return ToolResult(
                success=False,
                output="",
                error="annotations 为空列表，无需处理",
                metadata={"pdf_path": pdf_path},
            )

        if not output_path:
            output_path = pdf_path

        # 2. 执行批量注释
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
            now = datetime.now()
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

                    # ── 空文本：直接添加页边便签（不需要高亮）──────────────
                    if not text:
                        _add_margin_note(page, comment, anchor, i)
                        success_count += 1
                        continue

                    # ── Unicode 规范化 + 剔除 Markdown 语法 ──────────────
                    norm_text = normalize(text)
                    # 剔除 docling 生成的 Markdown 标记（## / # / ** / * / ` 等）
                    clean_text = re.sub(r'^#{1,6}\s*', '', norm_text)  # 行首 # 标题
                    clean_text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', clean_text)  # **bold** / *italic*
                    clean_text = re.sub(r'`[^`]*`', '', clean_text)  # `code`
                    clean_text = clean_text.strip()
                    # 如果剔除后文本变短，取最长可搜索的核心片段
                    search_text = clean_text if clean_text else norm_text

                    # ── 文本搜索（先精确，再模糊）─────────────────────────
                    instances = page.search_for(search_text)
                    if not instances and search_text != norm_text:
                        instances = page.search_for(norm_text)
                    if not instances and norm_text != text:
                        instances = page.search_for(text)   # 原始文本兜底
                    if not instances:
                        instances = _fuzzy_search(page, search_text)
                    if not instances and search_text != norm_text:
                        instances = _fuzzy_search(page, norm_text)

                    if instances:
                        for rect in instances:
                            hl = page.add_highlight_annot(rect)
                            hl.set_colors(stroke=hl_color)
                            hl.set_info(content=f"[{i}] {comment}")
                            hl.update()
                            note_pt = fitz.Point(rect.x1 + 8, rect.y0)
                            note = page.add_text_annot(note_pt, comment, icon="Note")
                            note.set_info(content=comment)
                            note.update()
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
            for page_0, comments in page_fallback.items():
                page = doc[page_0]
                combined = "\n\n".join(comments)
                # 摆在右上角，避免遮挡正文
                pt = fitz.Point(page.rect.width - 30, 40)
                note = page.add_text_annot(pt, combined, icon="Note")
                note.set_info(content=combined)

            doc.save(save_path, garbage=4, deflate=True, clean=True)
            doc.close()

            if same_file:
                os.remove(pdf_path)
                shutil.move(temp_path, pdf_path)   # shutil.move 支持跨驱动器
                final_path = pdf_path
            else:
                final_path = output_path

            summary = (
                f"已处理 {success_count}/{len(items)} 条注释，"
                f"{len(page_fallback)} 条文本未精确定位（已添加汇总便签），"
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
                    "unfound_count": sum(len(v) for v in page_fallback.values()),
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
