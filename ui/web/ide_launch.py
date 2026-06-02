"""
服务启动约 1 秒后自动打开聊天页。**默认**用 `open_http_url` 打开**系统/Windows 默认浏览器**（等同
点一次终端里的 http 链接）；WSL 下会尽量从 Windows 侧打开。

  TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER=1  在系统浏览器**之后**再尝试当前窗口 Simple Browser
  （需能在 PATH 中调用 code/cursor；WSL/Remote 上见 `_which_ide_for_simple_browser`）
  TEX_AGENT_NO_OPEN_BROWSER=1  不自动打开**外部**系统浏览器
  TEX_AGENT_NO_OPEN_SIMPLE_BROWSER=1  不尝试 Simple（对上面的 ALSO 也生效）
  TEX_AGENT_NO_REMOTE_IDE_FOR_SIMPLE=1  不回落到带 remote-cli 的 code/cursor 包装
  TEX_AGENT_OPEN_IDE_CLI=1  旧式仅走 code/cursor 子进程（见下方实现）
  （其余与 IDE / 浏览器 相关的变量见各函数内）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from ui.web.browser_open import is_wsl, open_http_url
from typing import List, Optional

# 内置「Simple Browser」：任意 VS Code 均有，在编辑器区域展示 URL（聊天页）
_CMD_SIMPLE_BROWSER = "simpleBrowser.show"
# 需安装本仓库 vscode-extension 时可用；默认不再使用，否则新开的 VS Code 里看不到界面
_WORKBENCH_EXT_VIEW = "workbench.view.extension.texagent"

_IDE_CANDIDATES = ("cursor", "code", "codium", "windsurf")


def project_root() -> Path:
    """ui/web/ide_launch.py 向上三级为仓库根（Tex_Agent/）。"""
    return Path(__file__).resolve().parent.parent.parent


def _should_spawn_ide_cli() -> bool:
    """
    默认 **False**（不调用本机 code/cursor），避免子进程多弹一个 IDE 窗口。

    需要旧式「子进程调 CLI」: TEX_AGENT_OPEN_IDE_CLI=1
    明确禁止: TEX_AGENT_NO_OPEN_IDE=1（与默认效果相同，仅作显式说明）
    """
    if (os.environ.get("TEX_AGENT_NO_OPEN_IDE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    v = (os.environ.get("TEX_AGENT_OPEN_IDE_CLI") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False


def _is_remote_ide_shim(path: str) -> bool:
    """
    远程/集成终端里 PATH 中的 cursor、code 往往是 remote-cli 包装，执行后不会「再弹一个本地新窗口」。
    例：~/.cursor-server/.../bin/remote-cli/cursor
    """
    p = path.replace("\\", "/").lower()
    if "remote-cli" in p:
        return True
    if "/.cursor-server/" in p and "/bin/" in p:
        return True
    if "/.vscode-server/" in p and "bin" in p:
        return True
    return False


def _should_open_browser_fallback() -> bool:
    v = (os.environ.get("TEX_AGENT_NO_OPEN_BROWSER") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return False
    return True


def _web_url() -> str:
    host = (os.environ.get("TEX_AGENT_WEB_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = (os.environ.get("TEX_AGENT_WEB_PORT") or "8765").strip() or "8765"
    # 浏览器和 Simple Browser 都可能复用旧标签页；启动时加时间戳，强制取最新 index.html。
    return f"http://{host}:{port}/?_t={int(time.time())}"


def _which_ide() -> tuple[Optional[str], Optional[str]]:
    """
    返回 (可执行路径, 跳过原因)。原因用于日志：例如命中 remote-cli。
    """
    override = (os.environ.get("TEX_AGENT_IDE") or "").strip()
    if override:
        p = Path(override)
        resolved = str(p) if p.is_file() else shutil.which(override)
        if not resolved:
            return None, f"TEX_AGENT_IDE={override!r} 未找到可执行文件"
        if _is_remote_ide_shim(resolved):
            return None, f"TEX_AGENT_IDE 指向远程/环境内的包装脚本: {resolved}"
        return resolved, None

    skip_notes: list[str] = []
    for name in _IDE_CANDIDATES:
        w = shutil.which(name)
        if not w:
            continue
        if _is_remote_ide_shim(w):
            skip_notes.append(f"{name} -> {w}（remote/集成 CLI，已跳过）")
            continue
        return w, None

    if skip_notes:
        return None, "；".join(skip_notes)
    return None, "PATH 中未找到 cursor / code 等"


def _which_ide_for_simple_browser() -> tuple[Optional[str], Optional[str]]:
    """
    Simple Browser 用：先走「非 remote-cli」的 cursor/code，便于命中本机安装；
    若无且未设 TEX_AGENT_NO_REMOTE_IDE_FOR_SIMPLE=1，则**任意** PATH 中的候选都接受，便于
    WSL/Remote 里只有集成终端注入的 `code`/`cursor` 包装、`_which_ide` 会跳过的情况。
    """
    ide, note = _which_ide()
    if ide:
        return ide, None
    v = (os.environ.get("TEX_AGENT_NO_REMOTE_IDE_FOR_SIMPLE") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return None, note
    for name in _IDE_CANDIDATES:
        w = shutil.which(name)
        if w:
            return w, None
    return None, note


def _ide_new_window() -> bool:
    v = (os.environ.get("TEX_AGENT_IDE_NEW_WINDOW") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False


def _ide_reuse_includes_folder() -> bool:
    """默认 False：-r 只发命令、不附工作区路径，让 Simple Browser 出现在「正在跑终端的那个」本机 IDE 窗口。"""
    v = (os.environ.get("TEX_AGENT_IDE_REUSE_WITH_FOLDER") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return False


def _vscode_open_argv(ide: str, root: Path, url: str) -> List[str]:
    """
    执行 simpleBrowser.show(url)（或打开扩展侧栏视图）。

    - 复用窗口（默认 -r）：**不附带仓库路径**，只向本机已运行的 VS Code / Cursor
      的「最后活动窗口」发命令，这样你在**哪个窗口里跑的 ui.web.server**，页就进哪个窗。
      若你遇到命令进了别的实例，可设 TEX_AGENT_IDE_REUSE_WITH_FOLDER=1，恢复为
      [ide, 本仓库, -r, --command, ...]。
    - 新窗口（TEX_AGENT_IDE_NEW_WINDOW=1）：[ide, 本仓库, -n, --command, ...] 会新开一窗并打开仓库再执行。
    """
    r = str(root.resolve())
    u = str(url)
    use_ext = (os.environ.get("TEX_AGENT_VSCODE_UI") or "").strip().lower() == "extension"
    new_win = _ide_new_window()
    win_flag = "-n" if new_win else "-r"
    with_folder = new_win or _ide_reuse_includes_folder()

    if use_ext:
        if with_folder:
            return [ide, r, win_flag, "--command", _WORKBENCH_EXT_VIEW]
        return [ide, win_flag, "--command", _WORKBENCH_EXT_VIEW]
    if with_folder:
        return [ide, r, win_flag, "--command", _CMD_SIMPLE_BROWSER, u]
    return [ide, win_flag, "--command", _CMD_SIMPLE_BROWSER, u]


def _looks_like_vscode_or_cursor_host_terminal() -> bool:
    """
    在 VS / Cursor 集成终端中跑起的服务进程通常带 TERM_PROGRAM=vscode 等标记；
    用这些判断「值得尝试」向当前工作区发 simpleBrowser，避免在纯服务器/SSH 里乱调 code。
    """
    e = os.environ
    if (e.get("TEX_AGENT_OPEN_SIMPLE_BROWSER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    if (e.get("TEX_AGENT_NO_OPEN_SIMPLE_BROWSER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    if e.get("TERM_PROGRAM") == "vscode":
        return True
    if e.get("VSCODE_INJECTION") == "1":
        return True
    _vs = ("VSCODE_IPC_HOOK", "VSCODE_IPC_HOOK_CLI", "VSCODE_NLS_CONFIG", "VSCODE_CWD")
    if any(m in e for m in _vs):
        return True
    _cr = ("CURSOR_TRACE_ID", "CURSOR_AGENT", "CURSOR_IS_CLI")
    if any(m in e for m in _cr):
        return True
    return any(k.startswith("CURSOR_") for k in e)


def _try_open_simple_browser_in_host_ide() -> bool:
    """
    在「从 VS / Cursor 集成终端启动的 Python」里，继承 env 后调 cursor|code，尽量在**本窗口** Simple Browser 打开。

    注意：不设置 start_new_session，以便保留与父前端的 IPC（若可）。
    """
    if (os.environ.get("TEX_AGENT_NO_OPEN_SIMPLE_BROWSER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    if not _looks_like_vscode_or_cursor_host_terminal():
        return False
    url = _web_url()
    ide, _skip = _which_ide_for_simple_browser()
    if not ide:
        print(
            f"[TeX Agent] 未找到 cursor/code 可发 Simple Browser 命令（或已禁止 remote 回落）。"
            f"在**本窗口**请按 Ctrl+Alt+T 或浏览器打开: {url}",
            flush=True,
        )
        return False
    argv = [ide, "-r", "--command", _CMD_SIMPLE_BROWSER, url]
    try:
        subprocess.Popen(  # noqa: S603
            argv,
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(
            f"[TeX Agent] 已请求在当前编辑器 Simple Browser 打开: {url}",
            "(若在集成终端中启动；否则可能打开其它实例。）",
            flush=True,
        )
        return True
    except OSError as e:
        print(f"[TeX Agent] Simple Browser 自动打开未成功: {e}。可手动: {url}", flush=True)
        return False


def _open_default_browser_like_clicking_link(url: str) -> bool:
    """同终端里点 http 链接；WSL 用 Windows 侧打开，其它环境用系统默认程序。"""
    if not _should_open_browser_fallback():
        print(f"[TeX Agent] 已设置 TEX_AGENT_NO_OPEN_BROWSER=1。地址: {url}", flush=True)
        return False
    if open_http_url(url):
        extra = "（WSL：已通过 Windows 打开；可装 wslu 的 wslview 更稳。）" if is_wsl() else ""
        print(f"[TeX Agent] 已用默认方式打开: {url} {extra}".strip(), flush=True)
        return True
    print(f"[TeX Agent] 无法自动打开。请手动在浏览器访问: {url}", flush=True)
    return False


def open_ide_window(delay_sec: float = 0.8) -> None:
    time.sleep(float(delay_sec))
    root = project_root()
    if not (root / "ui" / "web" / "server.py").is_file():
        return
    url = _web_url()
    if _should_spawn_ide_cli():
        ide, skip_reason = _which_ide()
        launched = False
        if ide:
            try:
                argv = _vscode_open_argv(ide, root, url)
                popen_kw: dict = {
                    "env": os.environ.copy(),
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                }
                if sys.platform != "win32":
                    popen_kw["start_new_session"] = True
                subprocess.Popen(argv, **popen_kw)  # noqa: S603
                _nw = _ide_new_window()
                _wf = _nw or _ide_reuse_includes_folder()
                print(
                    f"[TeX Agent] 已调 IDE: {ide}（新窗: {_nw}；加仓库: {_wf}；→ {url}）",
                    flush=True,
                )
                launched = True
            except OSError as e:
                print(f"[TeX Agent] 调 IDE 失败: {e}", flush=True)
        if not launched and skip_reason:
            print(f"[TeX Agent] {skip_reason}", flush=True)
        if not launched:
            _default_open_chat_url(url)
        return
    # 默认：先系统默认浏览器，再按环境变量（可选）打开 Simple Browser
    _default_open_chat_url(url)


def _default_open_chat_url(url: str) -> None:
    """先 `open_http_url`；若设 `TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER=1` 再试当前窗口 Simple。"""
    _open_default_browser_like_clicking_link(url)
    if (os.environ.get("TEX_AGENT_ALSO_OPEN_SIMPLE_BROWSER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        _try_open_simple_browser_in_host_ide()


def default_open_chat_after_start() -> None:
    """子进程/脚本在本地拉齐 `ui.web.server` 后调用，策略同 `open_ide_window` 的默认打开顺序。"""
    _default_open_chat_url(_web_url())


def schedule_open_ide(delay_sec: float = 0.8) -> None:
    t = threading.Thread(
        target=open_ide_window,
        kwargs={"delay_sec": delay_sec},
        name="texagent-open-ide",
        daemon=True,
    )
    t.start()
