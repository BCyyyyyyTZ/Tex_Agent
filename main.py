"""
TeX_Agent 程序主入口

任务执行路径（task / 裸输入 / plan）：
  main → TeXAgentCLI.run_task / run_plan_task → LangGraph app.invoke
  → workflow.graph_builder 为每个 agent 节点实例化
     agents.simple_agent.SimpleAgent（按 config.settings 选择 OpenAI 兼容或 Gemini，避免无 API key 时强绑 Google Genai）。
"""
import sys
import shlex
from core.agent_cli import TeXAgentCLI
from utils.display import display


def parse_task_args(raw_args: str):
    """
    解析 task 参数，支持：
    - task <prompt>
    - task -wf <workflow_name> <prompt>
    - task --wf <workflow_name> <prompt>
    - task --workflow <workflow_name> <prompt>
    - task -wf=<workflow_name> <prompt>
    - task --wf=<workflow_name> <prompt>
    """
    args = raw_args.strip()
    if not args:
        return None, ""

    tokens = shlex.split(args)
    if not tokens:
        return None, ""

    first = tokens[0]
    wf_prefixes = ("-wf=", "--wf=", "--workflow=")
    wf_flags = ("-wf", "--wf", "--workflow")

    # 格式：-wf=name / --wf=name / --workflow=name
    if any(first.startswith(prefix) for prefix in wf_prefixes):
        workflow_name = first.split("=", 1)[1].strip()
        task = " ".join(tokens[1:]).strip()
        return workflow_name or None, task

    # 格式：-wf name / --wf name / --workflow name
    if first in wf_flags:
        if len(tokens) < 2:
            raise ValueError("参数格式错误：-wf/--wf/--workflow 后需要指定工作流名称")
        workflow_name = tokens[1].strip()
        task = " ".join(tokens[2:]).strip()
        return workflow_name or None, task

    return None, args


def print_banner():
    """打印欢迎横幅"""
    print(display.banner(
        "TeX_Agent — LaTeX 论文写作增强系统",
        "基于 LangGraph 多智能体架构 + 分支记忆"
    ))
    print("\n💡 提示: LLM 响应需要 30-60 秒，请耐心等待")
    print("💡 输入 'help' 查看所有命令\n")


def print_help():
    """打印帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════════
║                        可用命令                                   
╠══════════════════════════════════════════════════════════════════
║  task <Prompt>          - 执行默认工作流任务
║  task --wf <name> <Prompt> - 执行指定工作流任务
║  auto <Prompt>          - Auto 模式（当前默认单节点直连）
║  plan <Prompt>          - 执行动态规划任务
║  branch list            - 列出所有分支                                  
║  branch create <name>   - 创建新分支                               
║  branch switch <name>   - 切换分支                                 
║  branch merge  <name>   - 合并分支到主分支                        
║  status                 - 显示系统状态                                  
║  clear                  - 清空所有记忆                                  
║  help                   - 显示此帮助                                    
║  exit, quit             - 退出程序                                      
╚══════════════════════════════════════════════════════════════════
""")


