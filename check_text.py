#!/usr/bin/env python3
"""
无 UI 批量执行 checklist_text_v3（文本审查工作流）。

支持 Linux / Windows 命令行。输入为结构化 JSON 路径，preflight 节点不调用 LLM。

用法示例：
  python check_text.py --checklist thesis-checklists.md --output-dir ./output \\
      --pdfs paper1.pdf paper2.pdf

  python check_text.py --config config/run_config_text.json

配置 JSON 字段：
  - workflow（可选，默认 checklist_text_v3）
  - checklist_path：审查清单路径
  - output_dir：输出目录，每篇论文生成 {原名}-checked.pdf
  - pdf_paths / pdfs / pdf_path：待审查 PDF 列表
"""
from __future__ import annotations

import argparse
import errno
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from core.agent_cli import TeXAgentCLI
from utils.display import display

DEFAULT_CONFIG = ROOT / "config" / "run_config_text.json"
DEFAULT_WORKFLOW = "checklist_text_v3"

EXIT_OK = 0
EXIT_ERR = 1
EXIT_CONNECT = 2


class ConnectionAbort(Exception):
    """模型或网络连接失败，应停止整批任务。"""


def _conn_substrings_loose() -> Tuple[str, ...]:
    return (
        "connection refused",
        "connection reset",
        "connection aborted",
        "connection timed out",
        "connect timeout",
        "read timeout",
        "write timeout",
        "name or service not known",
        "network is unreachable",
        "no route to host",
        "econnrefused",
        "econnreset",
        "getaddrinfo",
        "failed to establish a new connection",
        "tls handshake",
        "ssl handshake",
        "ssl: ",
        "nodename nor servname",
        "temporary failure in name resolution",
        "could not resolve host",
        "api connection error",
        "apiconnectionerror",
    )


def is_connection_failure_text(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(s in t for s in _conn_substrings_loose())


def is_connection_failure_exc(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        code = getattr(exc, "errno", None)
        if code in (
            errno.ENETUNREACH,
            errno.ECONNREFUSED,
            errno.ETIMEDOUT,
            errno.EHOSTUNREACH,
            errno.ECONNRESET,
        ):
            return True
        return is_connection_failure_text(str(exc))
    try:
        import httpx

        if isinstance(
            exc,
            (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout),
        ):
            return True
    except ImportError:
        pass
    try:
        import openai

        ac = getattr(openai, "APIConnectionError", None)
        if ac and isinstance(exc, ac):
            return True
    except ImportError:
        pass
    return is_connection_failure_text(str(exc))


def probe_model_connectivity() -> None:
    """checklist_text_v3 的 agent 节点使用 OpenAI 兼容 API。"""
    if not (settings.openai_api_key or "").strip():
        raise ConnectionAbort("未配置 OPENAI_API_KEY（审查与汇总节点必需）")
    try:
        from openai import OpenAI

        oc = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=25.0,
        )
        oc.models.list()
    except Exception as e:  # noqa: BLE001
        raise ConnectionAbort(f"OpenAI 兼容 API 连通性检查失败: {e}") from e


def _load_run_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到 {path}，请将 config/run_config_text.example.json 复制为 config/run_config_text.json。"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_path(raw: str, base_dir: Path) -> Path:
    raw = (raw or "").strip()
    if not raw:
        return Path()
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (base_dir / p).resolve()


def collect_pdf_paths(data: Dict[str, Any]) -> List[str]:
    ordered: List[str] = []
    seen: set[str] = set()
    for key in ("pdf_paths", "pdfs", "input_pdfs"):
        val = data.get(key)
        if isinstance(val, list):
            for item in val:
                s = str(item).strip()
                if s and s not in seen:
                    seen.add(s)
                    ordered.append(s)
        elif isinstance(val, str) and val.strip():
            s = val.strip()
            if s not in seen:
                seen.add(s)
                ordered.append(s)
    one = data.get("pdf_path")
    if isinstance(one, str) and one.strip():
        s = one.strip()
        if s not in seen:
            ordered.append(s)
    return ordered


def allocate_output_pdf(output_dir: Path, pdf_name: str) -> Path:
    """与 register_inputs 默认命名一致：{stem}-checked.pdf"""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf_name).stem
    base = output_dir / f"{stem}-checked.pdf"
    if not base.exists():
        return base
    i = 1
    while True:
        cand = output_dir / f"{stem}-checked_{i}.pdf"
        if not cand.exists():
            return cand
        i += 1


def run_one_pdf(
    cli: TeXAgentCLI,
    workflow_name: str,
    pdf_abs: Path,
    checklist_abs: Path,
    output_abs: Path,
    *,
    use_loading: bool,
) -> Tuple[bool, str]:
    payload = {
        "pdf_path": str(pdf_abs),
        "checklist_path": str(checklist_abs),
        "output_path": str(output_abs),
    }
    user_input = json.dumps(payload, ensure_ascii=False)
    try:
        result = cli.run_task(
            user_input,
            workflow_name=workflow_name,
            use_loading=use_loading,
        )
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        if is_connection_failure_exc(e):
            raise ConnectionAbort(str(e)) from e
        return False, str(e)

    err = (result or {}).get("error") or ""
    if err and is_connection_failure_text(err):
        raise ConnectionAbort(err)

    output_ok = output_abs.is_file() and output_abs.stat().st_size > 512
    if output_ok:
        # state.error 使用 first-error-wins：并行分支曾失败时可能仍残留错误，但 PDF 已生成则算成功
        if err:
            return True, f"已生成批注 PDF（工作流曾报错，可忽略）: {err[:240]}"
        return True, ""

    if err:
        return False, err
    return False, f"工作流未报错但输出 PDF 不存在: {output_abs}"


