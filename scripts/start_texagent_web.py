#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TeX Agent Web 一键启动：子进程跑 ``python -m ui.web.server``，约 2.2s 后通过
``default_open_chat_after_start`` **默认**用系统/Windows 默认浏览器打开（见 ``browser_open``、``ide_launch``）；
设 ``TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER=1`` 可在那之后再试 **Simple Browser**。

在已装本仓库扩展时，可用带 ``--no-browser`` 仅起服务后自行 **Ctrl+Alt+T**。

  TEX_AGENT_NO_OPEN_BROWSER=1  不自动打开浏览器
用法：
  python scripts/start_texagent_web.py
  python scripts/start_texagent_web.py --no-browser
  python scripts/start_texagent_web.py --port 9000
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ui.web.ide_launch import default_open_chat_after_start  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="启动 TeX Agent Web UI (FastAPI + 静态页)")
    ap.add_argument(
        "--no-browser",
        action="store_true",
        help="只起服务，不自动打开系统浏览器（给扩展用 Simple Browser 等）",
    )
    ap.add_argument("--host", default=os.environ.get("TEX_AGENT_WEB_HOST", "127.0.0.1"))
    ap.add_argument(
        "--port", type=int, default=int(os.environ.get("TEX_AGENT_WEB_PORT", "8765"))
    )
    args = ap.parse_args()
    os.environ["TEX_AGENT_WEB_HOST"] = str(args.host)
    os.environ["TEX_AGENT_WEB_PORT"] = str(args.port)
    url = f"http://{args.host}:{args.port}/"
    if not (REPO / "ui" / "web" / "server.py").is_file():
        print("错误：找不到 ui/web/server.py，请在 TeX_Agent 仓库根下运行本脚本。", file=sys.stderr)
        return 1
    os.chdir(REPO)
    print(f"[TeX Agent] 工作目录: {REPO}", flush=True)
    print(f"[TeX Agent] 将启动: {sys.executable} -m ui.web.server", flush=True)
    proc = subprocess.Popen([sys.executable, "-m", "ui.web.server"], cwd=str(REPO))
    if args.no_browser:
        print(f"[TeX Agent] --no-browser。服务: {url}", flush=True)
    else:
        time.sleep(2.2)
        default_open_chat_after_start()

    def on_sig(_sig=None, _frame=None) -> None:  # type: ignore[no-untyped-def]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, on_sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_sig)
    if sys.platform == "win32" and hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, on_sig)  # type: ignore[attr-defined]
    rc = proc.wait()
    return int(rc) if rc is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
