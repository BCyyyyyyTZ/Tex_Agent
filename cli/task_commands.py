# cli/task_commands.py
"""
任务执行命令
"""
from typing import Optional, Tuple
import shlex
from cli.commands import Command
from utils.display import display


class TaskCommand(Command):
    """执行任务命令"""
    
    def __init__(self):
        super().__init__(
            name="task",
            description="执行任务（支持默认/指定工作流）",
            usage="task [-wf 工作流名] [-b 分支名] <任务描述>"
        )

    def _parse_task_args(self, args: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        解析 task 命令参数。
        支持：
          -wf / --wf / --workflow <name>
          -b  / --branch <name>
        返回：(workflow_name, branch_name, task_text)
        """
        tokens = shlex.split(args)
        workflow_name: Optional[str] = None
        branch_name: Optional[str] = None
        task_tokens = []

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-wf", "--wf", "--workflow"):
                if i + 1 >= len(tokens):
                    raise ValueError("参数错误：-wf/--workflow 后缺少工作流名称")
                workflow_name = tokens[i + 1].strip()
                i += 2
                continue
            if tok in ("-b", "--branch"):
                if i + 1 >= len(tokens):
                    raise ValueError("参数错误：-b/--branch 后缺少分支名称")
                branch_name = tokens[i + 1].strip()
                i += 2
                continue
            task_tokens.append(tok)
            i += 1

        task_text = " ".join(task_tokens).strip()
        return workflow_name, branch_name, task_text
    
    def execute(self, args: str, cli) -> bool:
        if not args.strip():
            print("❌ 请提供任务描述")
            print("   示例1: task 请帮我写一篇关于 Transformer 的论文引言")
            print("   示例2: task -wf report_flow 帮我写摘要")
            return True

        try:
            workflow_name, branch_name, task_text = self._parse_task_args(args)
        except ValueError as e:
            print(f"❌ {e}")
            print("   用法: task [-wf 工作流名] [-b 分支名] <任务描述>")
            return True

        if not task_text:
            print("❌ 请提供任务描述")
            print("   用法: task [-wf 工作流名] [-b 分支名] <任务描述>")
            return True

        print("\n" + display.separator())
        result = cli.run_task(
            task_text,
            branch=branch_name,
            workflow_name=workflow_name,
        )
        print(display.separator())
        
        display.print_result(result)
        return True


class StatusCommand(Command):
    """状态命令"""
    
    def __init__(self):
        super().__init__(
            name="status",
            description="显示系统状态",
            usage="status"
        )
    
    def execute(self, args: str, cli) -> bool:
        cli.show_status()
        return True


class ClearCommand(Command):
    """清空命令"""
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="清空所有记忆和对话",
            usage="clear"
        )
    
    def execute(self, args: str, cli) -> bool:
        cli.clear_all()
        return True


class ExitCommand(Command):
    """退出命令"""
    
    def __init__(self):
        super().__init__(
            name="exit",
            description="退出程序",
            usage="exit"
        )
    
    def execute(self, args: str, cli) -> bool:
        print("\n👋 再见！")
        return False  # 返回 False 表示退出


class HelpCommand(Command):
    """帮助命令"""
    
    def __init__(self, registry):
        self.registry = registry
        super().__init__(
            name="help",
            description="显示帮助信息",
            usage="help"
        )
    
    def execute(self, args: str, cli) -> bool:
        print(self.registry.show_help())
        return True


def get_task_commands(registry):
    """获取任务相关命令"""
    return [
        TaskCommand(),
        StatusCommand(),
        ClearCommand(),
        ExitCommand(),
        HelpCommand(registry),
    ]