"""
启动独立幽灵窗口（阶段 10）：不依赖 VS Code 扩展。

  python -m latex.ghost_cli --root path/to/project --main-tex main.tex
"""
from __future__ import annotations

import argparse
import sys

from latex.ghost_server import run_ghost_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TeX_Agent LaTeX 幽灵窗口（浏览器内行间建议，非 CLI 文本 / 非 Web 主 UI）"
    )
    parser.add_argument("--root", required=True, help="LaTeX 项目根目录")
    parser.add_argument("--main-tex", dest="main_tex", help="主 tex 相对路径")
    parser.add_argument(
        "--quiet-sec",
        type=float,
        default=1.0,
        help="目录发生修改后静默多久再触发诊断（秒）",
    )
    parser.add_argument(
        "--enable-auto-polish",
        action="store_true",
        help="启用空闲自动润色（PR-10a 默认关闭）",
    )
    parser.add_argument(
        "--disable-latexmk",
        action="store_true",
        help="关闭编译检查（默认开启，与静态检查同触发条件）",
    )
    parser.add_argument(
        "--idle-polish-sec",
        type=float,
        default=2.0,
        help="启用自动润色时，停笔后触发润色（秒）",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="不自动打开浏览器",
    )
    args = parser.parse_args()

    try:
        run_ghost_server(
            root=args.root,
            main_tex=args.main_tex,
            quiet_sec=args.quiet_sec,
            auto_polish=args.enable_auto_polish,
            enable_latexmk=not args.disable_latexmk,
            idle_polish_sec=args.idle_polish_sec,
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
        )
    except KeyboardInterrupt:
        print("\n[Ghost UI] 已停止。", file=sys.stderr)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
