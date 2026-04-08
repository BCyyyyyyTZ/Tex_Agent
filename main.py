#main.py
"""
TeX_Agent 程序主入口。
启动 Design → Think → Execute 基础工作流链路，验证 MVP 端到端可运行性。

运行方式：
    # 交互式输入任务：
    python main.py

    # 命令行直接传入任务：
    python main.py 帮我检索关于 large language model 的最新论文

配置：
    复制 .env.example 为 .env，填入 OPENAI_API_KEY 后运行。
"""
import sys

from utils.logger import get_logger
from workflow.graph_builder import build_graph
from core.state import WorkflowState
from context.context_manager import ContextManager

logger = get_logger(__name__)

# MVP 示例任务（未提供输入时使用）
DEFAULT_TASK = (
    "请帮我检索关于 large language model 的最新论文，"
    "分析研究现状，并给出 Related Work 章节的写作框架建议。"
)


def run_workflow(user_input: str) -> dict:
    """
    执行 TeX_Agent 完整工作流（Design → Think → Execute）。

    Args:
        user_input: 用户的论文写作任务描述文本。

    Returns:
        最终 WorkflowState 字典，关键字段：
        - output: 工作流最终输出结果
        - messages: 所有节点产生的消息历史列表
        - error: 执行过程中的错误信息（正常时为 None）

    Raises:
        Exception: 工作流构建失败或配置错误时。
    """
    ctx = ContextManager(max_messages=200, default_limit=20)
    app = build_graph(context_manager=ctx)

    initial_state: WorkflowState = {
        "messages": [],
        "current_node": "",
        "input": user_input,
        "output": "",
        "error": None,
        "metadata": {},
        "retrieved_context": "",  # RAG 未启用时保持空字符串
    }

    logger.info(f"工作流启动 | 任务: {user_input[:60]}{'...' if len(user_input) > 60 else ''}")
    result = app.invoke(initial_state)
    logger.info("工作流执行完毕")

    return result


def _print_banner() -> None:
    """打印欢迎横幅。"""
    print("\n" + "=" * 65)
    print("  TeX_Agent — LaTeX 论文写作增强系统  (MVP v0.1)")
    print("  基于 LangGraph 多智能体架构")
    print("=" * 65)


def _print_result(result: dict) -> None:
    """格式化打印工作流执行结果。"""
    print("\n" + "=" * 65)
    print("  工作流执行完毕")
    print("=" * 65)

    if result.get("error"):
        print(f"\n⚠  执行过程中出现错误: {result['error']}")

    output = result.get("output", "")
    if output:
        print(f"\n【最终输出】\n{output}")
    else:
        print("\n（工作流未生成输出，请检查日志）")

    msg_count = len(result.get("messages", []))
    print(f"\n{'─' * 65}")
    print(f"  消息历史：{msg_count} 条 | "
          f"执行节点：{result.get('current_node', '未知')}")
    print("=" * 65 + "\n")


def main() -> None:
    """程序主函数，处理命令行参数与交互式输入。"""
    _print_banner()

    # 从命令行参数或交互式输入获取任务
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:]).strip()
        print(f"\n[命令行任务] {user_input}")
    else:
        print("\n请输入您的论文写作任务（直接回车使用默认示例任务）：")
        try:
            user_input = input("\n任务 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n已取消。")
            return

        if user_input.lower() in ("q", "quit", "exit"):
            print("已退出。")
            return
        if not user_input:
            # 直接回车 → 使用默认任务
            user_input = DEFAULT_TASK
            print(f"\n[使用默认任务]\n{user_input}")

    print("\n" + "─" * 65)
    print("正在执行工作流（Design → Think → Execute）...")
    print("─" * 65)

    try:
        result = run_workflow(user_input)
        _print_result(result)

    except KeyboardInterrupt:
        print("\n\n用户中断执行。")
        sys.exit(0)

    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        print(f"\n执行失败：{e}")
        print("\n排查建议：")
        print("  1. 检查 .env 文件中的 OPENAI_API_KEY 是否正确配置")
        print("  2. 检查网络连接是否正常")
        print("  3. 查看上方日志获取详细错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
