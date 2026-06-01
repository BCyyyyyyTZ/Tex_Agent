"""
进程内协作式取消：让 Ctrl+C / 关闭服务时能打断 arXiv 等长时间阻塞。

Web 流式接口勿在 thread 池里无限 queue.get()，否则主线程无法及时处理 SIGINT。
"""
from __future__ import annotations

import signal
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

_CANCEL = threading.Event()
_SIGINT_COUNT = 0
_HANDLER_INSTALLED = False
# 模块加载时保存真实 sleep，避免 patch_sleep_interruptible 后 interruptible_sleep 递归调用自身
_REAL_SLEEP = time.sleep


def clear_run_cancel() -> None:
    """新一轮任务开始前清除取消标记。"""
    global _SIGINT_COUNT
    _CANCEL.clear()
    _SIGINT_COUNT = 0


def request_run_cancel() -> None:
    _CANCEL.set()


def is_run_cancelled() -> bool:
    return _CANCEL.is_set()


def check_run_cancelled() -> None:
    """在阻塞循环中调用；已请求取消时抛出 KeyboardInterrupt。"""
    if _CANCEL.is_set():
        raise KeyboardInterrupt("用户中断（Ctrl+C）")


def interruptible_sleep(seconds: float, *, step: float = 0.2) -> None:
    """可被打断的 sleep（检查取消标记，便于 Ctrl+C 后尽快退出）。"""
    if seconds <= 0:
        check_run_cancelled()
        return
    end = time.monotonic() + seconds
    while True:
        check_run_cancelled()
        remain = end - time.monotonic()
        if remain <= 0:
            return
        _REAL_SLEEP(min(step, remain))


@contextmanager
def patch_sleep_interruptible() -> Iterator[None]:
    """在 with 块内将 time.sleep 替换为 interruptible_sleep（含 arxiv SDK 内部等待）。"""
    orig_sleep = time.sleep

    def _patched(sec: float) -> None:
        interruptible_sleep(float(sec))

    time.sleep = _patched  # type: ignore[method-assign]
    try:
        yield
    finally:
        time.sleep = orig_sleep  # type: ignore[method-assign]


def _on_sigint(signum: int, frame: Any) -> None:
    global _SIGINT_COUNT
    _SIGINT_COUNT += 1
    request_run_cancel()
    if _SIGINT_COUNT >= 2:
        # 第二次 Ctrl+C：强制退出（避免 arxiv 线程仍占着进程）
        sys.stderr.write("\n强制退出…\n")
        sys.stderr.flush()
        raise SystemExit(128 + signum)
    raise KeyboardInterrupt


def install_sigint_handler() -> None:
    global _HANDLER_INSTALLED
    if _HANDLER_INSTALLED:
        return
    signal.signal(signal.SIGINT, _on_sigint)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _on_sigint)  # Windows Ctrl+Break
    _HANDLER_INSTALLED = True
