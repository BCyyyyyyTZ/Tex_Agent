"""
agents.base_agent 的单元测试（只测试“本地可确定”的部分）。

范围：
- AgentMemory：add/get/clear 的基础行为；
- BaseAgent.set_tool_args：嵌套参数写入；
- BaseAgent.call_tool：工具查找、参数合并（调用时合并默认 tool_args）。

说明：
- 不触发真实 LLM 调用（OpenAI/Gemini），避免外部依赖与网络；
- 通过最小可用实现验证框架层逻辑（工具调用路由、参数合并、内存结构）。
"""

from __future__ import annotations

import pytest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from core.message import ToolResult, WorkflowMessage
from tools.base_tool import BaseTool


def _load_base_agent_module():
    """
    通过文件路径加载 agents/base_agent.py，避免导入 agents 包触发其 __init__ 里的额外依赖。
    """
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "agents" / "base_agent.py"
    spec = spec_from_file_location("_tex_agent_agents_base_agent", str(path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_base_agent = _load_base_agent_module()
AgentMemory = _base_agent.AgentMemory
AgentMemoryItem = _base_agent.AgentMemoryItem
BaseAgent = _base_agent.BaseAgent


class _MinimalTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(name="t1", description="t1", input_schema={"x": "int", "y": "int"})
        self.last_args = None

    def run(self, x: int, y: int = 0) -> ToolResult:
        self.last_args = {"x": x, "y": y}
        return ToolResult(success=True, output=str(x + y), error="", metadata=self.last_args)


class _MinimalAgent(BaseAgent):
    """
    只为满足抽象类接口的最小实现。
    """

    def run(self, message) -> WorkflowMessage:
        return WorkflowMessage(role="assistant", source_type="agent", source_id=self.name, content="ok")

    def reset(self) -> None:
        self.memory.clear()


def test_agent_memory_add_get_clear() -> None:
    mem = AgentMemory()
    mem.add(AgentMemoryItem(data={"a": 1}, data_type="x"))
    mem.add(AgentMemoryItem(data={"b": 2}, data_type="y"))
    xs = mem.get("x")
    assert len(xs) == 1
    assert xs[0].data["a"] == 1
    mem.clear()
    assert mem.get("x") == []


def test_base_agent_set_tool_args_and_call_tool_merges_args() -> None:
    """
    set_tool_args 会写入 agent.tool_args：
    - call_tool 调用时会把入参 tool_args 与 agent 默认 tool_args 合并；
    - 若调用时显式传入同名参数，应以调用时参数优先（当前实现是 update 后写入默认值，默认值会覆盖）。

    说明：
    这里锁定当前实现行为：tool_args.update(self.tool_args.get(tool_name, {}))。
    即：默认参数会覆盖调用时同名字段。
    若未来要调整为“调用参数优先”，需要同时更新生产代码与此测试。
    """
    tool = _MinimalTool()
    agent = _MinimalAgent(name="a", system_prompt="s", tools=[tool])

    agent.set_tool_args({"t1": {"y": 100}})

    r = agent.call_tool("t1", {"x": 1, "y": 2})
    assert r.success is True
    # 根据当前实现：默认 y=100 覆盖调用时 y=2
    assert tool.last_args == {"x": 1, "y": 100}
    assert r.output == "101"


def test_base_agent_call_tool_rejects_unknown_tool() -> None:
    agent = _MinimalAgent(name="a", system_prompt="s", tools=[])
    with pytest.raises(ValueError, match="未注册"):
        agent.call_tool("missing", {})
