from __future__ import annotations

import sys

from tools.command_running_tool import CommandRunningTool


def test_command_running_tool__python_print_success() -> None:
    tool = CommandRunningTool()
    cmd = f"\"{sys.executable}\" -c \"print('hello')\""
    r = tool.run(cmd)
    assert r.success is True
    assert "hello" in (r.output or "")

