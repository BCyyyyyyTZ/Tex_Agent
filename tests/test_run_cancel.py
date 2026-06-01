"""run_cancel：可中断 sleep 与 patch 不递归。"""
import time

from utils import run_cancel as rc


def test_patch_sleep_no_recursion():
    with rc.patch_sleep_interruptible():
        t0 = time.monotonic()
        time.sleep(0.05)
        assert time.monotonic() - t0 < 2.0
