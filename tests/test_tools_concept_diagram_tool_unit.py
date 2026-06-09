"""
tools.concept_diagram_tool 的测试。

覆盖点：
1) 入参校验（prompt/output_path）；
2) 未配置 API key 时的错误提示；
3) Mermaid 提取与编码的本地逻辑（不依赖外部服务）。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

if "agents.base_agent" not in sys.modules:
    agents_pkg = types.ModuleType("agents")
    agents_pkg.__path__ = []
    sys.modules["agents"] = agents_pkg

    base_agent_mod = types.ModuleType("agents.base_agent")

    class GeminiClient:
        def __init__(self, *args, **kwargs):
            pass

        def response(self, prompt: str, *args, **kwargs) -> str:
            return "flowchart TB\nA-->B\n"

    base_agent_mod.GeminiClient = GeminiClient
    sys.modules["agents.base_agent"] = base_agent_mod

from tools.concept_diagram_tool import ConceptDiagramTool


def test_concept_diagram_rejects_empty_prompt(tmp_path: Path) -> None:
    tool = ConceptDiagramTool(api_key="")
    r = tool.run(prompt="", output_path=str(tmp_path / "x.png"))
    assert r.success is False
    assert "prompt" in (r.error or "")


def test_concept_diagram_rejects_empty_output_path() -> None:
    tool = ConceptDiagramTool(api_key="")
    r = tool.run(prompt="x", output_path="")
    assert r.success is False
    assert "output_path" in (r.error or "")


def test_concept_diagram_requires_api_key(tmp_path: Path) -> None:
    tool = ConceptDiagramTool(api_key="")
    r = tool.run(prompt="x", output_path=str(tmp_path / "x.png"))
    assert r.success is False
    assert "GEMINI_API_KEY" in (r.error or "") or "GOOGLE_API_KEY" in (r.error or "")


def test_concept_diagram_extract_mermaid_strips_fences() -> None:
    tool = ConceptDiagramTool(api_key="")
    raw = "```mermaid\nflowchart TB\nA-->B\n```"
    s = tool._extract_mermaid(raw)
    assert s.startswith("flowchart")
    assert "```" not in s


def test_concept_diagram_encode_mermaid_ink_has_expected_prefix() -> None:
    tool = ConceptDiagramTool(api_key="")
    encoded = tool._encode_mermaid_ink("flowchart TB\nA-->B\n")
    assert encoded.startswith("pako:")
    # mermaid.ink 的 URL-safe base64 变体不应包含 '+' '/'
    assert "+" not in encoded
    assert "/" not in encoded
