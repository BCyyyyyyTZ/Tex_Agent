from __future__ import annotations

from pathlib import Path

import pytest

from memory.factory import MemoryFactory


def test_create_memory__shared_and_private() -> None:
    m1 = MemoryFactory.create_memory("shared")
    assert m1 is not None
    m2 = MemoryFactory.create_memory("private", "agent1")
    assert m2 is not None


def test_create_memory__private_requires_agent_id() -> None:
    with pytest.raises(ValueError):
        MemoryFactory.create_memory("private")


def test_branch_memory__branch_ops_and_merge(tmp_path: Path) -> None:
    mem = MemoryFactory.create_shared_memory(branch_enabled=True, persist_path=str(tmp_path / "m.jsonl"))
    assert mem.branch_enabled is True
    assert mem.list_branches() == ["main"]
    mem.save("k1", "v1")
    assert mem.load()[-1] == "v1"

    assert mem.create_branch("b1") is True
    assert mem.switch_branch("b1") is True
    mem.save("k2", "v2")
    assert "v2" in mem.load()

    out = mem.merge_to_main()
    assert out["success"] is True
    assert mem.switch_branch("main") is True
    assert "v2" in mem.load()

