"""
在终端里「自动点 http 链接」的跨平台实现。

WSL 下若未装任何 Linux 浏览器，标准库 ``webbrowser`` 会走 ``xdg-open`` 并失败（见用户日志）；
本模块在检测到 WSL 时优先用 **Windows** 侧打开：``wslview`` / ``powershell`` / ``cmd``。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _open_in_windows_from_wsl(url: str) -> bool:
    """在 WSL 里唤起 Windows 默认浏览器。"""
    wslview = shutil.which("wslview")
    if wslview:
        try:
            subprocess.Popen(
                [wslview, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    for ps in (
        Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
        Path("/mnt/c/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe"),
    ):
        if ps.is_file():
            try:
                subprocess.Popen(
                    [str(ps), "-NoProfile", "-Command", f"Start-Process '{url}'"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except OSError:
                pass
    cmd = Path("/mnt/c/Windows/System32/cmd.exe")
    if cmd.is_file():
        try:
            subprocess.Popen(
                [str(cmd), "/c", "start", "", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    return False


def open_http_url(url: str) -> bool:
    """
    打开 http(s) 链接。WSL 下优先用 Windows，避免无 Linux 浏览器时 xdg-open 报一串 not found。

    返回是否认为已成功提交打开请求（不保证用户侧一定有浏览器）。
    """
    if is_wsl() and _open_in_windows_from_wsl(url):
        return True
    try:
        return bool(webbrowser.open(url, new=1, autoraise=True))
    except OSError:
        return False