def _merge_cli_into_config(
    data: Dict[str, Any],
    *,
    pdfs: List[str] | None,
    checklist: str | None,
    output_dir: str | None,
    workflow: str | None,
) -> Dict[str, Any]:
    merged = dict(data)
    if pdfs:
        merged["pdf_paths"] = pdfs
    if checklist:
        merged["checklist_path"] = checklist
    if output_dir:
        merged["output_dir"] = output_dir
    if workflow:
        merged["workflow"] = workflow
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量执行 checklist_text_v3 文本审查（结构化路径输入，preflight 不调用 LLM）"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="运行配置 JSON（默认 config/run_config_text.json，若存在）",
    )
    parser.add_argument(
        "--pdfs",
        nargs="+",
        default=None,
        help="待审查 PDF 路径（可多个，支持绝对路径或相对项目根）",
    )
    parser.add_argument(
        "--checklist",
        default=None,
        help="审查清单路径（.md/.txt/.json 等）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="输出目录，每篇生成 {原名}-checked.pdf",
    )
    parser.add_argument(
        "--workflow",
        default=None,
        help=f"工作流名称（默认 {DEFAULT_WORKFLOW}）",
    )
    parser.add_argument(
        "--no-loading",
        action="store_true",
        help="关闭终端旋转进度条",
    )
    parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="跳过模型连通性探测（不推荐）",
    )
    args = parser.parse_args()

    data: Dict[str, Any] = {}
    cfg_path: Path | None = None
    if args.config is not None:
        cfg_path = args.config if args.config.is_absolute() else ROOT / args.config
        try:
            data = _load_run_config(cfg_path)
        except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"❌ 读取配置失败: {e}", file=sys.stderr)
            return EXIT_ERR
    elif DEFAULT_CONFIG.is_file():
        cfg_path = DEFAULT_CONFIG
        try:
            data = _load_run_config(cfg_path)
        except (OSError, json.JSONDecodeError) as e:
            print(f"❌ 读取默认配置失败: {e}", file=sys.stderr)
            return EXIT_ERR

    data = _merge_cli_into_config(
        data,
        pdfs=args.pdfs,
        checklist=args.checklist,
        output_dir=args.output_dir,
        workflow=args.workflow,
    )

    workflow_name = (data.get("workflow") or data.get("workflow_name") or DEFAULT_WORKFLOW).strip()

    pdf_entries = collect_pdf_paths(data)
    if not pdf_entries:
        print(
            "❌ 未指定任何 PDF。请使用 --pdfs，或在配置中设置 pdf_paths。",
            file=sys.stderr,
        )
        return EXIT_ERR

    checklist_raw = data.get("checklist_path")
    if not isinstance(checklist_raw, str) or not checklist_raw.strip():
        print("❌ 缺少 checklist_path（--checklist 或配置文件）", file=sys.stderr)
        return EXIT_ERR

    output_raw = data.get("output_dir") or data.get("output_path")
    if not isinstance(output_raw, str) or not output_raw.strip():
        print("❌ 缺少 output_dir（--output-dir 或配置文件）", file=sys.stderr)
        return EXIT_ERR

    checklist_abs = resolve_path(checklist_raw, ROOT)
    output_dir = resolve_path(output_raw, ROOT)
    if not checklist_abs.is_file():
        print(f"❌ checklist 不存在: {checklist_abs}", file=sys.stderr)
        return EXIT_ERR

    if not args.skip_probe:
        try:
            probe_model_connectivity()
        except ConnectionAbort as e:
            print(f"❌ 模型连接检查未通过，已中止:\n{e}", file=sys.stderr)
            return EXIT_CONNECT

    print(display.banner("checklist_text 批处理", f"工作流: {workflow_name}"))
    if cfg_path:
        print(f"配置: {cfg_path}")
    print(f"checklist: {checklist_abs}")
    print(f"输出目录: {output_dir}\n")

    cli = TeXAgentCLI(use_branch=True)
    use_loading = not args.no_loading
    any_failed = False
    ran_any = False
    ok_count = 0
    total = len(pdf_entries)

    for idx, raw_pdf in enumerate(pdf_entries, start=1):
        pdf_abs = resolve_path(raw_pdf, ROOT)
        if not pdf_abs.is_file():
            print(f"[{idx}/{total}] ⏭ 跳过（文件不存在）: {raw_pdf} -> {pdf_abs}")
            continue

        ran_any = True
        out_pdf = allocate_output_pdf(output_dir, pdf_abs.name)
        print(f"[{idx}/{total}] ▶ {pdf_abs.name}  →  {out_pdf.name}")

        try:
            ok, err = run_one_pdf(
                cli,
                workflow_name,
                pdf_abs,
                checklist_abs,
                out_pdf,
                use_loading=use_loading,
            )
        except ConnectionAbort as e:
            print(f"❌ 连接/传输错误，停止后续任务: {e}", file=sys.stderr)
            return EXIT_CONNECT
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断，已停止。", file=sys.stderr)
            return EXIT_ERR
        except Exception as e:
            any_failed = True
            print(f"   ✗ 未预期异常（继续下一个）: {e}", file=sys.stderr)
            traceback.print_exc()
            continue

        if ok:
            ok_count += 1
            print(f"   ✓ 完成：{out_pdf}")
        else:
            any_failed = True
            print(f"   ✗ 失败（继续下一个）: {err}")

    if not ran_any:
        print("⚠️ 没有可处理的 PDF（均已跳过或列表为空）", file=sys.stderr)
        return EXIT_ERR

    print(
        f"\n── 批处理结束：成功 {ok_count} 个"
        + ("，失败/跳过项见上文" if any_failed else "，全部成功")
        + " ──"
    )
    return EXIT_ERR if any_failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
