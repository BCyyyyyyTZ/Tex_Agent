"""
Ghost 主动润色 Prompt 组装（PR-10d）。
"""
from __future__ import annotations


def _clip(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n% [TeX_Agent] 内容过长，已截断。"


def build_ghost_polish_prompt(
    *,
    query: str,
    target_file: str,
    target_text: str,
    context_file: str,
    context_text: str,
) -> str:
    """
    要求模型返回结构化 JSON：
    - original_text
    - polished_text
    - problem_zh
    - advice_zh
    """
    target_block = _clip(target_text)
    context_block = _clip(context_text)
    return f"""你是学术论文 LaTeX 润色助手。请根据用户需求提出**可应用的局部润色建议**。

约束：
1) 不破坏 LaTeX 语法，不改动宏命令名称与数学命令结构。
2) 必须返回 JSON（不要包含 markdown 代码块外文本）。
3) original_text 必须是 target_file 中原文的连续子串，便于定位。
4) polished_text 为替换后的文本；problem_zh 描述原文问题；advice_zh 说明为何这样改。
5) 若不需要修改，polished_text 置空，problem_zh 说明原因，original_text 置空。

输出 JSON 模板：
{{
  "file": "{target_file}",
  "original_text": "...",
  "polished_text": "...",
  "problem_zh": "...",
  "advice_zh": "..."
}}

用户润色要求：
{query}

目标文件（必须从此文件抽取 original_text）：
file: {target_file}
```latex
{target_block}
```

上下文文件（辅助理解语义）：
file: {context_file}
```latex
{context_block}
```
"""
