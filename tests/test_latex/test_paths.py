from __future__ import annotations

import os
from pathlib import Path

import pytest

from latex.paths import normalize_rel_path, resolve_tex_file

VALORA = Path(__file__).resolve().parents[1] / "test_latex" / "VaLoRA_TMC"
INTRO_REL = "weijun/Intro.tex"


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_resolve_with_root_and_posix_rel() -> None:
    abs_path, rel = resolve_tex_file(root=str(VALORA), rel_path=INTRO_REL)
    assert abs_path.is_file()
    assert rel == INTRO_REL


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_resolve_with_windows_style_rel() -> None:
    abs_path, rel = resolve_tex_file(root=str(VALORA), rel_path=r"weijun\Intro.tex")
    assert abs_path.is_file()
    assert rel == INTRO_REL


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_resolve_with_absolute_path() -> None:
    intro = (VALORA / "weijun" / "Intro.tex").resolve()
    abs_path, rel = resolve_tex_file(path=str(intro), root=str(VALORA))
    assert abs_path == intro
    assert rel == INTRO_REL


@pytest.mark.skipif(not VALORA.is_dir(), reason="VaLoRA_TMC fixture not present")
def test_resolve_path_relative_to_root_on_windows() -> None:
    # 模拟 API 传入相对 path + root（不依赖盘符格式）
    abs_path, rel = resolve_tex_file(
        path=os.path.join("weijun", "Intro.tex"),
        root=str(VALORA),
    )
    assert abs_path.is_file()
    assert rel == INTRO_REL


def test_normalize_rel_path() -> None:
    assert normalize_rel_path(r".\weijun\Intro.tex") == "weijun/Intro.tex"
    assert normalize_rel_path("/weijun/Intro.tex") == "weijun/Intro.tex"
    assert normalize_rel_path("weijun/Intro.tex") == "weijun/Intro.tex"
