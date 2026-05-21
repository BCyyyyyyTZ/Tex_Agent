"""
文件级脏区检测：checksum 对比（阶段 5 MVP 占位，供 __latex_dirty__）。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from latex.models import ProjectIndex
from latex.paths import normalize_rel_path

# end_line <= 0 表示整文件脏（占位，阶段 7 前不做行级 diff）
WHOLE_FILE_MARKER: Tuple[int, int] = (1, 0)


def compute_file_dirty(
    index: ProjectIndex,
    baseline: Dict[str, str],
) -> Dict[str, List[Tuple[int, int]]]:
    """
    对比当前 ProjectIndex 与 baseline（file -> checksum）。

    返回 rel_path -> [(start_line, end_line), ...]；整文件变更用 (1, 0)。
    """
    dirty: Dict[str, List[Tuple[int, int]]] = {}
    current_keys = set(index.files.keys())

    for rel, pf in index.files.items():
        norm = normalize_rel_path(rel)
        old = baseline.get(norm) or baseline.get(rel)
        if old is None or old != pf.checksum:
            dirty[norm] = [WHOLE_FILE_MARKER]

    for rel in baseline:
        norm = normalize_rel_path(rel)
        if norm not in current_keys and norm not in dirty:
            dirty[norm] = [WHOLE_FILE_MARKER]

    return dirty


def baseline_from_index(index: ProjectIndex) -> Dict[str, str]:
    """从 ProjectIndex 提取 checksum 快照，可写入 __latex_last_good_build__。"""
    return {
        normalize_rel_path(rel): pf.checksum
        for rel, pf in index.files.items()
        if pf.checksum
    }
