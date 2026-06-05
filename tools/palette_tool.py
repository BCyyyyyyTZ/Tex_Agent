"""配色方案生成：基于 curated 色板 + HSL 微调，输出预览图与 HEX 列表。"""
from __future__ import annotations

import colorsys
import random
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.message import ToolResult
from tools.base_tool import BaseTool
from tools.web_tool_utils import unique_output_path
from utils.logger import get_logger

logger = get_logger(__name__)

# 每套主题：名称 + 基础色（6 色）+ 用途说明
THEME_PALETTES: dict[str, dict[str, Any]] = {
    "academic": {
        "label": "学术稳重",
        "colors": ["#1D3557", "#457B9D", "#A8DADC", "#F1FAEE", "#E63946", "#2A9D8F"],
        "desc": "适合论文图表、系统架构图",
    },
    "ieee": {
        "label": "IEEE 风",
        "colors": ["#0072BD", "#D95319", "#EDB120", "#7E2F8E", "#77AC30", "#4DBEEE"],
        "desc": "经典 IEEE 默认色序",
    },
    "nature": {
        "label": "自然大地",
        "colors": ["#606C38", "#283618", "#FEFAE0", "#DDA15E", "#BC6C25", "#588157"],
        "desc": "偏生态、地理、环境类论文",
    },
    "ocean": {
        "label": "海洋蓝调",
        "colors": ["#03045E", "#0077B6", "#00B4D8", "#90E0EF", "#CAF0F8", "#023E8A"],
        "desc": "清爽冷色，适合信息可视化",
    },
    "sunset": {
        "label": "日落暖色",
        "colors": ["#780000", "#C1121F", "#FDF0D5", "#669BBC", "#003049", "#FCBF49"],
        "desc": "对比鲜明，适合 highlight 数据",
    },
    "pastel": {
        "label": "柔和粉彩",
        "colors": ["#FFC8DD", "#FFAFCC", "#BDE0FE", "#A2D2FF", "#CDB4DB", "#E2ECE9"],
        "desc": "演示文稿、海报友好",
    },
    "grayscale": {
        "label": "印刷灰阶",
        "colors": ["#212529", "#343A40", "#495057", "#6C757D", "#ADB5BD", "#DEE2E6"],
        "desc": "黑白打印、审稿预览",
    },
    "colorblind": {
        "label": "色盲友好",
        "colors": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#F0E442"],
        "desc": "Okabe-Ito 色盲安全配色",
    },
}


def _hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


def _luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _text_color_for_bg(hex_color: str) -> str:
    return "#FFFFFF" if _luminance(hex_color) < 0.55 else "#1A1A2E"


def _vary_color(hex_color: str, seed: int, idx: int) -> str:
    """对基础色做轻微 HSL 偏移，使 random/seed 模式有变化但仍在同一色系。"""
    r, g, b = _hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    rng = random.Random(seed + idx * 9973)
    h = (h + rng.uniform(-0.04, 0.04)) % 1.0
    l = max(0.18, min(0.82, l + rng.uniform(-0.06, 0.06)))
    s = max(0.25, min(0.95, s + rng.uniform(-0.08, 0.08)))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(nr, ng, nb)


class PaletteTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="palette",
            description="生成论文/演示向配色方案，输出色块预览图与 HEX 列表。",
            input_schema={
                "theme": "主题名或 random",
                "count": "颜色数量 3~8",
                "seed": "可选随机种子",
            },
        )

    def _resolve_theme(self, theme: str) -> str:
        t = (theme or "academic").strip().lower()
        if t == "random":
            return random.choice(list(THEME_PALETTES.keys()))
        if t in THEME_PALETTES:
            return t
        # neon 等旧名映射
        aliases = {"neon": "sunset", "academic": "academic"}
        return aliases.get(t, "academic")

    def _pick_colors(self, theme: str, count: int, seed: int | None) -> tuple[str, list[str], str]:
        key = self._resolve_theme(theme)
        meta = THEME_PALETTES[key]
        base = list(meta["colors"])
        n = max(3, min(8, count))
        if seed is not None:
            random.seed(seed)
        # 取前 n 色；不足则循环并微调
        colors: list[str] = []
        for i in range(n):
            src = base[i % len(base)]
            if seed is not None or theme.strip().lower() == "random":
                colors.append(_vary_color(src, seed or random.randint(0, 99999), i))
            else:
                colors.append(src.upper())
        return key, colors, str(meta.get("desc", ""))

    def _render_palette_card(self, colors: list[str], theme_key: str, output_path: Path) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        n = len(colors)
        fig_h = 2.8 + (1 if n > 6 else 0)
        fig, ax = plt.subplots(figsize=(max(7.5, n * 1.15), fig_h))
        fig.patch.set_facecolor("#0F172A")
        ax.set_facecolor("#0F172A")
        ax.set_xlim(0, n)
        ax.set_ylim(0, 2.2)
        ax.axis("off")

        ax.text(
            n / 2,
            2.05,
            f"Palette / {theme_key}",
            ha="center",
            va="center",
            fontsize=13,
            fontweight="600",
            color="#E2E8F0",
        )

        for i, c in enumerate(colors):
            rect = patches.FancyBboxPatch(
                (i + 0.06, 0.35),
                0.88,
                1.35,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=c,
                edgecolor="white",
                linewidth=0.8,
                alpha=0.95,
            )
            ax.add_patch(rect)
            tc = _text_color_for_bg(c)
            ax.text(i + 0.5, 1.02, c, ha="center", va="center", fontsize=9, fontweight="600", color=tc)
            ax.text(i + 0.5, 0.62, f"C{i + 1}", ha="center", va="center", fontsize=8, color=tc, alpha=0.85)

        fig.tight_layout(pad=0.6)
        fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

    def run(self, theme: str = "academic", count: int = 6, seed: Any = None) -> ToolResult:
        try:
            s = int(seed) if seed not in (None, "") else None
            theme_key, colors, desc = self._pick_colors(theme, int(count or 6), s)
            out = unique_output_path("palette")
            self._render_palette_card(colors, theme_key, out)
            return ToolResult(
                success=True,
                output=str(out),
                metadata={
                    "colors": colors,
                    "theme": theme_key,
                    "theme_label": THEME_PALETTES[theme_key]["label"],
                    "description": desc,
                    "output_path": str(out),
                },
            )
        except Exception as e:
            logger.error(f"配色生成失败: {e}")
            return ToolResult(success=False, output="", error=f"配色生成失败: {e}")
