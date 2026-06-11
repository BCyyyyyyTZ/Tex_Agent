"""
Generate a thesis project from outline + template using an Agent.
Produces a single main.tex with ~8 pages of English academic content.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from agents.simple_agent_new import SimpleAgent
from core.message import WorkflowMessage


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response text."""
    patterns = [
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        r"(\{[\s\S]*\})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _build_generation_prompt(
    outline: str,
    template_dir: Optional[Path] = None,
    template_content: Optional[str] = None,
) -> str:
    """Build a prompt for the LLM to generate an English thesis."""
    q = chr(34)
    prompt_parts = [
        "You are an academic LaTeX thesis writing expert. Follow instructions precisely.",
        "",
        "## Thesis Outline",
        outline,
        "",
        "## CRITICAL REQUIREMENTS",
        "1. Generate a SINGLE file: main.tex only. DO NOT split into separate chapter files.",
        "2. Use standard English LaTeX (\\documentclass[11pt,a4paper]{article} or report).",
        "   Do NOT use ctex or any Chinese-specific packages.",
        "3. Content must be EXTENSIVE: aim for ~8000 words total across all sections.",
        "   This should fill approximately 8 pages when compiled (single-spaced, 11pt).",
        "4. Each section must have substantial paragraphs (200-500 words each)",
        "   with proper academic arguments, evidence, and analysis.",
        "5. Required sections: abstract, introduction, literature review,",
        "   methodology, results/discussion, conclusion, references.",
        "6. Use \\section and \\subsection for structure.",
        "   Add \\label{} and \\ref{} for cross-references.",
        "7. Include at least 3 tables (\\begin{table}) and 2 figures (\\begin{figure}).",
        "8. Include at least 5 mathematical equations (\\begin{equation}).",
        "9. Add a bibliography with 10+ references using \\bibitem.",
        "10. Return ONLY valid JSON in this format:",
        f"  {q}{q}{q}json",
        "  {",
        "    \"files\": [{\"path\": \"main.tex\", \"content\": \"...\"}],",
        "    \"title\": \"Your Thesis Title\",",
        "    \"main_tex\": \"main.tex\"",
        "  }",
        f"  {q}{q}{q}",
    ]

    if template_dir and template_dir.is_dir():
        tex_files = list(template_dir.rglob("*.tex"))
        if tex_files:
            prompt_parts.append("## Available Template Files (reference structure only)")
            for tf in tex_files[:3]:
                rel = str(tf.relative_to(template_dir).as_posix())
                chunk = tf.read_text("utf-8", errors="replace")[:2000]
                prompt_parts.append(f"### {rel}")
                prompt_parts.append(f"```\n{chunk}\n```")

    if template_content:
        prompt_parts.append("## Template Content")
        prompt_parts.append(template_content[:3000])

    return "\n".join(prompt_parts)


def generate_thesis_project(
    project_dir: Path,
    outline: str,
    template_dir: Optional[Path] = None,
    template_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a complete English thesis as single main.tex (~8 pages)."""
    prompt = _build_generation_prompt(outline, template_dir, template_content)

    agent = SimpleAgent(name="thesis_generator", temperature=0.7, max_tokens=32768)
    msg = WorkflowMessage(role="user", content=prompt)
    res = agent.run(msg)

    raw = str(res.content)
    data = _extract_json_from_text(raw)

    if not data or "files" not in data:
        main_tex = "main.tex"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / main_tex).write_text(raw, "utf-8")
        return {"title": outline[:50], "main_tex": main_tex, "summary": "Generated"}

    files = data["files"]
    main_tex = data.get("main_tex", "main.tex")

    project_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        path = f.get("path", "")
        content = f.get("content", "")
        if not path:
            continue
        fp = project_dir / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, "utf-8")

    title = data.get("title", outline[:50])
    summary = data.get("summary", data.get("abstract", ""))[:200]
    return {"title": title, "main_tex": main_tex, "summary": summary}
