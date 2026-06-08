"""
Web UI 一次性下载令牌：工具将服务器本地文件路径注册为 token，浏览器通过
GET /api/download/artifact?token=... 下载（短时有效，避免任意路径泄露）。
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Dict, Optional, Tuple

_lock = threading.Lock()
# token -> (绝对路径, monotonic 过期时间)
_store: Dict[str, Tuple[str, float]] = {}

DEFAULT_TTL_SEC = 86400.0  # 24h


def _purge_locked(now: float) -> None:
    dead = [k for k, (_, exp) in _store.items() if now > exp]
    for k in dead:
        del _store[k]


def register_file(abs_path: str, ttl_sec: float = DEFAULT_TTL_SEC) -> str:
    """登记绝对路径，返回 URL 安全 token。"""
    path = (abs_path or "").strip()
    if not path:
        raise ValueError("empty path")
    tok = secrets.token_urlsafe(24)
    with _lock:
        now = time.monotonic()
        _purge_locked(now)
        _store[tok] = (path, now + float(ttl_sec))
    return tok


def get_file_path(token: str) -> Optional[str]:
    """解析 token；过期或不存在返回 None（令牌可重复使用至过期）。"""
    if not token or len(token) < 8:
        return None
    with _lock:
        now = time.monotonic()
        _purge_locked(now)
        item = _store.get(token)
        if not item:
            return None
        path, exp = item
        if now > exp:
            del _store[token]
            return None
        return path
