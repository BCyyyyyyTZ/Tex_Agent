# utils/display.py
"""
输出格式化工具
"""
import sys
from typing import Dict, Any, List
from datetime import datetime


def safe_print(*args, **kwargs) -> None:
    """Windows GBK 控制台无法输出 emoji 时降级为替换字符，避免中断 Plan/Task。"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        end = kwargs.get("end", "\n")
        stream = kwargs.get("file", sys.stdout)
        enc = getattr(stream, "encoding", None) or "utf-8"
        if hasattr(stream, "buffer"):
            stream.buffer.write((text + end).encode(enc, errors="replace"))
            stream.buffer.flush()
        else:
            stream.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + end)


class DisplayFormatter:
    """输出格式化器"""
    
    @staticmethod
    def banner(title: str, subtitle: str = "", width: int = 70) -> str:
        """打印横幅"""
        lines = []
        lines.append("=" * width)
        lines.append(f"  {title}")
        if subtitle:
            lines.append(f"  {subtitle}")
        lines.append("=" * width)
        return "\n".join(lines)
    
    @staticmethod
    def separator(char: str = "─", width: int = 70) -> str:
        """打印分隔线"""
        return char * width
    
    @staticmethod
    def section(title: str, width: int = 70) -> str:
        """打印章节标题"""
        return f"\n{DisplayFormatter.separator(width)}\n{title}\n{DisplayFormatter.separator(width)}"
    
    @staticmethod
    def truncate(text: str, max_length: int = 1000, suffix: str = "...") -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + suffix
    
    @staticmethod
    def format_memory_item(item: Any, max_length: int = 50) -> str:
        """格式化记忆项"""
        if isinstance(item, dict):
            key = item.get('key', 'unknown')
            value = str(item.get('value', ''))[:max_length]
            return f"  [{key}] {value}"
        return f"  {str(item)[:max_length]}"
    
    @staticmethod
    def print_result(result: Dict[str, Any]):
        """打印工作流结果"""
        print("\n" + "=" * 65)
        print("  工作流执行完毕")
        print("=" * 65)
        
        if result.get("error"):
            print(f"\n⚠️  错误: {result['error']}")
        
        output = result.get("output", "")
        if output:
            print(f"\n📄 输出:\n{output}")
        else:
            print("\n（未生成输出）")
        
        msg_count = len(result.get("messages", []))
        print(f"\n{'─' * 65}")
        print(f"  消息历史：{msg_count} 条 | 执行节点：{result.get('current_node', '未知')}")
        print("=" * 65 + "\n")


display = DisplayFormatter()