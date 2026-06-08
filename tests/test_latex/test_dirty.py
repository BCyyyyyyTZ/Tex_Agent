from __future__ import annotations

from pathlib import Path

from latex.dirty import baseline_from_index, compute_file_dirty
from latex.project_index import build_project_index

MULTIFILE = Path(__file__).resolve().parents[1] / "fixtures" / "latex" / "multifile"


def test_compute_file_dirty_detects_checksum_change() -> None:
    index = build_project_index(MULTIFILE, enrich=False)
    baseline = baseline_from_index(index)
    assert baseline

    dirty = compute_file_dirty(index, baseline)
    assert dirty == {}

    tampered = dict(baseline)
    first_key = next(iter(tampered))
    tampered[first_key] = "sha256:deadbeef"
    dirty2 = compute_file_dirty(index, tampered)
    assert first_key in dirty2
    assert dirty2[first_key] == [(1, 0)]
