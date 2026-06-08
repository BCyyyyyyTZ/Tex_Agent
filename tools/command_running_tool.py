"""
CommandRunningTool：执行指定的命令行命令并返回执行结果。
"""
import subprocess
import shlex
from typing import Optional

from tools.base_tool import BaseTool
from core.message import ToolResult
from utils.logger import get_logger

logger = get_logger(__name__)


class CommandRunningTool(BaseTool):
    """
    命令行执行工具。

    执行指定的命令行命令，并返回执行结果。

    Example:
        tool = CommandRunningTool()
        result = tool.run("dir")
        print(result.output)
    """

    def __init__(self):
        """初始化命令执行工具，并声明输入 schema（单条 command）。"""
        super().__init__(
            name="command_running",
            description="执行指定的命令行命令并返回执行结果。输入要执行的命令，返回命令的执行输出。",
            input_schema={
                "command": "要执行的命令行命令，例如 'dir' 或 'ls -la'"
            }
        )

    def _execute_command_with_auto_encoding(self, command):
        """执行命令并尝试自动处理控制台输出编码（优先 gbk，失败回退 utf-8）。"""
        try:
            # 1. 关键：不设置 encoding 和 text=True，以二进制模式读取
            # 这样后台读取线程就不会因为编码问题抛出 UnicodeDecodeError
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=False,  # 保持二进制
                timeout=30
            )
            
            try:
                output = result.stdout.decode("gbk")
                err = result.stderr.decode("gbk")

                # 构建输出内容
                content = ""
                if output:
                    content += "标准输出:\n" + output
                if err:
                    content += "\n标准错误:\n" + err

                return content, result

            except UnicodeDecodeError:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',      # 明确指定编码为UTF-8
                    errors='replace',      # 遇到编码错误时使用替换模式
                    timeout=30
                )

                content = ""

                output = result.stdout
                err = result.stderr

                if output:
                    content += "标准输出:\n" + output
                if err:
                    content += "\n标准错误:\n" + err

                return content, result

            
                    
        except Exception as e:
            raise RuntimeError(e)

    def run(self, command: str) -> ToolResult:
        """
        执行命令行命令。

        Args:
            command: 要执行的命令行命令。

        Returns:
            ToolResult，成功时 output 为命令执行结果，
            失败时 success=False 且 error 字段包含错误信息。
        """
        logger.info(f"命令执行启动 | 命令: {command!r}")
        try:
            # 处理命令参数
            if not command:
                raise ValueError("命令不能为空")
            
            # 执行命令
            # 使用shell=True来支持复杂命令，但需要注意安全风险
            # 使用encoding='utf-8'和errors='replace'来处理编码问题
            content, result = self._execute_command_with_auto_encoding(command)
            
            # 检查命令是否执行成功
            if result.returncode == 0:
                logger.info(f"命令执行成功 | 命令: {command!r}")
                return ToolResult(
                    success=True,
                    output=content,
                    metadata={
                        "command": command,
                        "returncode": result.returncode,
                    },
                )
            else:
                logger.warning(f"命令执行失败 | 命令: {command!r} | 返回码: {result.returncode}")
                return ToolResult(
                    success=False,
                    output=content,
                    error=f"命令执行失败，返回码: {result.returncode}",
                    metadata={
                        "command": command,
                        "returncode": result.returncode,
                    },
                )

        except subprocess.TimeoutExpired:
            error_msg = f"命令执行超时（30秒）: {command}"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output="",
                error=error_msg,
                metadata={"command": command},
            )
        except Exception as e:
            error_msg = f"命令执行失败: {e}"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output="",
                error=error_msg,
                metadata={"command": command},
            )

if __name__ == "__main__":
    tool = CommandRunningTool()
    # 测试echo命令
    print("=== 测试echo命令 ===")
    result = tool.run("echo hello world")
    print("命令执行结果:", "成功" if result.success else "失败")
    print("错误信息:", result.error if not result.success else "无")
    if result.success:
        print("返回码:", result.metadata.get("returncode", 0))
        print("\n命令输出:")
        output = result.output[:1000] + ("..." if len(result.output) > 1000 else "")
        print(output)
    
    # 测试type命令
    print("\n=== 测试type命令 ===")
    result = tool.run("type Framework.md")
    print("命令执行结果:", "成功" if result.success else "失败")
    print("错误信息:", result.error if not result.success else "无")
    if result.success:
        print("返回码:", result.metadata.get("returncode", 0))
        print("输出长度:", len(result.output))
        print(result.output)
    
    # 测试dir命令
    print("\n=== 测试dir命令 ===")
    result = tool.run("dir")
    print("命令执行结果:", "成功" if result.success else "失败")
    if result.success:
        print("返回码:", result.metadata.get("returncode", 0))
        print("\n命令输出:")
        output = result.output[:500] + ("..." if len(result.output) > 500 else "")
        print(output)
