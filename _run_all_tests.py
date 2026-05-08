"""
综合测试脚本：
  Test A: arxiv_research_user workflow (tool + user 节点)
  Test B: file_analysis workflow (file_loading tool)
  Test C: plan 模式（动态规划含并行）

运行：$env:PYTHONUTF8="1"; E:\myconda\open-webui\python.exe _run_all_tests.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _print_separator(title: str, width: int = 70):
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}")

def _print_result_summary(label: str, result: dict):
    """打印节点执行摘要。"""
    meta = result.get("metadata", {})
    order = meta.get("__execution_order__", [])
    output = result.get("output", "")
    error  = result.get("error")

    print(f"\n[状态] {'ERROR: ' + str(error) if error else 'OK'}")
    print(f"[执行顺序] {' -> '.join(order)}")
    print(f"[最终输出] ({len(output)} chars)")
    if output:
        print(output[:1500])
    else:
        print("  (无 state.output，查看 metadata)")

    node_keys = [k for k in meta if not k.startswith("__") and isinstance(meta[k], dict)]
    print(f"\n[节点结果摘要]")
    for k in node_keys:
        nd = meta[k]
        res_preview = str(nd.get("result", ""))[:100]
        conf = nd.get("confidence", "N/A")
        status = nd.get("status", "?")
        print(f"  [{status}] {k}: conf={conf} | {res_preview}...")

    # 写详细结果到日志
    os.makedirs("logs", exist_ok=True)
    with open("logs/llm_interactions_trace.txt", "a", encoding="utf-8") as f:
        f.write(f"\n\n{'='*60}\n")
        f.write(f"Test: {label}\n")
        f.write(f"Exec order: {order}\n")
        f.write(f"Output:\n{output}\n")
        for k in node_keys:
            nd = meta[k]
            f.write(f"\n--- Node: {k} ---\n")
            f.write(f"status={nd.get('status')} conf={nd.get('confidence')}\n")
            f.write(f"result:\n{nd.get('result','')}\n")

# ──────────────────────────────────────────────────────────────────────────────
# 初始化 CLI（共用实例）
# ──────────────────────────────────────────────────────────────────────────────

def _build_auto_input_provider(answers: list):
    """构造按顺序自动回答 user 节点的提供器。"""
    idx = {"n": 0}
    def provider(prompt: str, schema: dict, rules: dict) -> str:
        n = idx["n"]
        answer = answers[n] if n < len(answers) else ""
        idx["n"] += 1
        options = schema.get("options", [])
        print(f"\n  [USER_NODE 自动回答 #{n+1}]")
        print(f"  Prompt: {prompt[:120]}...")
        if options:
            print(f"  Options: {options}")
        print(f"  Auto-answer: {repr(answer)}")
        return answer
    return provider

# ──────────────────────────────────────────────────────────────────────────────
# Test A: arxiv_research_user workflow
# ──────────────────────────────────────────────────────────────────────────────

def run_test_a():
    _print_separator("Test A: arxiv_research_user  (tool: arxiv_search + user 节点)")

    from core.agent_cli import TeXAgentCLI
    from workflow.graph_builder import build_app_from_workflow
    from core.state import normalize_messages_for_state
    from workflow.run_dump import create_run_output_dir
    from datetime import datetime

    # 自动回答 user 节点：1) 主题输入, 2) 质量评价
    auto_answers = [
        "大语言模型推理能力",           # topic_collector
        "基本满意，生成报告",           # user_quality_gate
    ]

    # 注册新 workflow
    from workflow.workflow_registry import WorkflowRegistry
    registry = WorkflowRegistry()

    # 构建 app
    try:
        from workflow.workflow_parser import YAMLWorkflowParser
        parser = YAMLWorkflowParser()
        cfg = parser.load_config("config/workflow/workflow_arxiv_research_user.json")
        nodes = parser.parse_nodes(cfg)
        edges = parser.parse_edges(cfg)
        from context.context_manager import ContextManager
        ctx = ContextManager(max_messages=50, default_limit=10)
        from memory.persona_memory import UserPersonaMemory
        persona = UserPersonaMemory()

        provider = _build_auto_input_provider(auto_answers)

        from workflow.graph_builder import build_dynamic_graph
        app = build_dynamic_graph(
            nodes=nodes,
            edges=edges,
            context_manager=ctx,
            persona_memory=persona,
            human_input_provider=provider,
        )
    except Exception as e:
        print(f"  [BUILD ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    run_dir = create_run_output_dir()
    initial_state = {
        "messages": [],
        "current_node": "",
        "input": "大语言模型推理能力研究",
        "output": "",
        "error": None,
        "metadata": {
            "workflow": "arxiv_research_user",
            "timestamp": datetime.now().isoformat(),
            "__run_output_dir__": str(run_dir),
        },
        "retrieved_context": "",
    }
    print(f"\n  图构建成功，开始执行（run_dir={run_dir}）...")
    t0 = time.time()
    try:
        result = app.invoke(initial_state)
        print(f"  完成，耗时 {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  [INVOKE ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    _print_result_summary("Test A: arxiv_research_user", result)
    return result

# ──────────────────────────────────────────────────────────────────────────────
# Test B: file_analysis workflow
# ──────────────────────────────────────────────────────────────────────────────

def run_test_b():
    _print_separator("Test B: file_analysis  (tool: file_loading)")

    from workflow.workflow_parser import YAMLWorkflowParser
    from workflow.graph_builder import build_dynamic_graph
    from workflow.run_dump import create_run_output_dir
    from context.context_manager import ContextManager
    from memory.persona_memory import UserPersonaMemory
    from datetime import datetime

    parser = YAMLWorkflowParser()
    try:
        cfg = parser.load_config("config/workflow/workflow_file_analysis.json")
        nodes = parser.parse_nodes(cfg)
        edges = parser.parse_edges(cfg)
        ctx = ContextManager(max_messages=50, default_limit=10)
        persona = UserPersonaMemory()
        app = build_dynamic_graph(
            nodes=nodes,
            edges=edges,
            context_manager=ctx,
            persona_memory=persona,
        )
    except Exception as e:
        print(f"  [BUILD ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    run_dir = create_run_output_dir()
    initial_state = {
        "messages": [],
        "current_node": "",
        "input": "分析 workflow_parallel_conditional_demo.json 的设计质量和改进点",
        "output": "",
        "error": None,
        "metadata": {
            "workflow": "file_analysis",
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

    _print_result_summary("Test B: file_analysis", result)
    return result

# ──────────────────────────────────────────────────────────────────────────────
# Test C: Plan 模式（含并行可能性）
# ──────────────────────────────────────────────────────────────────────────────

def run_test_c():
    _print_separator("Test C: Plan 模式（动态规划）")

    from workflow.workflow_parser import YAMLWorkflowParser
    from workflow.graph_builder import build_dynamic_graph
    from workflow.run_dump import create_run_output_dir
    from context.context_manager import ContextManager
    from memory.persona_memory import UserPersonaMemory
    from router.planner import AutoAgentsMASPlanner
    from config.planner_config import MAX_PLAN_ROUNDS_DEFAULT
    from datetime import datetime

    task = (
        "请帮我研究 Retrieval-Augmented Generation (RAG) 在大语言模型中的应用这一主题，"
        "分析其核心技术原理、典型应用场景和最新进展，并给出学习路线建议。"
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

    print("\n  [2/4] 分配 Agent 类型...")
    plan = planner.assign(plan, [])

    print("\n  [3/4] 解析图配置...")
    try:
        nodes, edges = parser.from_task_plan(plan)
        print(f"  解析完成: {len(nodes)} 节点, {len(edges)} 条边")
        for n in nodes:
            print(f"    - [{n.node_type}] {n.node_id}")
    except Exception as e:
        print(f"  [PARSE ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    print("\n  [4/4] 构建并运行动态图...")
    try:
        app = parser.build_graph(
            nodes, edges,
            context_manager=ctx,
            persona_memory=persona,
        )
    except Exception as e:
        print(f"  [BUILD ERROR] {e}")
        import traceback; traceback.print_exc()
        return None

    run_dir = create_run_output_dir()
    initial_state = {
        "messages": [],
        "current_node": "",
        "input": task,
        "output": "",
        "error": None,
        "metadata": {
            "workflow": "plan_dynamic",
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

    _print_result_summary("Test C: plan_dynamic", result)
    return result

# ──────────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_choice = sys.argv[1] if len(sys.argv) > 1 else "all"

    _print_separator("综合测试开始", 70)
    print(f"运行范围: {test_choice}")

    results = {}

    if test_choice in ("all", "a"):
        results["A"] = run_test_a()

    if test_choice in ("all", "b"):
        results["B"] = run_test_b()

    if test_choice in ("all", "c"):
        results["C"] = run_test_c()

    _print_separator("测试完成", 70)
    for k, v in results.items():
        status = "OK" if v and not v.get("error") else "FAIL"
        print(f"  Test {k}: {status}")
    print(f"\n详细日志已写入 logs/llm_interactions_trace.txt")
    print(f"节点 IO 已写入 output/<timestamp>/ 目录")
