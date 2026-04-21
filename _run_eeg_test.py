"""运行 checklist_annotate_v3 workflow 测试 EEG_Image_补充.pdf"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import time
from core.agent_cli import TeXAgentCLI

os.chdir(os.path.dirname(os.path.abspath(__file__)))

cli = TeXAgentCLI()
task = "请使用 checklist_annotate_v3 workflow 对 doc/EEG_Image_补充.pdf 进行全面检查，生成带彩色注释的 PDF 和审稿报告。"

t0 = time.time()
result = cli.run_task(
    user_input=task,
    workflow_name="checklist_annotate_v3",
)
elapsed = time.time() - t0
print(f"\n耗时: {elapsed:.1f}s")
print("\n--- 最终输出 ---")
if result and hasattr(result, 'get'):
    print(str(result.get('output', ''))[:800])

print("\n--- 节点执行概览 ---")
meta = result.get('metadata', {}) if result else {}
key_nodes = [
    "parse_paper", "get_outline",
    "slice_intro", "slice_method", "slice_analysis",
    "abstract_checker", "structure_checker", "language_checker",
    "content_checker", "figure_checker", "layout_checker",
    "annotation_formatter", "location_resolver", "pdf_annotator", "final_report"
]
for n in key_nodes:
    nd = meta.get(n)
    if nd:
        st = nd.get('status','?')
        cf = nd.get('confidence', 0)
        rl = len(str(nd.get('result','')))
        sm = str(nd.get('summary',''))[:90].replace('\n',' ')
        print(f"  [{n:25}] status={st}, conf={cf}, result_len={rl}, summary='{sm}'")
    else:
        print(f"  [{n:25}] (未执行或无元数据)")

annotated_pdf = "doc/EEG_Image_补充_annotated.pdf"
if os.path.exists(annotated_pdf):
    size_kb = os.path.getsize(annotated_pdf) / 1024
    print(f"\n[OK] 注释 PDF 已生成: {annotated_pdf}  ({size_kb:.1f} KB)")
else:
    print(f"\n[WARN] 注释 PDF 未生成: {annotated_pdf}")
