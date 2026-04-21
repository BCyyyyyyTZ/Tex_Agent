"""
text_normalize.py：文本规范化工具。

核心用途：
  docling 使用 RapidOCR 解析中文 PDF 时，有时将汉字映射为 Unicode「康熙部首」区段
  （U+2F00–U+2FDF）或「CJK 笔画」区段（U+31C0–U+31EF）而非标准 CJK 汉字
  （U+4E00–U+9FFF）。这会导致：
    - LLM 读到 markdown 后将康熙部首写入 text_quote
    - pdf_comment_tool 用 text_quote 在 PDF 中搜索时找不到（PDF 存的是标准汉字）

修复方法：
  1. 优先用 unicodedata.normalize('NFKC', text) —— NFKC 规范化会将大多数兼容字符
     映射回其对应的正常形式（包括大部分康熙部首）。
  2. 对 NFKC 无法覆盖的极少数情况，提供一张手工补丁表。

对外接口：
  normalize(text: str) -> str
    对任意字符串进行规范化，返回清理后的结果。
"""

import re
import unicodedata
from functools import lru_cache
from typing import Optional

# ---------------------------------------------------------------------------
# 手工补丁：NFKC 后仍可能残留的极端案例
# （实际上 NFKC 已覆盖 U+2F00-U+2FDF 大部分，这张表作为保险）
# ---------------------------------------------------------------------------
_EXTRA_MAP = {
    # 少数康熙部首 NFKC 仍不能还原（按需扩充）
    "\u2F08": "\u4EBA",  # ⼈ → 人
    "\u2F09": "\u5140",  # ⼉ → 儿
    "\u2F0B": "\u5165",  # ⼊ → 入
    "\u2F0C": "\u516B",  # ⼋ → 八
    "\u2F0F": "\u51A0",  # ⼏ → 几 (近似)
    "\u2F14": "\u5200",  # ⼑ → 刀
    "\u2F1C": "\u624B",  # ⼿ → 手
    "\u2F26": "\u53E3",  # ⼝ → 口
    "\u2F27": "\u56D7",  # ⼧ → 囗 (近似)
    "\u2F29": "\u571F",  # ⼩ → 土 (近似，按上下文)
    "\u2F2A": "\u58EB",  # ⼪ → 士
    "\u2F31": "\u5927",  # ⼱ → 大 (近似)
    "\u2F3B": "\u5973",  # ⼻ → 女
    "\u2F44": "\u5B50",  # ⽄ → 子
    "\u2F4A": "\u5C71",  # ⽊ → 山 (近似)
    "\u2F4B": "\u5DE5",  # ⽋ → 工 (近似)
    "\u2F50": "\u5F20",  # ⽐ → 弓 (近似)
    "\u2F54": "\u5FC3",  # ⼼ → 心
    "\u2F56": "\u6238",  # ⽖ → 戶 (近似)
    "\u2F5D": "\u624B",  # ⽝ → 手 (近似)
    "\u2F61": "\u6587",  # ⽡ → 文 (近似)
    "\u2F63": "\u659C",  # ⽣ → 斗 (近似)
    "\u2F64": "\u65A4",  # ⽤ → 斤
    "\u2F6C": "\u6728",  # ⽬ → 木 (近似，取决上下文)
    "\u2F6D": "\u6B20",  # ⽭ → 欠
    "\u2F6E": "\u6B62",  # ⽮ → 止
    "\u2F72": "\u6C34",  # ⽲ → 水
    "\u2F73": "\u706B",  # ⽳ → 火
    "\u2F76": "\u7236",  # ⽶ → 父 (近似)
    "\u2F7A": "\u72AC",  # ⽺ → 犬 (近似)
    "\u2F7C": "\u7384",  # ⽼ → 玄 (近似)
    "\u2F81": "\u76EE",  # ⾁ → 目 (近似)
    "\u2F83": "\u77F3",  # ⾃ → 石
    "\u2F85": "\u793A",  # ⾅ → 示
    "\u2F88": "\u7F8A",  # ⾨ → 羊 (近似)
    "\u2F8B": "\u8001",  # ⾫ → 老 (近似)
    "\u2F8C": "\u8033",  # ⾬ → 而 (近似)
    "\u2F90": "\u8089",  # ⾰ → 肉
    "\u2F96": "\u81EA",  # ⾦ → 自 (近似)
    "\u2F97": "\u81F3",  # ⾧ → 至
    "\u2F9D": "\u8272",  # ⾭ → 色 (近似)
    "\u2FA0": "\u864E",  # ⾠ → 虎 (近似)
    "\u2FA3": "\u8840",  # ⾣ → 血
    "\u2FA6": "\u8FB0",  # ⾦ → 行 (近似)
    "\u2FA9": "\u8FB0",  # ⾩ → 辰 (近似)
    "\u2FAB": "\u91CC",  # ⾫ → 里 (近似)
    "\u2FAD": "\u9485",  # ⾭ → 钅 (简化)
    "\u2FB0": "\u9577",  # ⾰ → 長 (近似)
    "\u2FB1": "\u9580",  # ⾱ → 門
    "\u2FB3": "\u961C",  # ⾳ → 阜 (近似)
    "\u2FB6": "\u98DF",  # ⾶ → 食
    "\u2FB8": "\u9999",  # ⾸ → 香 (近似)
    "\u2FBA": "\u99AC",  # ⾺ → 馬
    "\u2FBB": "\u9AA8",  # ⾻ → 骨
    "\u2FC0": "\u9B3C",  # ⿀ → 鬼
}

# 空格变体 → 普通空格
_SPACE_MAP = str.maketrans({
    "\u00A0": " ",  # NO-BREAK SPACE
    "\u2002": " ",  # EN SPACE
    "\u2003": " ",  # EM SPACE
    "\u3000": " ",  # IDEOGRAPHIC SPACE（全角空格）
    "\uFEFF": "",   # BOM
})


@lru_cache(maxsize=4096)
def _normalize_char(ch: str) -> str:
    """单字符规范化（带缓存）。"""
    nfkc = unicodedata.normalize("NFKC", ch)
    if nfkc != ch:
        return nfkc
    return _EXTRA_MAP.get(ch, ch)


def normalize(text: str) -> str:
    """
    对字符串进行全面规范化：
      1. NFKC Unicode 规范化（处理大部分兼容字符 → 标准字符）
      2. 手工补丁表兜底（极少数 NFKC 覆盖不到的康熙部首）
      3. 空格变体统一 → 普通空格
    """
    if not text:
        return text
    # Step 1: NFKC (最有效，覆盖绝大多数康熙部首和半角/全角字符)
    nfkc = unicodedata.normalize("NFKC", text)
    # Step 2: 手工补丁（仅对 NFKC 仍为非标准字符的情况起效）
    result = "".join(_normalize_char(ch) for ch in nfkc)
    # Step 3: 空格统一
    result = result.translate(_SPACE_MAP)
    return result


def normalize_for_search(text: str, strip_spaces: bool = True) -> str:
    """
    为文本搜索准备规范化版本：
      - normalize()
      - 可选：去除所有空格（字符级匹配更健壮）
    """
    result = normalize(text)
    if strip_spaces:
        result = re.sub(r'\s+', '', result)
    return result
