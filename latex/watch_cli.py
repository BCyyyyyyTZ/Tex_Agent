"""
LaTeX 目录监视 CLI（阶段 9）。
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from latex.watch_service import WatchService
from latex.watch_events import WatchEvent


def _cli_print(message: str) -> None:
    """Windows 控制台默认 GBK 时避免 emoji 导致崩溃。"""
    try:
        print(message)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(message.encode(enc, errors="replace").decode(enc, errors="replace"))


def _explain_issue_zh(issue: dict) -> str:
    message = str(issue.get("message") or "").lower()
    if "no match found for" in message:
        return "括号或定界符没有配对，请检查附近的 { }、( )、[ ] 是否成对。"
    if "could not execute latex command" in message:
        return "LaTeX 命令执行失败，通常由上一行语法破坏引起。"
    if "undefined control sequence" in message:
        return "发现未定义命令，可能缺少宏包或命令拼写错误。"
    if "number of" in message and "doesn't match" in message:
        return "符号数量不匹配，建议优先检查当前行及上一行。"
    if "command terminated with space" in message:
        return "命令后多余空格（风格类警告）。"
    return "请根据该行上下文检查语法或排版。"


def _is_low_value_warning(issue: dict) -> bool:
    if issue.get("severity") != "warning":
        return False
    msg = str(issue.get("message") or "").lower()
    low_patterns = (
        "command terminated with space",
        "you should put a space in front of parenthesis",
        "delete this space to maintain correct pagereferences",
    )
    return any(p in msg for p in low_patterns)


def print_human_readable(payload: dict) -> None:
    """打印人读视图。"""
    issues = payload.get("issues", [])
    suggestions = payload.get("suggestions", [])
    polish = payload.get("polish_suggestions", [])

    error_count = sum(1 for i in issues if i.get("severity") == "error")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    _cli_print("\n" + "=" * 50)
    _cli_print(f"[摘要] 诊断结果: {error_count} 错误, {warning_count} 警告")
    _cli_print("=" * 50)

    chktex_warnings = payload.get("chktex_warnings") or []
    if chktex_warnings and not issues:
        _cli_print("\n[提示] ChkTeX 未产出 issues，可能原因:")
        for w in chktex_warnings:
            _cli_print(f"  - {w}")
        if "chktex_not_found" in chktex_warnings:
            _cli_print("  建议: 安装 chktex 并加入 PATH，否则只能依赖 LLM 润色。")

    if issues:
        _cli_print("\n[问题列表] Top-K (全部 ERROR + 高价值 WARN):")
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [
            i for i in issues
            if i.get("severity") == "warning" and not _is_low_value_warning(i)
        ]
        hidden_low = sum(1 for i in issues if _is_low_value_warning(i))
        top_k = errors + warnings[:20]

        for i, issue in enumerate(top_k, 1):
            sev = "ERROR" if issue.get("severity") == "error" else "WARN"
            _cli_print(
                f"  {i}. [{sev}] [{issue.get('source')}] "
                f"{issue.get('file')}:{issue.get('line')} - {issue.get('message')}"
            )
            _cli_print(f"     说明: {_explain_issue_zh(issue)}")

        remain = max(0, len(issues) - len(top_k))
        if hidden_low > 0:
            _cli_print(f"  ... 已折叠 {hidden_low} 条低价值风格警告（内部保留，不默认展示）")
        if remain > 0:
            _cli_print(f"  ... 还有 {remain} 个问题未显示")
    elif not chktex_warnings:
        _cli_print("\n[问题列表] 当前未发现诊断问题。")

    if suggestions:
        _cli_print("\n[修改建议] 纠错:")
        for i, sug in enumerate(suggestions, 1):
            line_no = sug.get("range", {}).get("start", {}).get("line", 0) + 1
            _cli_print(f"  {i}. {sug.get('file')} (行 {line_no})")
            _cli_print(f"     理由: {sug.get('rationale_zh')}")
            if sug.get("replacement"):
                _cli_print(f"     替换为: {sug.get('replacement')}")

    if polish:
        _cli_print("\n[润色建议]:")
        for i, sug in enumerate(polish, 1):
            _cli_print(f"  {i}. {sug.get('file')}")
            _cli_print(f"     理由: {sug.get('rationale_zh')}")
            if sug.get("replacement"):
                _cli_print(f"     替换为: {sug.get('replacement')}")

    _cli_print("=" * 50 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TeX_Agent LaTeX 目录监视服务")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    start_parser = subparsers.add_parser("start", help="启动监视服务")
    subparsers.add_parser("stop", help="停止监视服务")
    subparsers.add_parser("status", help="查看监视状态")

    start_parser.add_argument("--root", required=True, help="LaTeX 项目根目录")
    start_parser.add_argument("--main_tex", help="主文件路径 (相对 root)")
    start_parser.add_argument(
        "--idle-polish-sec",
        type=float,
        default=2.0,
        help="空闲润色触发时间 (秒)",
    )
    start_parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    if args.command == "start":
        root_path = Path(args.root).expanduser().resolve()
        if not root_path.is_dir():
            _cli_print(f"错误: 目录 {root_path} 不存在")
            sys.exit(1)

        last_error: Dict[str, Optional[str]] = {"value": None}

        def on_event(event: WatchEvent) -> None:
            if args.json:
                _cli_print(event.model_dump_json())
                return
            if event.event_type in ("diagnostics_updated", "polish_suggestions_updated"):
                print_human_readable(event.payload)
            elif event.event_type == "error":
                stage = str(event.payload.get("stage") or "runtime")
                err = str(event.payload.get("error") or "未知错误")
                detail = str(event.payload.get("detail") or "")
                message = f"[{stage}] {err}" + (f" | 详情: {detail}" if detail else "")
                if message == last_error["value"]:
                    return
                last_error["value"] = message
                _cli_print(f"\n[错误] {message}\n")

        service = WatchService(
            watch_id="cli_watch",
            root=str(root_path),
            main_tex=args.main_tex,
            idle_polish_sec=args.idle_polish_sec,
            on_event=on_event,
        )

        _cli_print("[启动] LaTeX 监视服务...")
        _cli_print(f"[目录] {root_path}")
        if args.main_tex:
            _cli_print(f"[主文件] {args.main_tex}")
        _cli_print("保存 .tex/.bib 后会触发诊断；停笔约 2s 后触发润色。")
        _cli_print("按 Ctrl+C 停止监视\n")

        try:
            service.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _cli_print("\n[停止] 正在停止服务...")
            service.stop()
            _cli_print("服务已停止。")
    else:
        _cli_print("提示: 当前 CLI 仅支持前台 start 模式。")


if __name__ == "__main__":
    main()
