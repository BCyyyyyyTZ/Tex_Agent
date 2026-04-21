"""
测试脚本：
  Test D: docling_user_test workflow (docling_parse tool + user 节点 + 全量上游传递)
  Test E: Plan 模式 terminal 节点输出长度测试
  Test F: user 节点 CLI 界面展示（直接模拟）

运行：$env:PYTHONUTF8="1"; E:\myconda\open-webui\python.exe _run_docling_user_test.py [d|e|f]
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(__file__))


def _sep(title, w=70):
    print(f"\n{'='*w}\n  {title}\n{'='*w}")


def _print_result_summary(label, result):
    meta = result.get("metadata", {})
    order = meta.get("__execution_order__", [])
    output = result.get("output", "")
    error = result.get("error")
    print(f"\n[状态] {'ERROR: ' + str(error) if error else 'OK'}")
    print(f"[执行顺序] {' -> '.join(order)}")
    print(f"[最终输出] ({len(output)} chars)")
    if output:
        print(output[:2000])
    node_keys = [k for k in meta if not k.startswith("__") and isinstance(meta[k], dict)]
    print("\n[节点摘要]")
    for k in node_keys:
        nd = meta[k]
        res_len = len(str(nd.get("result", "")))
        conf = nd.get("confidence", "N/A")
        status = nd.get("status", "?")
        summary = str(nd.get("summary", ""))[:80]
        print(f"  [{status}] {k}: conf={conf} result_len={res_len} | {summary}...")
    # 写日志
    os.makedirs("logs", exist_ok=True)
    with open("logs/llm_interactions_trace.txt", "a", encoding="utf-8") as f:
        f.write(f"\n\n{'='*60}\nTest: {label}\nExec: {order}\nOutput ({len(output)} chars):\n{output}\n")
        for k in node_keys:
            nd = meta[k]
            f.write(f"\n--- {k} ---\nresult:\n{nd.get('result','')}\n")


# ─────────────────────────────────────────────────────────────────
# Test D: docling_user_test workflow
# ─────────────────────────────────────────────────────────────────

def run_test_d():
    _sep("Test D: docling_user_test (docling_parse + user 节点 + 全量上游传递)")

    from workflow.workflow_parser import YAMLWorkflowParser
    from workflow.graph_builder import build_dynamic_graph
    from workflow.run_dump import create_run_output_dir
    from context.context_manager import ContextManager
    from memory.persona_memory import UserPersonaMemory
    from datetime import datetime

    auto_answers = [
        "技术实现细节（系统架构和算法）",   # user_focus_selector
    ]
    idx = {"n": 0}

    def auto_provider(prompt: str, schema: dict, rules: dict) -> str:
        n = idx["n"]
        answer = auto_answers[n] if n < len(auto_answers) else ""
        idx["n"] += 1
        # 仍然打印完整 CLI 界面以验证美化效果
        options = schema.get("options", [])
        print(f"\n{'─'*60}")
        print(f"  [用户输入模拟] 节点: user_focus_selector")
        print(f"{'─'*60}")
        prompt_lines = prompt.splitlines()
        for line in prompt_lines[:10]:   # 只打印前10行避免太长
            print(f"  {line[:60]}")
        if len(prompt_lines) > 10:
            print(f"  ... (共 {len(prompt_lines)} 行)")
        if options:
            print(f"\n  可选项：")
            for i, opt in enumerate(options, 1):
                print(f"    [{i}] {opt}")
        print(f"\n  自动回答: {repr(answer)}")
        print(f"{'─'*60}")
        return answer

    parser = YAMLWorkflowParser()
    try:
        cfg = parser.load_config("config/workflow_docling_user_test.json")
        nodes = parser.parse_nodes(cfg)
        edges = parser.parse_edges(cfg)
        ctx = ContextManager(max_messages=50, default_limit=10)
        persona = UserPersonaMemory()
        app = build_dynamic_graph(
            nodes=nodes, edges=edges,
            context_manager=ctx, persona_memory=persona,
            human_input_provider=auto_provider,
        )
    except Exception as e:
        print(f"  [BUILD ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    run_dir = create_run_output_dir()
    initial_state = {
        "messages": [], "current_node": "",
        "input": "解析并分析 Efficient Video Analytics 论文",
        "output": "", "error": None,
        "metadata": {
            "workflow": "docling_user_test",
            "timestamp": datetime.now().isoformat(),
            "__run_output_dir__": str(run_dir),
        },
        "retrieved_context": "",
    }

    print(f"\n  图构建成功，开始执行...")
    t0 = time.time()
    try:
        result = app.invoke(initial_state)
        print(f"  完成，耗时 {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  [INVOKE ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    _print_result_summary("Test D: docling_user_test", result)

    # 专项检查：doc_parser 的 output 是否包含 Markdown 内容预览
    meta = result.get("metadata", {})
    doc_out = meta.get("doc_parser", {}).get("result", "")
    if "Markdown 内容预览" in doc_out or "document.md" in doc_out:
        print("\n  [DOCLING CHECK] docling 工具输出包含文档内容预览 ✓")
    else:
        print(f"\n  [DOCLING CHECK] docling 输出前200字: {doc_out[:200]}")

    return result


# ─────────────────────────────────────────────────────────────────
# Test E: Plan 模式 terminal 节点长度
# ─────────────────────────────────────────────────────────────────

def run_test_e():
    _sep("Test E: Plan 模式 terminal 节点输出长度测试")

    from workflow.workflow_parser import YAMLWorkflowParser
    from workflow.graph_builder import build_dynamic_graph
    from workflow.run_dump import create_run_output_dir
    from context.context_manager import ContextManager
    from memory.persona_memory import UserPersonaMemory
    from router.planner import AutoAgentsMASPlanner
    from config.planner_config import MAX_PLAN_ROUNDS_DEFAULT
    from datetime import datetime

    task = (
        "请分析 Transformer 架构在自然语言处理中的核心创新点，"
        "以及它相比 RNN/LSTM 的主要优势，最后给出学习建议。"
    )
    print(f"\n  任务: {task[:80]}...")

    planner = AutoAgentsMASPlanner(max_plan_rounds=MAX_PLAN_ROUNDS_DEFAULT)
    parser = YAMLWorkflowParser()
    ctx = ContextManager(max_messages=50, default_limit=10)
    persona = UserPersonaMemory()

    print("\n  [1/4] PlanAgent 规划中...")
    t0 = time.time()
    try:
        plan = planner.decompose(task)
    except Exception as e:
        print(f"  [PLAN ERROR] {e}")
        import traceback; traceback.print_exc()
        return None
    print(f"  规划完成（{time.time()-t0:.1f}s），{len(plan.subtasks)} 节点: {plan.subtasks}")

    plan = planner.assign(plan, [])
    nodes, edges = parser.from_task_plan(plan)
    print(f"  解析: {len(nodes)} 节点, {len(edges)} 边")
    for n in nodes:
        print(f"    [{n.node_type}] {n.node_id}")

    try:
        app = parser.build_graph(nodes, edges, context_manager=ctx, persona_memory=persona)
    except Exception as e:
        print(f"  [BUILD ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    run_dir = create_run_output_dir()
    initial_state = {
        "messages": [], "current_node": "",
        "input": task, "output": "", "error": None,
        "metadata": {
            "workflow": "plan_dynamic_e",
            "timestamp": datetime.now().isoformat(),
            "__run_output_dir__": str(run_dir),
        },
        "retrieved_context": "",
    }
    t1 = time.time()
    try:
        result = app.invoke(initial_state)
        print(f"  执行完成，耗时 {time.time()-t1:.1f}s")
    except Exception as e:
        print(f"  [INVOKE ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    _print_result_summary("Test E: plan_dynamic", result)

    output = result.get("output", "")
    print(f"\n  [TERMINAL LENGTH CHECK] output = {len(output)} chars")
    if len(output) >= 300:
        print("  >= 300 chars: PASS ✓")
    else:
        print("  < 300 chars: 仍偏短，需进一步优化")

    return result


# ─────────────────────────────────────────────────────────────────
# Test F: user 节点 CLI 界面展示（无需 LLM，直接测试界面）
# ─────────────────────────────────────────────────────────────────

def run_test_f():
    _sep("Test F: user 节点 CLI 界面交互测试（无 LLM，仅验证界面）")

    from workflow.nodes import make_user_node
    from core.state import WorkflowState
    from datetime import datetime

    print("\n--- 场景1: 单选题 ---")
    auto1 = ["2"]  # 选第2项
    idx1 = {"n": 0}

    def provider1(prompt: str, schema: dict, rules: dict) -> str:
        # 调用真实的 _default_provider 逻辑（此处模拟）
        options = schema.get("options", [])
        print(f"\n{'─'*60}")
        print(f"  [test] prompt preview: {prompt[:100]}")
        print(f"  [test] type={schema.get('type')} options={options}")
        choice = auto1[idx1["n"]] if idx1["n"] < len(auto1) else "1"
        idx1["n"] += 1
        print(f"  [test] auto input: {choice!r}")
        print(f"{'─'*60}")
        return choice

    node_cfg_single = {
        "prompt_template": "请选择数据集处理方式：",
        "input_schema": {"type": "single_choice", "options": ["全量处理", "采样10%", "自定义比例"]},
        "validation": {"required": True},
        "default_value": "采样10%",
        "write_to": "user_input.dataset_mode",
    }
    node_fn = make_user_node(
        node_id="dataset_selector",
        node_config=node_cfg_single,
        human_input_provider=provider1,
    )
    state: WorkflowState = {
        "messages": [], "current_node": "", "input": "test",
        "output": "", "error": None, "metadata": {}, "retrieved_context": "",
    }
    result = node_fn(state)
    meta = result.get("metadata", {})
    print(f"  写入 metadata: {meta.get('user_input', meta.get('dataset_selector', 'N/A'))}")

    print("\n--- 场景2: 文本输入 ---")
    auto2 = ["分析注意力机制的计算复杂度"]
    idx2 = {"n": 0}

    def provider2(prompt: str, schema: dict, rules: dict) -> str:
        val = auto2[idx2["n"]] if idx2["n"] < len(auto2) else ""
        idx2["n"] += 1
        print(f"  [test] text input auto: {val!r}")
        return val

    node_cfg_text = {
        "prompt_template": "请描述您希望深入研究的问题（至少10字）：",
        "input_schema": {"type": "text"},
        "validation": {"required": True, "min_length": 10},
        "write_to": "user_input.research_question",
    }
    node_fn2 = make_user_node(
        node_id="question_collector",
        node_config=node_cfg_text,
        human_input_provider=provider2,
    )
    result2 = node_fn2(state)
    meta2 = result2.get("metadata", {})
    print(f"  写入 metadata: {json.dumps(meta2, ensure_ascii=False, indent=2)[:200]}")
    print("\n  Test F: PASS ✓")
    return True


if __name__ == "__main__":
    test = sys.argv[1] if len(sys.argv) > 1 else "all"

    _sep("docling + user 节点综合测试")

    results = {}
    if test in ("all", "f"):
        results["F"] = run_test_f()
    if test in ("all", "d"):
        results["D"] = run_test_d()
    if test in ("all", "e"):
        results["E"] = run_test_e()

    _sep("测试完成")
    for k, v in results.items():
        status = "OK" if v else "FAIL/SKIP"
        print(f"  Test {k}: {status}")
