#!/usr/bin/env python3
"""
无 UI 批量执行 checklist_multi（v1/v2/v3）。

配置：config/run_config.json（模板见 config/run_config.example.json）
输入目录约定：files/input、files/checklist；输出 files/output；成功后原稿归档 files/checked。
"""
from __future__ import annotations

import argparse
import errno
import json
import shutil
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

DEFAULT_CONFIG = ROOT / "config" / "run_config.json"
FILES_INPUT = ROOT / "files" / "input"
FILES_CHECKLIST = ROOT / "files" / "checklist"
FILES_OUTPUT = ROOT / "files" / "output"
FILES_CHECKED = ROOT / "files" / "checked"

_VERSION_TO_WORKFLOW = {
    "v1": "checklist_multi_v1",
    "v2": "checklist_multi_v2",
    "v3": "checklist_multi_v3",
    "1": "checklist_multi_v1",
    "2": "checklist_multi_v2",
    "3": "checklist_multi_v3",
}

EXIT_OK = 0
EXIT_ERR = 1
EXIT_CONNECT = 2


class ConnectionAbort(Exception):
    """模型或网络连接失败，应停止整批任务。"""


# 用于「异常对象」回退判断（略宽，但避免匹配普通业务报错里的 timeout/unreachable 等词）
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
    """判断 error 文本是否像网络/连接层失败；已去掉过宽的 timeout/unreachable 等子串以免误判。"""
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
    """启动前探测 Gemini（MultiSimpleAgent）与 OpenAI 兼容通道（SimpleAgent）是否可达。"""
    import os

    gem_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    model = (os.getenv("GEMINI_MODEL") or "gemini-3-flash-preview").strip()
    errs: List[str] = []

    if not gem_key:
        errs.append("未配置 GEMINI_API_KEY 或 GOOGLE_API_KEY（checklist_multi 审查节点必需）")
    else:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gem_key)
            client.models.generate_content(
                model=model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=4),
            )
        except Exception as e:  # noqa: BLE001
            errs.append(f"Gemini 连通性检查失败 ({model}): {e}")

    if not (settings.openai_api_key or "").strip():
        errs.append("未配置 OPENAI_API_KEY（annotation_formatter / final_report 等节点必需）")
    else:
        try:
            from openai import OpenAI

            oc = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=25.0,
            )
            oc.models.list()
        except Exception as e:  # noqa: BLE001
            errs.append(f"OpenAI 兼容 API 连通性检查失败: {e}")

    if errs:
        raise ConnectionAbort("\n".join(errs))


def _load_run_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到 {path}，请将 config/run_config.example.json 复制为 config/run_config.json 并填写内容。"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_workflow_name(data: Dict[str, Any]) -> str:
    wf = (data.get("workflow") or data.get("workflow_name") or "").strip()
    if wf:
        return wf
    ver_raw = data.get("version", "v1")
    ver = str(ver_raw).strip().lower()
    if ver in _VERSION_TO_WORKFLOW:
        return _VERSION_TO_WORKFLOW[ver]
    if ver.startswith("checklist_multi_"):
        return ver
    raise ValueError(
        f"无法解析工作流：version={ver_raw!r}。请使用 v1/v2/v3，或设置 workflow。"
    )


def resolve_asset_path(raw: str, base_dir: Path) -> Path:
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


