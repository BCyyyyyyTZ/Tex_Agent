"""论文标题灵感：3 条本地模板 + 2 条 OpenAI 兼容 API 生成。"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.base_agent import LlmClient
from config.settings import settings
from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)

LOCAL_COUNT = 3
API_COUNT = 2

SERIOUS_TEMPLATES = [
    "{topic}: A {method} Approach",
    "Towards {adj} {topic} with {method}",
    "{topic} via {method}: {scope}",
    "Revisiting {topic}: An Empirical Study on {aspect}",
    "On {aspect} in {topic}: A {method} Perspective",
    "{adj} {topic} for {scope}: Benchmarks and Analysis",
    "Exploring {aspect} in {topic} through {method}",
]

FUNNY_TEMPLATES = [
    "I Survived {topic} and All I Got Was This {noun}",
    "How I Learned to Stop Worrying and Love {method}",
    "{topic} Is Just {noun} with Extra Steps",
    "We Added {method} to {topic} and Accidentally Published",
    "Confessions of a Researcher Who Loved {topic} Too Much",
]

ADJ = ["Robust", "Scalable", "Interpretable", "Efficient", "Adaptive", "Unified"]
NOUN = ["Attention", "Embeddings", "Baselines", "Ablation Studies", "GPU Memory"]
METHOD = [
    "Contrastive Learning", "Retrieval-Augmented Generation", "Graph Neural Networks",
    "Prompt Engineering", "Knowledge Distillation", "Self-Supervision",
]
ASPECT = ["Generalization", "Efficiency", "Robustness", "Long-Context Modeling"]
SCOPE = ["Real-World Applications", "Low-Resource Settings", "Multilingual Scenarios"]


def _title_case_topic(s: str) -> str:
    stop = {"a", "an", "the", "and", "or", "for", "in", "on", "of", "to", "via", "with"}
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if w.isupper() and len(w) <= 5:
            out.append(w)
        elif i > 0 and lw in stop:
            out.append(lw)
        else:
            out.append(w.capitalize() if w.islower() else w[0].upper() + w[1:])
    return " ".join(out)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        k = re.sub(r"\s+", " ", x.strip().lower())
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out


def _parse_llm_titles(raw: str, expected: int) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    # 尝试 JSON 数组
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x).strip().strip('"\'') for x in arr if str(x).strip()]
        except json.JSONDecodeError:
            pass
    # 编号列表或逐行
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\d]+[\.\)、]\s*", "", line)
        line = re.sub(r"^[-*•]\s*", "", line)
        line = line.strip('"\' ')
        if line and not line.startswith("{") and len(line) > 8:
            lines.append(line)
    return lines[:expected]


class PaperTitleTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="paper_title",
            description="根据关键词生成 3 条本地模板标题 + 2 条 OpenAI API 标题。",
            input_schema={
                "keywords": "主题关键词",
                "style": "serious | funny",
                "use_llm": "是否调用 OpenAI 兼容 API 生成 2 条（默认 true）",
                "seed": "本地模板随机种子",
            },
        )

    def _resolve_api_key(self) -> str:
        return (settings.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()

    def _fill_template(self, tpl: str, topic: str, rng: random.Random) -> str:
        return tpl.format(
            topic=_title_case_topic(topic),
            adj=rng.choice(ADJ),
            noun=rng.choice(NOUN),
            method=rng.choice(METHOD),
            aspect=rng.choice(ASPECT),
            scope=rng.choice(SCOPE),
        )

    def _generate_local(self, topic: str, style: str, seed: Any) -> list[str]:
        pool = list(FUNNY_TEMPLATES if style == "funny" else SERIOUS_TEMPLATES)
        rng = random.Random(int(seed)) if seed not in (None, "") else random.Random()
        rng.shuffle(pool)
        titles: list[str] = []
        seen_lower: set[str] = set()
        attempts = 0
        while len(titles) < LOCAL_COUNT and attempts < 40:
            attempts += 1
            tpl = pool[attempts % len(pool)] if attempts <= len(pool) else rng.choice(pool)
            candidate = self._fill_template(tpl, topic, rng)
            key = re.sub(r"\s+", " ", candidate.strip().lower())
            if key not in seen_lower:
                seen_lower.add(key)
                titles.append(candidate)
        return titles[:LOCAL_COUNT]

    def _build_llm_prompt(self, topic: str, style: str) -> str:
        if style == "serious":
            return (
                f"You are an academic writing assistant. Topic keywords: {topic}\n"
                f"Generate exactly {API_COUNT} rigorous, publishable paper titles "
                "for a top-tier CS/AI venue (e.g. NeurIPS, ACL, CVPR).\n"
                "Requirements:\n"
                "1) English, standard academic Title Case;\n"
                "2) Each title must be specific: explicitly name the method, dataset "
                "   domain, or key contribution—no vague filler like 'A Novel Approach';\n"
                "3) No puns, no humour, no exclamation marks;\n"
                "4) Vary the sentence structure: mix colon subtitles, "
                "   'via / through / for / beyond' constructions;\n"
                "5) Output ONLY a JSON array of strings, no markdown, no explanation.\n"
                'Example: ["Sparse Retrieval via Learned Term Weights for Open-Domain QA", '
                '"Beyond Fine-Tuning: Adapter-Based Continual Learning for Low-Resource NLP"]\n'
            )
        else:
            return (
                f"You are a witty academic comedy writer. Topic keywords: {topic}\n"
                f"Generate exactly {API_COUNT} humorous paper titles that look like "
                "real (but absurd) CS/AI conference paper titles.\n"
                "Requirements:\n"
                "1) English; Title Case or sentence-style both fine;\n"
                "2) MUST use at least one of: subverted academic expectation, "
                "   relatable PhD-life struggle, pop-culture reference, or "
                "   self-deprecating researcher humour;\n"
                "3) The research topic keywords must appear—don't ignore them;\n"
                "4) Avoid any straight-faced academic phrasing like 'A Comprehensive Survey' "
                "   or 'Towards Robust ...'; that's what the serious mode is for;\n"
                "5) Output ONLY a JSON array of strings, no markdown, no explanation.\n"
                'Example: ["We Spent Three Years on This and It Still Fails on Edge Cases: '
                'A Study of {topic}", "My Advisor Said One More Experiment: '
                'An Infinite Regress in {topic}"]\n'
            )

    def _generate_api(self, topic: str, style: str) -> tuple[list[str], str | None]:
        api_key = self._resolve_api_key()
        if not api_key:
            return [], "未配置 OPENAI_API_KEY，已跳过 AI 标题（仅返回 3 条本地模板）"

        try:
            llm = LlmClient(
                model_name=settings.llm_model,
                api_key=api_key,
                base_url=settings.openai_base_url,
                temperature=min(0.85, max(0.5, float(settings.llm_temperature))),
                max_tokens=512,
            )
            raw = llm.response(self._build_llm_prompt(topic, style))
            titles = _parse_llm_titles(raw, API_COUNT)
            if not titles:
                return [], f"AI 返回无法解析为标题：{raw[:200]}"
            return titles[:API_COUNT], None
        except Exception as e:
            logger.warning(f"PaperTitleTool API 失败: {e}")
            return [], f"OpenAI API 调用失败：{e}"

    def run(
        self,
        keywords: str = "",
        style: str = "serious",
        count: int = 5,  # 保留参数兼容；实际固定 3+2
        seed: Any = None,
        use_llm: bool = True,
    ) -> ToolResult:
        topic = (keywords or "Large Language Models").strip()
        topic = re.sub(r"\s+", " ", topic)
        st = (style or "serious").strip().lower()
        if st not in {"serious", "funny"}:
            st = "serious"

        local = self._generate_local(topic, st, seed)
        api_titles: list[str] = []
        api_note: str | None = None

        if use_llm:
            api_titles, api_note = self._generate_api(topic, st)
            api_titles = [t for t in _dedupe_keep_order(api_titles) if t.lower() not in {x.lower() for x in local}]

        lines: list[str] = []
        lines.append("【本地模板】")
        for i, t in enumerate(local, 1):
            lines.append(f"{i}. {t}")
        if api_titles:
            lines.append("")
            lines.append("【AI 生成 · OpenAI】")
            for i, t in enumerate(api_titles, len(local) + 1):
                lines.append(f"{i}. {t}")

        note_parts = ["仅供 brainstorming，正式投稿请自行斟酌。"]
        if api_note:
            note_parts.append(api_note)
        lines.append("")
        lines.append("（" + " ".join(note_parts) + "）")

        all_titles = local + api_titles
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={
                "titles": all_titles,
                "local_titles": local,
                "api_titles": api_titles,
                "style": st,
                "keywords": topic,
                "mode": "hybrid" if api_titles else ("template-only" if not use_llm else "template-partial"),
                "llm_model": settings.llm_model if api_titles else None,
                "api_skipped_reason": api_note if not api_titles and use_llm else None,
            },
        )
