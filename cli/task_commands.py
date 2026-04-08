# cli/task_commands.py
"""
任务执行命令
"""
from typing import Any
from cli.commands import Command
from utils.display import display


class TaskCommand(Command):
    """执行任务命令"""
    
    def __init__(self):
        super().__init__(
            name="task",
            description="执行论文写作任务",
            usage="task <任务描述>"
        )
    
    def execute(self, args: str, cli) -> bool:
        if not args.strip():
            print("❌ 请提供任务描述")
            print("   示例: task 请帮我写一篇关于 Transformer 的论文引言")
            return True
        
        print("\n" + display.separator())
        result = cli.run_task(args.strip())
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