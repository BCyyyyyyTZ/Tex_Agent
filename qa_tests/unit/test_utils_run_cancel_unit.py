from __future__ import annotations

import pytest

from utils.run_cancel import (
    clear_run_cancel,
    interruptible_sleep,
    is_run_cancelled,
    patch_sleep_interruptible,
    request_run_cancel,
)


def test_request_and_clear_run_cancel() -> None:
    clear_run_cancel()
    assert is_run_cancelled() is False
    request_run_cancel()
    assert is_run_cancelled() is True
    clear_run_cancel()
    assert is_run_cancelled() is False


def test_interruptible_sleep__raises_keyboard_interrupt_when_cancelled() -> None:
    clear_run_cancel()
    request_run_cancel()
    with pytest.raises(KeyboardInterrupt):
        interruptible_sleep(0.01)


def test_patch_sleep_interruptible__patches_time_sleep() -> None:
    import time

    clear_run_cancel()
    with patch_sleep_interruptible():
        request_run_cancel()
        with pytest.raises(KeyboardInterrupt):
            time.sleep(0.01)