def uniquify_path(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suf = path.suffix
    i = 1
    while True:
        cand = parent / f"{stem}_{i}{suf}"
        if not cand.exists():
            return cand
        i += 1


def allocate_output_pdf(output_dir: Path, original_filename: str) -> Path:
    stem = Path(original_filename).stem
    output_dir.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        p = output_dir / f"{stem}_checked_v{n}.pdf"
        if not p.exists():
            return p
        n += 1


def archive_original_on_success(src_pdf: Path) -> None:
    """成功后将「原稿」放入 files/checked：在 files/input 下则用 move，否则 copy2。"""
    if not src_pdf.is_file():
        return
    FILES_CHECKED.mkdir(parents=True, exist_ok=True)
    src_r = src_pdf.resolve()
    input_root = FILES_INPUT.resolve()
    dest = uniquify_path(FILES_CHECKED / src_r.name)
    try:
        if src_r.parent == input_root or input_root in src_r.parents:
            shutil.move(str(src_r), str(dest))
        else:
            shutil.copy2(str(src_r), str(dest))
    except OSError as e:
        print(f"⚠️  归档原文件到 files/checked 失败（可手动处理）: {e}")


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

    if err:
        return False, err
    if not output_abs.is_file():
        return False, f"工作流未报错但输出 PDF 不存在: {output_abs}"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="批量执行 checklist_multi（读取 config/run_config.json）")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="运行配置（默认 config/run_config.json）",
    )
    parser.add_argument(
        "--version",
        choices=("v1", "v2", "v3"),
        default=None,
        help="覆盖配置文件中的 version",
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
    cfg_path = args.config if args.config.is_absolute() else ROOT / args.config

    try:
        data = _load_run_config(cfg_path)
    except (OSError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ 读取配置失败: {e}", file=sys.stderr)
        return EXIT_ERR

    if args.version:
        data["version"] = args.version

    try:
        workflow_name = _resolve_workflow_name(data)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return EXIT_ERR

    pdf_entries = collect_pdf_paths(data)
    if not pdf_entries:
        print("❌ run_config 中未配置任何 PDF（pdf_path 或 pdf_paths）", file=sys.stderr)
        return EXIT_ERR

    checklist_raw = data.get("checklist_path")
    if not isinstance(checklist_raw, str) or not checklist_raw.strip():
        print("❌ run_config 缺少 checklist_path", file=sys.stderr)
        return EXIT_ERR

    checklist_abs = resolve_asset_path(checklist_raw, FILES_CHECKLIST)
    if not checklist_abs.is_file():
        print(f"❌ checklist 不存在，跳过全部任务: {checklist_abs}", file=sys.stderr)
        return EXIT_ERR

    if not args.skip_probe:
        try:
            probe_model_connectivity()
        except ConnectionAbort as e:
            print(f"❌ 模型连接检查未通过，已中止:\n{e}", file=sys.stderr)
            return EXIT_CONNECT

    FILES_INPUT.mkdir(parents=True, exist_ok=True)
    FILES_CHECKLIST.mkdir(parents=True, exist_ok=True)
    FILES_OUTPUT.mkdir(parents=True, exist_ok=True)
    FILES_CHECKED.mkdir(parents=True, exist_ok=True)

    print(display.banner("checklist_multi 批处理", f"工作流: {workflow_name}"))
    print(f"配置: {cfg_path}")
    print(f"checklist: {checklist_abs}\n")

    cli = TeXAgentCLI(use_branch=True)
    use_loading = not args.no_loading
    any_failed = False
    ran_any = False
    ok_count = 0
    total = len(pdf_entries)

    for idx, raw_pdf in enumerate(pdf_entries, start=1):
        pdf_abs = resolve_asset_path(raw_pdf, FILES_INPUT)
        label = raw_pdf
        if not pdf_abs.is_file():
            print(f"[{idx}/{total}] ⏭ 跳过（文件不存在）: {label} -> {pdf_abs}")
            continue

        ran_any = True
        out_pdf = allocate_output_pdf(FILES_OUTPUT, pdf_abs.name)
        print(f"[{idx}/{total}] ▶ {pdf_abs.name}  → 输出 {out_pdf.name}")

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
            archive_original_on_success(pdf_abs)
            print(f"   ✓ 完成：批注已写入 {out_pdf}")
            print(f"     原稿已归档到 files/checked/（若在 files/input 则为移动，否则为复制）")
        else:
            any_failed = True
            print(f"   ✗ 失败（继续下一个）: {err}")

    if not ran_any:
        print("⚠️ 没有可处理的 PDF（均已跳过或列表为空）", file=sys.stderr)
        return EXIT_ERR

    print(
        f"\n── 批处理结束：成功 {ok_count} 个"
        + (f"，失败/跳过项见上文" if any_failed else "，全部成功")
        + " ──"
    )
    return EXIT_ERR if any_failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
