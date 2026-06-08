"""
基于 PDF 书签（outline）的学位论文文字提取。

使用 pypdf 读取目录与页码，pdfplumber 按页取正文，按章节树输出 Markdown；
并生成与 Docling 结构兼容的 document.json，便于 docling_search 等下游工具复用。

依赖：pypdf、pdfplumber（见项目 requirements.txt）。
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class ChapterNode:
    def __init__(self, title: str, page: int, depth: int = 0):
        self.title = title
        self.page = page
        self.depth = depth
        self.number = extract_chapter_number(title)
        self.children: List[ChapterNode] = []
        self.end_page: int | None = None
        self.text = ""
        # 选择器命中信息（仅在被 select_nodes_by_chapters 命中时被赋值）。
        self.match_reason: str | None = None
        self.match_input: str | None = None
        self.ordinal_path: Tuple[int, ...] | None = None


def build_outline_tree(reader, items, depth=0):
    """递归构建目录树。"""
    nodes: List[ChapterNode] = []
    for item in items:
        if isinstance(item, list):
            if nodes:
                nodes[-1].children = build_outline_tree(reader, item, depth + 1)
        else:
            page = reader.get_destination_page_number(item)
            nodes.append(ChapterNode(item.title, page, depth))
    return nodes


def build_outline_tree_from_toc(toc: Iterable[List[Any]]) -> List[ChapterNode]:
    """
    从 PyMuPDF 的 get_toc() 结果构建目录树。

    toc 行结构一般为 [level(1-based), title, page(1-based), ...]
    """
    roots: List[ChapterNode] = []
    stack: List[ChapterNode] = []
    for row in toc:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        try:
            level = max(1, int(row[0]))
            title = str(row[1] or "").strip()
            page_1_based = int(row[2] or 1)
        except Exception:
            continue
        if not title:
            continue
        node = ChapterNode(title=title, page=max(0, page_1_based - 1), depth=level - 1)
        while stack and stack[-1].depth >= node.depth:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def flatten_nodes(nodes, result):
    """前序遍历展平节点，用于计算 end_page。"""
    for n in nodes:
        result.append(n)
        flatten_nodes(n.children, result)
    return result


def compute_end_pages(flat_nodes, total_pages):
    """计算每个章节的结束页（不包含）。"""
    for i, n in enumerate(flat_nodes):
        j = i + 1
        while j < len(flat_nodes) and flat_nodes[j].depth > n.depth:
            j += 1
        if j < len(flat_nodes):
            n.end_page = flat_nodes[j].page
        else:
            n.end_page = total_pages


def extract_pages_text(pdf_path, start, end):
    """使用 pdfplumber 提取 [start, end) 页的文字，并移除页码行。"""
    import pdfplumber

    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        max_end = min(int(end), len(pdf.pages))
        for p in range(int(start), max(int(start), max_end)):
            page = pdf.pages[p]
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
            if lines and re.match(r"^[IVXivx\d]+$", lines[-1].strip()):
                lines = lines[:-1]
            texts.append("\n".join(lines))
    return "\n".join(texts)


def normalize_text(s: str) -> str:
    return s.replace(" ", "").replace("\u3000", "").replace("\n", "")


_CH_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*$")
_TITLE_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)")
_CN_CHAPTER_RE = re.compile(r"第\s*([一二三四五六七八九十百千万零两\d]+)\s*[章节篇]", flags=re.IGNORECASE)
_CN_CHAPTER_ROMAN_RE = re.compile(r"第\s*([IVXLCDMivxlcdm]+)\s*[章节篇]")
_EN_CHAPTER_RE = re.compile(r"chapter\s+(\d+)", flags=re.IGNORECASE)
_EN_CHAPTER_ROMAN_RE = re.compile(r"chapter\s+([IVXLCDM]+)", flags=re.IGNORECASE)
_ROMAN_TITLE_RE = re.compile(
    r"^([IVXLCDMivxlcdm]{1,5})(?:[\.\)、:：]|\s+(?=[\u4e00-\u9fa5A-Za-z\d]))",
)
_LETTER_TITLE_RE = re.compile(r"^([A-Z])[\.\)、:：](?:\s|$)")
_CN_BRACKET_NUM_RE = re.compile(r"^[（\(]\s*([一二三四五六七八九十百千万零两\d]+)\s*[）\)]")
_TAIL_SECTION_WORDS_RE = re.compile(r"(?:这一|这)?(?:章节|小节|节|部分)\s*$", flags=re.IGNORECASE)
_TITLE_PREFIX_RE = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百千万零两\d]+\s*[章节篇]\s*|"
    r"第\s*[IVXLCDMivxlcdm]+\s*[章节篇]\s*|"
    r"chapter\s+(?:\d+(?:\.\d+)*|[IVXLCDM]+)\s*|"
    r"\d+(?:\.\d+)*\s*[\.、:：\-\s]*|"
    r"[IVXLCDMivxlcdm]+\s*[\.\)、:：]\s*|"
    r"[A-Z]\s*[\.\)、:：]\s*)",
    flags=re.IGNORECASE,
)

_SPECIAL_TITLE_ALIASES: Dict[str, List[str]] = {
    "摘要": ["摘要", "中文摘要", "摘 要"],
    "英文摘要": ["英文摘要", "english abstract", "abstract"],
    "abstract": ["abstract", "英文摘要"],
    "参考文献": ["参考文献", "references", "bibliography"],
    "致谢": ["致谢", "鸣谢", "acknowledgements", "acknowledgments"],
}

ALL_CHAPTERS_TOKEN = "*"
_FULLTEXT_NORM_ALIASES: Set[str] = {
    "全文",
    "全部",
    "整篇",
    "整本",
    "整篇论文",
    "整本论文",
    "全部章节",
    "所有章节",
    "全部内容",
    "所有内容",
    "全篇",
    "通篇",
    "尽全文",
    "从头到尾",
    "整篇文章",
    "整本文档",
    "整部论文",
    "整份论文",
    "整套论文",
    "完整论文",
    "完整文档",
    "全部段落",
    "整个文档",
    "每一章",
    "各个章节",
    "所有小节",
    "all",
    "everything",
    "entire",
    "whole",
    "fulltext",
    "fulldocument",
    "fullpaper",
    "wholedocument",
    "entiredocument",
    "completedocument",
    "thewholedocument",
    "theentiredocument",
    "thecompletethesis",
    "thecompletepaper",
    "parseentire",
    "everychapter",
    "allchapters",
}

_UNICODE_ROMAN_MAP: Dict[str, str] = {
    "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
    "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
    "Ⅺ": "XI", "Ⅻ": "XII",
    "ⅰ": "i", "ⅱ": "ii", "ⅲ": "iii", "ⅳ": "iv", "ⅴ": "v",
    "ⅵ": "vi", "ⅶ": "vii", "ⅷ": "viii", "ⅸ": "ix", "ⅹ": "x",
}

_FRONT_BACK_MATTER_NORMS: Set[str] = {
    # 前置
    "封面", "扉页", "独创性声明", "原创性声明", "学位论文原创性声明",
    "学位论文版权使用授权书", "学位论文使用授权书", "授权书",
    "中文摘要", "摘要", "英文摘要", "abstract", "englishabstract",
    "目录", "contents", "图目录", "表目录", "图表目录", "符号说明", "缩略词",
    "关键词", "keywords",
    # 后置
    "参考文献", "references", "bibliography",
    "致谢", "鸣谢", "acknowledgements", "acknowledgments",
    "附录", "appendix",
    "个人简历", "作者简介", "在学期间发表的论文",
    "攻读硕士学位期间发表的成果", "攻读博士学位期间发表的成果",
    "攻读学位期间的研究成果",
}


def _normalize_unicode_chars(s: str) -> str:
    """统一全角字符/罗马 unicode 编码，便于后续 ASCII 正则匹配。"""
    if not s:
        return s
    out: List[str] = []
    for ch in s:
        if ch in _UNICODE_ROMAN_MAP:
            out.append(_UNICODE_ROMAN_MAP[ch])
            continue
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19:  # 全角数字
            out.append(chr(code - 0xFEE0))
        elif 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:  # 全角字母
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _roman_to_int(token: str) -> int | None:
    text = (token or "").strip().upper()
    if not text or len(text) > 7:
        return None
    if not re.fullmatch(r"[IVXLCDM]+", text):
        return None
    table = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(text):
        val = table[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total if total > 0 else None


def _letter_to_int(token: str) -> int | None:
    text = (token or "").strip()
    if len(text) != 1:
        return None
    upper = text.upper()
    if "A" <= upper <= "Z":
        return ord(upper) - ord("A") + 1
    return None


def _cn_to_int(token: str) -> int | None:
    text = str(token or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    num_map = {
        "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    unit_map = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    current = 0
    for ch in text:
        if ch in num_map:
            current = num_map[ch]
            continue
        if ch in unit_map:
            unit = unit_map[ch]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
    total += current
    return total if total > 0 else None


def extract_chapter_number(title: str) -> str:
    raw = str(title or "").strip()
    if not raw:
        return ""
    t = _normalize_unicode_chars(raw)
    m = _TITLE_NUMBER_RE.match(t)
    if m:
        return m.group(1)
    m = _CN_BRACKET_NUM_RE.match(t)
    if m:
        n = _cn_to_int(m.group(1))
        if n:
            return str(n)
    m = _CN_CHAPTER_RE.search(t)
    if m:
        n = _cn_to_int(m.group(1))
        if n:
            return str(n)
    m = _CN_CHAPTER_ROMAN_RE.search(t)
    if m:
        n = _roman_to_int(m.group(1))
        if n:
            return str(n)
    m = _EN_CHAPTER_RE.search(t)
    if m:
        return str(int(m.group(1)))
    m = _EN_CHAPTER_ROMAN_RE.search(t)
    if m:
        n = _roman_to_int(m.group(1))
        if n:
            return str(n)
    m = _ROMAN_TITLE_RE.match(t)
    if m:
        n = _roman_to_int(m.group(1))
        if n:
            return str(n)
    m = _LETTER_TITLE_RE.match(t)
    if m:
        n = _letter_to_int(m.group(1))
        if n:
            return str(n)
    return ""


def normalize_chapter_selector(selector: str) -> str:
    text = str(selector or "").strip()
    if not text:
        return ""
    text = text.strip("[]()（）\"'“”‘’")
    text = _normalize_unicode_chars(text)
    # 全文哨兵：先于其他归一化判定，避免被裁剪。
    flat = normalize_text(text).lower()
    if flat in _FULLTEXT_NORM_ALIASES:
        return ALL_CHAPTERS_TOKEN
    text = _TAIL_SECTION_WORDS_RE.sub("", text)
    text = text.rstrip("的")
    text = text.replace("～", "-").replace("—", "-").replace("到", "-").replace("至", "-")
    if _CH_NUMBER_RE.match(text):
        return text
    # 多级混合编号：罗马/字母 + .数字。例如 "III.2" / "A.2"。
    m_mix = re.match(r"^([IVXLCDMivxlcdm]+|[A-Za-z])\s*\.\s*(\d+(?:\.\d+)*)$", text)
    if m_mix:
        head = _roman_to_int(m_mix.group(1)) or _letter_to_int(m_mix.group(1))
        if head:
            return f"{head}.{m_mix.group(2)}"
    n = extract_chapter_number(text)
    if n:
        return n
    # 单个罗马/字母 token（如 "III"、"A"）
    roman = _roman_to_int(text)
    if roman is not None:
        return str(roman)
    letter = _letter_to_int(text)
    if letter is not None:
        return str(letter)
    return normalize_text(text).lower()


def _normalize_title_for_matching(title: str) -> str:
    t = str(title or "").strip()
    if not t:
        return ""
    t = _normalize_unicode_chars(t)
    t = _TITLE_PREFIX_RE.sub("", t).strip()
    t = _TAIL_SECTION_WORDS_RE.sub("", t).strip().rstrip("的")
    return normalize_text(t).lower()


def _is_front_back_matter(title: str) -> bool:
    """识别"摘要 / 目录 / 参考文献 / 致谢 / 附录"等前后置内容，用于序数兜底过滤。"""
    if not title:
        return False
    t = _normalize_unicode_chars(str(title))
    t = _TITLE_PREFIX_RE.sub("", t).strip()
    norm = normalize_text(t).lower()
    if not norm:
        return False
    if norm in _FRONT_BACK_MATTER_NORMS:
        return True
    # 附录 A / 附录B / Appendix C
    if norm.startswith("附录") or norm.startswith("appendix"):
        return True
    return False


def _parse_ordinal_path(token: str) -> Tuple[int, ...] | None:
    """把 "1.1.2" / "第三章" / "III" / "A" 之类归一化为整数元组路径。"""
    normalized = normalize_chapter_selector(token)
    if not normalized or normalized == ALL_CHAPTERS_TOKEN:
        return None
    if not _CH_NUMBER_RE.match(normalized):
        return None
    try:
        parts = tuple(int(x) for x in normalized.split("."))
    except ValueError:
        return None
    if not parts or any(p <= 0 for p in parts):
        return None
    return parts


def _pick_by_ordinal_path(
    tree: List["ChapterNode"],
    path: Tuple[int, ...],
) -> "ChapterNode | None":
    """按层级序数沿目录树取节点；首层会自动跳过前后置内容。"""
    if not path:
        return None
    current_layer: List[ChapterNode] = list(tree or [])
    chosen: ChapterNode | None = None
    for level, idx in enumerate(path):
        if level == 0:
            layer = [n for n in current_layer if not _is_front_back_matter(n.title)]
        else:
            layer = current_layer
        if idx < 1 or idx > len(layer):
            return None
        chosen = layer[idx - 1]
        current_layer = list(chosen.children)
    return chosen


def _split_selector_tokens(chapters: str | List[str] | Tuple[str, ...]) -> List[str]:
    if isinstance(chapters, (list, tuple)):
        raw = [str(x or "").strip() for x in chapters]
        return [x for x in raw if x]
    text = str(chapters or "").strip()
    if not text:
        return []
    # 尝试解析 JSON 数组字符串
    if text.startswith("[") and text.endswith("]"):
        try:
            import json
            arr = json.loads(text)
            if isinstance(arr, list):
                return [str(x or "").strip() for x in arr if str(x or "").strip()]
        except Exception:
            pass
    parts = re.split(r"[,\n;；、+]+", text)
    return [p.strip() for p in parts if p.strip()]


def _build_match_indexes(flat_nodes: List[ChapterNode]) -> Tuple[Dict[str, ChapterNode], Dict[str, List[ChapterNode]]]:
    by_number: Dict[str, ChapterNode] = {}
    by_norm_title: Dict[str, List[ChapterNode]] = {}
    for node in flat_nodes:
        if node.number:
            by_number[node.number] = node
        norm_title = normalize_text(node.title).lower()
        by_norm_title.setdefault(norm_title, []).append(node)
        compact_title = _normalize_title_for_matching(node.title)
        if compact_title:
            by_norm_title.setdefault(compact_title, []).append(node)
    return by_number, by_norm_title


def select_nodes_by_chapters(
    tree: List[ChapterNode],
    chapters: str | List[str] | Tuple[str, ...],
) -> Tuple[List[ChapterNode], List[str]]:
    """
    根据章节选择器从目录树中选节点，支持：
    - 单项：3 / 3.1 / 第三章 / Chapter 3 / 标题 / III / A. / 全文
    - 范围：3.1-3.3
    - 多项分隔：, ; 、 + 换行

    命中节点会被设置 ``match_reason / match_input / ordinal_path`` 属性，便于上层观察。
    """
    tokens = _split_selector_tokens(chapters)
    if not tokens:
        return [], []

    # 全文哨兵：任一 token 归一化后是 ALL → 返回全部根节点。
    for raw in tokens:
        if normalize_chapter_selector(raw) == ALL_CHAPTERS_TOKEN:
            roots: List[ChapterNode] = list(tree)
            for node in roots:
                node.match_reason = "all"
                node.match_input = raw
                node.ordinal_path = None
            return roots, []

    flat: List[ChapterNode] = []
    flatten_nodes(tree, flat)
    by_number, by_norm_title = _build_match_indexes(flat)
    index_map = {id(n): i for i, n in enumerate(flat)}

    selected: Dict[int, ChapterNode] = {}
    unresolved: List[str] = []

    def _annotate(
        node: ChapterNode,
        *,
        reason: str,
        input_token: str,
        ordinal_path: Tuple[int, ...] | None = None,
    ) -> ChapterNode:
        node.match_reason = reason
        node.match_input = input_token
        node.ordinal_path = ordinal_path
        return node

    def _match_one(token: str) -> ChapterNode | None:
        normalized = normalize_chapter_selector(token)
        if not normalized:
            return None
        if normalized in by_number:
            return _annotate(by_number[normalized], reason="number", input_token=token)
        for alias in _SPECIAL_TITLE_ALIASES.get(normalized, []):
            alias_norm = _normalize_title_for_matching(alias)
            matched_alias = by_norm_title.get(alias_norm, [])
            if matched_alias:
                return _annotate(matched_alias[0], reason="alias", input_token=token)
        matched = by_norm_title.get(normalized, [])
        if matched:
            return _annotate(matched[0], reason="title", input_token=token)
        # 若 token 形如 "1.1研究背景"，优先按章节号匹配到 1.1 节
        m = re.match(r"^(\d+(?:\.\d+)+)", normalized)
        if m and m.group(1) in by_number:
            return _annotate(by_number[m.group(1)], reason="number", input_token=token)
        # 模糊兜底：允许 token 与标题去编号后的主体互为包含
        for key, nodes in by_norm_title.items():
            if not key or not nodes:
                continue
            if normalized in key or key in normalized:
                return _annotate(nodes[0], reason="fuzzy", input_token=token)
        # 最后兜底：按目录树顺序数到第 path 个节点。
        ordinal_path = _parse_ordinal_path(token)
        if ordinal_path:
            picked = _pick_by_ordinal_path(tree, ordinal_path)
            if picked is not None:
                return _annotate(
                    picked,
                    reason="ordinal",
                    input_token=token,
                    ordinal_path=ordinal_path,
                )
        return None

    for token in tokens:
        if "-" in token and normalize_chapter_selector(token) != ALL_CHAPTERS_TOKEN:
            left_raw, right_raw = token.split("-", 1)
            left = _match_one(left_raw)
            right = _match_one(right_raw)
            if not left or not right:
                unresolved.append(token)
                continue
            i, j = index_map[id(left)], index_map[id(right)]
            lo, hi = (i, j) if i <= j else (j, i)
            level = min(left.depth, right.depth)
            for k in range(lo, hi + 1):
                candidate = flat[k]
                if candidate.depth == level:
                    _annotate(candidate, reason="range", input_token=token)
                    selected[id(candidate)] = candidate
            continue

        matched = _match_one(token)
        if matched:
            selected[id(matched)] = matched
        else:
            unresolved.append(token)

    # 只保留“根选择”（如果父章节和子章节同时被选，输出父章节即可，递归会带上子树）
    selected_nodes = sorted(selected.values(), key=lambda n: index_map[id(n)])
    selected_set: Set[int] = {id(n) for n in selected_nodes}
    compact: List[ChapterNode] = []
    for node in selected_nodes:
        keep = True
        for other in selected_nodes:
            if other is node:
                continue
            if id(node) not in selected_set:
                continue
            # other 是否为 node 祖先
            stack = list(other.children)
            while stack:
                c = stack.pop()
                if c is node:
                    keep = False
                    break
                stack.extend(c.children)
            if not keep:
                break
        if keep:
            compact.append(node)
    return compact, unresolved


def fuzzy_find_title(text, title):
    title_norm = normalize_text(title)
    lines = text.split("\n")
    pos = 0
    for line in lines:
        line_norm = normalize_text(line)
        if line_norm == title_norm or line_norm.startswith(title_norm):
            return pos
        pos += len(line) + 1
    return -1


def split_text_by_children(node, text):
    children = node.children
    if not children:
        return text, {}

    split_points = []
    for child in children:
        pos = fuzzy_find_title(text, child.title)
        if pos >= 0:
            split_points.append((pos, child))
        else:
            logger.warning(
                "在章节 %r 中未找到子章节标题 %r", node.title, child.title
            )

    split_points.sort(key=lambda x: x[0])

    intro = text[: split_points[0][0]] if split_points else text
    child_texts = {}
    for i, (pos, child) in enumerate(split_points):
        end_pos = split_points[i + 1][0] if i + 1 < len(split_points) else len(text)
        child_texts[child] = text[pos:end_pos]

    return intro, child_texts


def process_chapter(node, inherited_text="", pdf_path=""):
    if inherited_text:
        full_text = inherited_text
    else:
        assert node.end_page is not None
        end_page = max(node.page + 1, int(node.end_page))
        full_text = extract_pages_text(pdf_path, node.page, end_page)

    intro, child_texts = split_text_by_children(node, full_text)
    # 兜底：叶子章节仅抽到标题时，扩一页重取（兼容 inherited_text 仅含标题的情况）。
    if not node.children:
        stripped_intro = strip_title_from_text(intro.strip(), node.title).strip()
        if (not stripped_intro) and node.end_page is not None:
            fallback_end = max(node.page + 2, int(node.end_page) + 1)
            fallback_text = extract_pages_text(pdf_path, node.page, fallback_end)
            intro, child_texts = split_text_by_children(node, fallback_text)
    node.text = intro.strip()

    for child in node.children:
        child_inherited = child_texts.get(child, "")
        process_chapter(child, child_inherited, pdf_path)


def strip_title_from_text(text, title):
    if not text:
        return text
    lines = text.split("\n")
    if lines:
        first_norm = normalize_text(lines[0])
        title_norm = normalize_text(title)
        if first_norm == title_norm or first_norm.startswith(title_norm):
            return "\n".join(lines[1:]).strip()
    return text


def merge_paragraphs(text):
    lines = text.split("\n")
    result = []
    current = []

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if current:
                result.append("".join(current))
                current = []
            continue

        if not current:
            current.append(stripped)
        else:
            prev = current[-1]
            if prev.endswith("-"):
                current[-1] = prev[:-1]
                current.append(stripped)
            elif stripped.startswith(
                ("（", "『", "“", "(", "[", "{", "<", '"', "'")
            ):
                current.append(stripped)
            elif prev.endswith(
                (
                    "。",
                    "，",
                    "；",
                    "：",
                    "、",
                    "！",
                    "？",
                    "”",
                    "』",
                    "）",
                    ")",
                    "]",
                    "}",
                    ">",
                    '"',
                    "'",
                    "%",
                )
            ):
                current.append(stripped)
            elif re.search(r"[a-zA-Z]$", prev) and re.match(r"^[a-zA-Z]", stripped):
                current.append(" " + stripped)
            else:
                current.append(stripped)

    if current:
        result.append("".join(current))
    return "\n\n".join(result)


def write_markdown(node, f):
    text = strip_title_from_text(node.text, node.title)
    text = merge_paragraphs(text)

    heading = "#" * (node.depth + 1)
    f.write(f"{heading} {node.title}\n")
    if text:
        f.write(text + "\n")
    f.write("\n")

    for child in node.children:
        write_markdown(child, f)


def build_docling_compatible_json(
    flat_nodes: List[ChapterNode], source_name: str
) -> Dict[str, Any]:
    """按展平章节生成与 docling_search 兼容的 JSON（page_no 为 1-based）。"""
    texts: List[Dict[str, Any]] = []
    idx = 0
    for node in flat_nodes:
        body = merge_paragraphs(strip_title_from_text(node.text, node.title))
        heading = "#" * (node.depth + 1)
        combined = f"{heading} {node.title}\n\n{body}".strip()
        if not combined:
            continue
        page_no = max(1, int(node.page) + 1)
        label = "section_header" if node.children or node.depth <= 1 else "text"
        texts.append(
            {
                "self_ref": f"#/texts/{idx}",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": label,
                "prov": [
                    {
                        "page_no": page_no,
                        "bbox": {
                            "l": 0.0,
                            "t": 0.0,
                            "r": 0.0,
                            "b": 0.0,
                            "coord_origin": "TOPLEFT",
                        },
                    }
                ],
                "orig": combined,
                "text": combined,
            }
        )
        idx += 1

    return {
        "schema_name": "DoclingDocument",
        "version": "1.0-thesis-outline",
        "name": source_name,
        "origin": {"filename": source_name},
        "body": {},
        "texts": texts,
        "tables": [],
        "pictures": [],
    }


def run_thesis_pdf_extract(pdf_path: str) -> Tuple[str, Dict[str, Any], int]:
    """
    执行完整提取流程。

    Returns:
        (markdown 全文, document.json 字典, PDF 总页数)

    Raises:
        ValueError: PDF 无书签目录时。
    """
    import pypdf

    path = str(pdf_path)
    reader = pypdf.PdfReader(path)
    outlines = reader.outline
    total_pages = len(reader.pages)

    if not outlines:
        raise ValueError("该 PDF 没有目录（outline），无法按章节提取。")

    tree = build_outline_tree(reader, outlines)
    flat: List[ChapterNode] = []
    flatten_nodes(tree, flat)
    compute_end_pages(flat, total_pages)

    for node in tree:
        process_chapter(node, pdf_path=path)

    buf = io.StringIO()
    for node in tree:
        write_markdown(node, buf)
    md = buf.getvalue()

    json_data = build_docling_compatible_json(flat, Path(path).name)
    return md, json_data, total_pages
