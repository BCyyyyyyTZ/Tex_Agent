"""
运行 checklist_annotate workflow 对 googlelenet.pdf 进行完整检查 + PDF 注释测试。

用法：
  python _run_checklist_test.py
"""

import sys
import os
import io
import json
import time
import traceback

# Windows GBK 终端下强制 UTF-8 输出，防止 emoji 编码报错
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 保证项目根目录在 sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from main import TeXAgentCLI


def run_checklist_workflow():
    print("\n" + "=" * 70)
    print("  Checklist Annotate Workflow - googlelenet.pdf")
    print("=" * 70)

    cli = TeXAgentCLI()
    task = "请使用 checklist_annotate 工作流对 doc/googlelenet.pdf 进行全面的 checklist 检查，并将检查注释写入 PDF。"

    t0 = time.time()
    try:
        result = cli.run_task(
            user_input=task,
            workflow_name="checklist_annotate_v2",
        )
        elapsed = time.time() - t0

        print(f"\n耗时: {elapsed:.1f}s")
        print(f"\n--- 最终输出 ---")
        if result:
            final_result = result.get("result", "")
            print(final_result[:3000])
            if len(final_result) > 3000:
                print(f"... [共 {len(final_result)} 字符，已截断显示]")

            # 检查各节点状态
            meta = result.get("metadata", {}) or {}
            print(f"\n--- 节点执行概览 ---")
            key_nodes = [
                "parse_paper", "load_checklist",
                "get_outline", "slice_abstract", "slice_experiment", "slice_refs",
                "abstract_checker", "structure_checker", "language_checker",
                "figure_checker", "experiment_checker", "layout_checker",
                "annotation_formatter", "location_resolver", "pdf_annotator", "final_report"
            ]
            for node_id in key_nodes:
                node_meta = meta.get(node_id)
                if node_meta:
                    status = node_meta.get("status", "?")
                    conf = node_meta.get("confidence", "N/A")
                    result_len = len(str(node_meta.get("result", "") or ""))
                    summary = (node_meta.get("summary") or "")[:60]
                    print(f"  [{node_id:25s}] status={status}, conf={conf}, result_len={result_len}, summary={summary!r}")
                else:
                    print(f"  [{node_id:25s}] (未执行或无元数据)")

            # 检查 PDF 注释文件
            annotated_pdf = "doc/googlelenet_checklist_v2.pdf"
            if os.path.exists(annotated_pdf):
                size_kb = os.path.getsize(annotated_pdf) / 1024
                print(f"\n[OK] 注释 PDF 已生成: {annotated_pdf}  ({size_kb:.1f} KB)")
            else:
                print(f"\n[WARN] 注释 PDF 未生成: {annotated_pdf}")

        else:
            print("(result is None)")

    except Exception as e:
        print(f"\n[FAIL] 执行失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    run_checklist_workflow()
