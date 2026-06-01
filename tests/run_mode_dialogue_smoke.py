"""
三种模式多轮 + 模式切换冒烟（需可用 LLM API）。
用法: python tests/run_mode_dialogue_smoke.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_cli import TeXAgentCLI
from utils.reply_format import format_reply_for_ui


def _reply_preview(result: dict, max_len: int = 120) -> str:
    text = str(result.get("output") or "").strip()
    if not text:
        meta = result.get("metadata") or {}
        order = meta.get("__execution_order__") or []
        if order:
            nd = meta.get(order[-1]) or {}
            text = str(nd.get("result") or "")
    text = format_reply_for_ui(text)
    text = " ".join(text.split())
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _ctx_len(cli: TeXAgentCLI) -> int:
    return len(cli.context) if cli.context else 0


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


def _run_step(cli: TeXAgentCLI, label: str, mode: str, message: str, **kwargs) -> dict:
    _safe_print(f"\n--- {label} [{mode}] ---")
    _safe_print(f"用户: {message}")
    before = _ctx_len(cli)
    if mode == "auto":
        res = cli.run_auto_task(message, use_loading=False)
    elif mode == "plan":
        res = cli.run_plan_task(message, use_loading=False)
    else:
        res = cli.run_task(message, use_loading=False, **kwargs)
    after = _ctx_len(cli)
    err = res.get("error")
    preview = _reply_preview(res)
    _safe_print(f"上下文条数: {before} -> {after}")
    _safe_print(f"错误: {err or '无'}")
    _safe_print(f"回复预览: {preview}")
    return res


def main() -> None:
    cli = TeXAgentCLI(use_branch=False)
    report = {"steps": []}

    steps = [
        ("auto-1", "auto", "原封不动输出：MODE_TEST_A", {}),
        ("auto-2", "auto", "上一句我让你输出什么？", {}),
        ("plan-1", "plan", "用一句话说明什么是 SMT 求解器。", {}),
        ("plan-2", "plan", "结合上一句，它常用于什么场景？", {}),
        ("task-1", "task", "用一句话介绍 LaTeX。", {"workflow_name": "default"}),
        ("auto-3", "auto", "我们对话里提到过 SMT 吗？只答有或没有。", {}),
    ]

    for label, mode, msg, kw in steps:
        try:
            res = _run_step(cli, label, mode, msg, **kw)
            report["steps"].append(
                {
                    "label": label,
                    "mode": mode,
                    "ctx_after": _ctx_len(cli),
                    "error": res.get("error"),
                    "preview": _reply_preview(res, 200),
                }
            )
        except Exception as ex:  # noqa: BLE001
            report["steps"].append({"label": label, "error": str(ex)})
            print(f"异常: {ex}")

    out_path = ROOT / "output" / "mode_dialogue_smoke_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已写入: {out_path}")


if __name__ == "__main__":
    main()
