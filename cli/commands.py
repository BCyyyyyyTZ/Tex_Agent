# cli/commands.py - 修复命令匹配
"""
命令基类和注册表
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, List, Tuple


class Command(ABC):
    """命令基类"""
    
    def __init__(self, name: str, description: str, usage: str = "", aliases: List[str] = None):
        self.name = name
        self.description = description
        self.usage = usage or name
        self.aliases = aliases or []
    
    @abstractmethod
    def execute(self, args: str, context: Any) -> bool:
        """执行命令，返回是否继续运行"""
        pass
    
    def matches(self, input_name: str) -> bool:
        """检查命令名是否匹配"""
        return input_name == self.name or input_name in self.aliases
    
    def help(self) -> str:
        """返回帮助信息"""
        alias_str = f" (别名: {', '.join(self.aliases)})" if self.aliases else ""
        return f"  {self.name:<15} - {self.description}{alias_str}"


class CommandRegistry:
    """命令注册表"""
    
    def __init__(self):
        self._commands: Dict[str, Command] = {}
    
    def register(self, command: Command):
        """注册命令"""
        self._commands[command.name] = command
    
    def find_command(self, input_name: str) -> Command:
        """查找匹配的命令"""
        for cmd in self._commands.values():
            if cmd.matches(input_name):
                return cmd
        return None
    
    def execute(self, input_line: str, context: Any) -> bool:
        """执行命令"""
        if not input_line.strip():
            return True
        
        parts = input_line.strip().split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 查找匹配的命令
        cmd = self.find_command(cmd_name)
        
        if cmd:
            return cmd.execute(args, context)
        
        # 不是命令，返回 None 表示需要作为任务处理
        return None
    
    def list_commands(self) -> List[str]:
        """列出所有命令"""
        return list(self._commands.keys())
    
    def show_help(self) -> str:
        """显示帮助信息"""
        lines = ["\n📋 可用命令:"]
        for cmd in self._commands.values():
            lines.append(cmd.help())
        lines.append("\n💡 直接输入文本即可执行任务")
        return "\n".join(lines)