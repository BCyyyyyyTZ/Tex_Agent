"""
全局用户画像记忆（User Persona Memory）。

- 单文件 JSON，与分支、具体工作流节点解耦；多次启动 main.py 共用同一画像。
- 由工作流「入口节点」在输出 JSON 中的 persona_memory_update 字段驱动合并写入。
- 各节点在构造 prompt 时在 system 段头部注入 format_for_prompt() 文本。
"""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_USER_PERSONA: Dict[str, Any] = {
    "version": 1,
    "display_name": "",
    "research_areas": [],
    "preferences": [],
    "writing_preferences": "",
    "latex_preferences": "",
    "citation_preferences": "",
    "other_notes": "",
    "extra": {},
}

_LIST_KEYS = frozenset({"research_areas", "preferences"})
_STRING_KEYS = frozenset({
    "display_name",
    "writing_preferences",
    "latex_preferences",
    "citation_preferences",
    "other_notes",
})


class UserPersonaMemory:
    """线程安全的文件持久化用户画像。"""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        root = Path(__file__).resolve().parent.parent
        self._path = Path(file_path) if file_path else root / "memory_store" / "user_persona.json"
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = deepcopy(DEFAULT_USER_PERSONA)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return
            merged = deepcopy(DEFAULT_USER_PERSONA)
            for k, v in obj.items():
                if k not in DEFAULT_USER_PERSONA:
                    continue
                if k == "extra":
                    if isinstance(v, dict):
                        merged["extra"] = {**(merged.get("extra") or {}), **v}
                    continue
                merged[k] = v
            self._data = merged
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"用户画像加载失败，使用默认空画像: {self._path} ({e})")

    def _atomic_write(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self._path)

    def reload(self) -> None:
        """从磁盘重新加载（多进程场景可选）。"""
        with self._lock:
            self._data = deepcopy(DEFAULT_USER_PERSONA)
            self._load()

    def reset_to_default(self) -> None:
        """清空为默认结构并写盘。"""
        with self._lock:
            self._data = deepcopy(DEFAULT_USER_PERSONA)
            try:
                self._atomic_write()
            except OSError as e:
                logger.warning(f"用户画像清空写盘失败: {e}")

    def get_profile(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def format_for_prompt(self) -> str:
        """拼到各节点 system 段最前的固定文案。"""
        with self._lock:
            blob = deepcopy(self._data)
        lines = [
            "--- [User Persona Memory | 长期用户画像，请勿编造未出现的事实] ---",
            json.dumps(blob, ensure_ascii=False, indent=2),
            "--- [End User Persona] ---",
            "",
        ]
        return "\n".join(lines)

    def _merge_delta(self, delta: Dict[str, Any]) -> None:
        if not isinstance(delta, dict):
            return
        for key, val in delta.items():
            if key == "extra" and isinstance(val, dict):
                ex = self._data.setdefault("extra", {})
                if isinstance(ex, dict):
                    ex.update(val)
                continue
            if key in _LIST_KEYS and isinstance(val, list):
                cur = list(self._data.get(key) or [])
                if not isinstance(cur, list):
                    cur = []
                seen = {str(x) for x in cur}
                for item in val:
                    s = str(item).strip()
                    if s and s not in seen:
                        cur.append(s)
                        seen.add(s)
                self._data[key] = cur
                continue
            if key in _STRING_KEYS and isinstance(val, str):
                s = val.strip()
                if s:
                    self._data[key] = s
                continue
            if key in DEFAULT_USER_PERSONA and key not in ("version", "extra"):
                self._data[key] = val

    def apply_persona_memory_update(self, update: Any) -> None:
        """
        解析入口节点 JSON 中的 persona_memory_update 对象。
        期望: {"action": "none"|"merge", "delta": { ... }}
        """
        if not isinstance(update, dict):
            return
        action = str(update.get("action", "none")).strip().lower()
        if action != "merge":
            return
        delta = update.get("delta")
        if not isinstance(delta, dict):
            return
        with self._lock:
            self._merge_delta(delta)
            try:
                self._atomic_write()
            except OSError as e:
                logger.warning(f"用户画像写盘失败: {e}")
