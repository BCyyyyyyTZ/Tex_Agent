# cli/branch_commands.py
"""
分支管理命令
"""
from typing import Any
from cli.commands import Command


class ListBranchesCommand(Command):
    """列出分支命令"""
    
    def __init__(self):
        super().__init__(
            name="branches",
            description="列出所有分支",
            usage="branches"
        )
    
    def execute(self, args: str, cli) -> bool:
        cli.list_branches()
        return True


class CreateBranchCommand(Command):
    """创建分支命令"""
    
    def __init__(self):
        super().__init__(
            name="branch-create",
            description="创建新分支",
            usage="branch-create <name> [from_branch]"
        )
    
    def execute(self, args: str, cli) -> bool:
        parts = args.split()
        if not parts:
            print("❌ 请指定分支名称")
            return True
        
        branch_name = parts[0]
        from_branch = parts[1] if len(parts) > 1 else "main"
        cli.create_branch(branch_name, from_branch)
        return True


class SwitchBranchCommand(Command):
    """切换分支命令"""
    
    def __init__(self):
        super().__init__(
            name="branch-switch",
            description="切换分支",
            usage="branch-switch <name>"
        )
    
    def execute(self, args: str, cli) -> bool:
        if not args.strip():
            print("❌ 请指定分支名称")
            return True
        cli.switch_branch(args.strip())
        return True


class MergeBranchCommand(Command):
    """合并分支命令"""
    
    def __init__(self):
        super().__init__(
            name="branch-merge",
            description="合并分支到主分支",
            usage="branch-merge <name>"
        )
    
    def execute(self, args: str, cli) -> bool:
        if not args.strip():
            print("❌ 请指定分支名称")
            return True
        cli.merge_branch(args.strip())
        return True


class ShowBranchCommand(Command):
    """显示分支状态命令"""
    
    def __init__(self):
        super().__init__(
            name="branch-show",
            description="显示当前分支状态",
            usage="branch-show"
        )
    
    def execute(self, args: str, cli) -> bool:
        cli.show_branch_status()
        return True


# 命令别名
BRANCH_COMMANDS = [
    ListBranchesCommand(),
    CreateBranchCommand(),
    SwitchBranchCommand(),
    MergeBranchCommand(),
    ShowBranchCommand(),
]

# 简化别名映射
BRANCH_ALIASES = {
    "ls": "branches",
    "list": "branches",
    "create": "branch-create",
    "switch": "branch-switch",
    "merge": "branch-merge",
    "show": "branch-show",
}