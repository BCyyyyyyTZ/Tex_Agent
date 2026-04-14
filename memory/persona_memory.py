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

    def _remove_from_lists(self, remove: Dict[str, Any]) -> None:
        """从列表型字段中删除与给定条目完全相同的项（去首尾空白后比较）。"""
        if not isinstance(remove, dict):
            return
        for key, to_drop in remove.items():
            if key not in _LIST_KEYS:
                continue
            if not isinstance(to_drop, list):
                continue
            drop_set = {str(x).strip() for x in to_drop if str(x).strip()}
            if not drop_set:
                continue
            cur = self._data.get(key) or []
            if not isinstance(cur, list):
                cur = []
            self._data[key] = [x for x in cur if str(x).strip() not in drop_set]

    def _set_fields(self, fields: Dict[str, Any]) -> None:
        """
        整字段覆盖：字符串可用空串清空；列表整表替换；extra 传入 dict 时整表替换。
        """
        if not isinstance(fields, dict):
            return
        for key, val in fields.items():
            if key == "version":
                if isinstance(val, int):
                    self._data["version"] = val
                elif isinstance(val, str) and val.strip().isdigit():
                    self._data["version"] = int(val.strip())
                continue
            if key == "extra":
                if val is None:
                    self._data["extra"] = {}
                elif isinstance(val, dict):
                    self._data["extra"] = deepcopy(val)
                continue
            if key in _LIST_KEYS:
                if isinstance(val, list):
                    self._data[key] = [
                        str(x).strip() for x in val if str(x).strip()
                    ]
                elif val is None:
                    self._data[key] = []
                continue
            if key in _STRING_KEYS:
                self._data[key] = "" if val is None else str(val)
                continue
            if key in DEFAULT_USER_PERSONA and key != "extra":
                self._data[key] = deepcopy(val)

    def _clear_keys(self, keys: List[Any]) -> None:
        """将指定顶层字段恢复为默认值（等同删除该字段上的用户内容）。"""
        if not isinstance(keys, list):
            return
        for raw in keys:
            k = str(raw).strip() if raw is not None else ""
            if not k or k not in DEFAULT_USER_PERSONA:
                continue
            self._data[k] = deepcopy(DEFAULT_USER_PERSONA[k])

    def apply_persona_memory_update(self, update: Any) -> None:
        """
        解析入口节点 JSON 中的 persona_memory_update。

        支持 action:
        - none: 不写盘
        - merge: delta 合并；可选 remove 从列表字段按精确项删除
        - set: fields 整字段覆盖（字符串可改为空串以清空；列表整表替换）
        - clear: clear_keys 将若干字段恢复为默认空值
        """
        if not isinstance(update, dict):
            return
        action = str(update.get("action", "none")).strip().lower()
        if action == "none":
            return

        with self._lock:
            if action == "merge":
                delta = update.get("delta")
                if isinstance(delta, dict):
                    self._merge_delta(delta)
                rem = update.get("remove")
                if isinstance(rem, dict):
                    self._remove_from_lists(rem)
            elif action == "set":
                fields = update.get("fields")
                if isinstance(fields, dict):
                    self._set_fields(fields)
                else:
                    logger.warning("persona_memory_update action=set 但缺少 fields 对象，已忽略")
                    return
            elif action == "clear":
                keys = update.get("clear_keys")
                if isinstance(keys, list):
                    self._clear_keys(keys)
                else:
                    logger.warning("persona_memory_update action=clear 但 clear_keys 非数组，已忽略")
                    return
            else:
                logger.warning(f"未知 persona_memory_update.action={action!r}，已忽略")
                return
            try:
                self._atomic_write()
            except OSError as e:
                logger.warning(f"用户画像写盘失败: {e}")
