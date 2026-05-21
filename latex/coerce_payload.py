"""
Tool 入参归一化：兼容 CLI 字符串 JSON 与 workflow 的 tool.run(**dict)。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Union


def coerce_json_payload(
    payload: Union[str, Dict[str, Any], None] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """将 payload / kwargs 合并为 dict。"""
    if kwargs:
        if isinstance(payload, dict):
            merged: Dict[str, Any] = {**payload, **kwargs}
        elif isinstance(payload, str) and str(payload).strip():
            try:
                base = json.loads(payload)
                if isinstance(base, dict):
                    merged = {**base, **kwargs}
                else:
                    merged = dict(kwargs)
            except json.JSONDecodeError:
                merged = {**kwargs, "input": str(payload)}
        else:
            merged = dict(kwargs)
    elif isinstance(payload, dict):
        merged = dict(payload)
    elif isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {}
        if text.startswith("{"):
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("JSON 根类型必须是 object")
            return data
        return {"root": text}
    else:
        return {}

    return merged


def parse_root_from_user_input(user_input: Any) -> str:
    """从 workflow user_input / 嵌套字段解析 root。"""
    if isinstance(user_input, dict):
        root = user_input.get("root")
        return str(root).strip() if root else ""
    text = str(user_input or "").strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("root"):
                return str(data["root"]).strip()
        except json.JSONDecodeError:
            pass
    return text