def main():
    """主函数"""
    print_banner()
    
    cli = TeXAgentCLI(use_branch=True)
    cli.show_status()
    print_help()
    
    while True:
        try:
            user_input = input("\n📝 > ").strip()
            if not user_input:
                continue
            
            # 获取原始输入，不提前分割
            original_input = user_input
            parts = user_input.split()
            
            if not parts:
                continue
            
            first_word = parts[0].lower()
            
            # 退出命令
            if first_word in ['exit', 'quit', 'q']:
                print("\n👋 再见！")
                break
            
            # 帮助命令
            elif first_word in ['help', 'h', '?']:
                print_help()
            
            # 状态命令
            elif first_word in ['status', 'info']:
                cli.show_status()
            
            # 清空命令
            elif first_word in ['clear', 'clean', 'reset']:
                cli.clear_all()
            
            # 分支列表 - 支持 "branches", "branch list", "branch ls"
            elif first_word == 'branches' or (first_word == 'branch' and len(parts) > 1 and parts[1] in ['list', 'ls']):
                cli.list_branches()
            
            # 分支显示详情 - "branch show" 或 "branch-show"
            elif first_word == 'branch' and len(parts) > 1 and parts[1] == 'show':
                cli.show_branch_status()
            elif first_word in ['branch-show', 'branch-info']:
                cli.show_branch_status()
            
            # 创建分支 - "branch create" 或 "create"
            elif first_word == 'create' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'create'):
                # 提取分支名称
                if first_word == 'create':
                    # create <name> [from_branch]
                    if len(parts) >= 2:
                        branch_name = parts[1]
                        from_branch = parts[2] if len(parts) > 2 else "main"
                        cli.create_branch(branch_name, from_branch)
                    else:
                        print("❌ 请指定分支名称")
                        print("   用法: create <分支名> [源分支]")
                else:
                    # branch create <name> [from_branch]
                    if len(parts) >= 3:
                        branch_name = parts[2]
                        from_branch = parts[3] if len(parts) > 3 else "main"
                        cli.create_branch(branch_name, from_branch)
                    else:
                        print("❌ 请指定分支名称")
                        print("   用法: branch create <分支名> [源分支]")
            
            # 切换分支 - "branch switch" 或 "switch"
            elif first_word == 'switch' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'switch'):
                if first_word == 'switch':
                    branch_name = parts[1] if len(parts) > 1 else ""
                else:
                    branch_name = parts[2] if len(parts) > 2 else ""
                
                if not branch_name:
                    print("❌ 请指定分支名称")
                    print("   用法: switch <分支名>  或  branch switch <分支名>")
                else:
                    cli.switch_branch(branch_name)
            
            # 合并分支 - "branch merge" 或 "merge"
            elif first_word == 'merge' or (first_word == 'branch' and len(parts) > 1 and parts[1] == 'merge'):
                if first_word == 'merge':
                    branch_name = parts[1] if len(parts) > 1 else ""
                else:
                    branch_name = parts[2] if len(parts) > 2 else ""
                
                if not branch_name:
                    print("❌ 请指定分支名称")
                    print("   用法: merge <分支名>  或  branch merge <分支名>")
                else:
                    cli.merge_branch(branch_name)
            
            # 动态规划命令（验证 AutoAgentsMASPlanner + build_dynamic_graph）
            elif first_word in ['auto']:
                task = ' '.join(parts[1:]) if len(parts) > 1 else ""
                if not task:
                    print("❌ 请提供任务描述")
                    print("   示例: auto 你好")
                else:
                    print("\n" + display.separator())
                    result = cli.run_auto_task(task)
                    print(display.separator())
                    display.print_result(result)

            elif first_word in ['plan', 'mas']:
                task = ' '.join(parts[1:]) if len(parts) > 1 else ""
                if not task:
                    print("❌ 请提供任务描述")
                    print("   示例: plan 帮我写论文的 Introduction 章节")
                else:
                    print("\n" + display.separator())
                    result = cli.run_plan_task(task)
                    print(display.separator())
                    display.print_result(result)

            # 显式任务命令
            elif first_word in ['task', 'run', 'do']:
                raw_task_args = ' '.join(parts[1:]) if len(parts) > 1 else ""
                try:
                    workflow_name, task = parse_task_args(raw_task_args)
                except ValueError as e:
                    print(f"❌ {e}")
                    print("   用法1: task <任务描述>")
                    print("   用法2: task --wf <工作流名> <任务描述>")
                    print("   示例 : task --wf report_flow 帮我写摘要")
                    continue

                if not task:
                    print("❌ 请提供任务描述")
                    print("   示例1: task 请帮我写一篇关于 Transformer 的论文引言")
                    print("   示例2: task --wf report_flow 帮我写摘要")
                else:
                    print("\n" + display.separator())
                    result = cli.run_task(task, workflow_name=workflow_name)
                    print(display.separator())
                    display.print_result(result)
            
            # 其他输入默认 Auto 单节点（后续可路由 plan/task）
            else:
                print("\n" + display.separator())
                result = cli.run_auto_task(original_input)
                print(display.separator())
                display.print_result(result)
        
        except KeyboardInterrupt:
            print("\n\n⚠️ 使用 'exit' 退出程序")
            continue
        except EOFError:
            print("\n\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()



def run_overleaf():
    """Launch the Overleaf-style LaTeX editor server."""
    from ui.overleaf.server import main as overleaf_main
    overleaf_main()


def quick_run():
    """快速运行模式"""
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:]).strip()
        print(f"\n[快速模式] {user_input[:100]}...")
        
        cli = TeXAgentCLI(use_branch=True)
        result = cli.run_task(user_input)
        
        if result.get("error"):
            print(f"\n❌ 失败: {result['error']}")
        else:
            output = result.get("output", "")
            print(f"\n📄 结果:\n{display.truncate(output)}")
    else:
        main()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ("overleaf", "ol"):
            run_overleaf()
        else:
            quick_run()
    else:
        main()