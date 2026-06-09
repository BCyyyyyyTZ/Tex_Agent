"""
tools.command_running_tool 的单元测试。

覆盖点：
1) run() 能执行一条安全命令并返回标准输出；
2) run() 对 returncode 0/非 0 的 ToolResult.success 与 error 字段行为；
3) run() 对空命令进行输入校验。

设计原则：
- 只执行“无副作用”的命令（基于当前 Python 解释器打印固定文本），避免环境差异与破坏性行为。
"""

from __future__ import annotations

import sys
from tools.command_running_tool import CommandRunningTool


def test_run_success_and_failure() -> None:
    """
    run() 根据 returncode 决定 ToolResult.success，并在失败时设置 error 字段。
    """
    tool = CommandRunningTool()

    # 成功用例：使用当前 Python 打印固定文本（跨平台且无副作用）
    r1 = tool.run(f"\"{sys.executable}\" -c \"print('OK_FROM_TEST')\"")
    assert r1.success is True
    assert "OK_FROM_TEST" in r1.output
    assert r1.error == "" or r1.error is None
    assert r1.metadata["returncode"] == 0

    # 失败用例：执行一个必然失败的命令（不依赖外部程序）
    r2 = tool.run("this_command_should_not_exist_123456")
    assert r2.success is False
    assert "返回码" in (r2.error or "")
    assert int(r2.metadata.get("returncode") or 0) != 0


def test_run_rejects_empty_command() -> None:
    """
    空命令属于输入校验错误：应返回 success=False。
    """
    tool = CommandRunningTool()
    r = tool.run("")
    assert r.success is False
    assert "命令不能为空" in (r.error or "")
