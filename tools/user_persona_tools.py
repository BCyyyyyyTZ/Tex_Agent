"""
入口节点专用：用户画像写库工具族。

将 merge / set / clear / none 拆成独立工具，语义写在各工具的 description 与 input_schema，
工作流 prompt 仅保留「须调用其一」的短契约，避免把整段 action 说明硬编码进 system prompt。
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

if TYPE_CHECKING:
    from memory.persona_memory import UserPersonaMemory

logger = get_logger(__name__)

PERSONA_MAINTENANCE_TOOL_NAMES: FrozenSet[str] = frozenset(
    {
        "user_persona_none",
        "user_persona_merge",
        "user_persona_set",
        "user_persona_clear",
    }
)


def entry_node_persona_system_addon() -> str:
    """供入口节点追加到 system 的短契约（具体 action 语义见各工具描述）。"""
    names = "、".join(sorted(PERSONA_MAINTENANCE_TOOL_NAMES))
    return f"""
---
[入口节点 · 用户画像维护]
你必须在本轮内调用一次下列工具之一完成用户画像写库：{names}。
各工具的行为、字段含义与参数格式以工具列表中的 tool_description 与 tool_input_schema 为准。
最终 JSON 顶层仅允许 result、summary、confidence、metadata 四个键，禁止输出 persona_memory_update。
---
"""


def entry_node_persona_simple_agent_addon() -> str:
    """SimpleAgent 入口：因无法执行工具，通过 JSON 顶层 persona_memory_update 写画像。"""
    return """
---
[入口节点 · 用户画像 JSON 写回 | 必须严格遵守]
当前为 SimpleAgent（本轮不能调用工具），你必须在输出 JSON 的顶层增加第 5 个键（与 result 等并列）：

  "persona_memory_update": {
    "action": "none" | "merge" | "set" | "clear",
    "delta": { },
    "fields": { },
    "clear_keys": [ ],
    "remove": { }
  }

规则摘要：
- none：无把握或无可保存信息时；其它子键可省略。
- merge：在 delta 中合并。内置字符串字段仅非空覆盖；列表去重追加；extra 为键合并。
  学校、院系、年级等可写入 "extra": { "school": "...", "department": "..." }；也可用任意新顶层键扩展（如 "affiliation": "某大学"）。
- set：整字段覆盖；clear：clear_keys 恢复默认或删除扩展顶层键。
若用户在 [原始任务] 中给出姓名、学校等稳定信息且你确信无误，应使用 merge 写入，勿编造未出现的内容。
---
"""


class UserPersonaGetTool(BaseTool):
    """可选：读取当前画像 JSON（入口与其它节点均可挂载；默认仅入口构图会带全套画像工具时可一并带上）。"""

    def __init__(self, persona_memory: "UserPersonaMemory") -> None:
        super().__init__(
            name="user_persona_get",
            description="读取当前持久化用户画像（JSON）。不改变磁盘内容。",
            input_schema={},
        )
        self._pm = persona_memory

    def run(self, **_kwargs: Any) -> ToolResult:
        blob = self._pm.get_profile()
        return ToolResult(
            success=True,
            output=json.dumps(blob, ensure_ascii=False, indent=2),
            metadata={"tool": self.name},
        )


class UserPersonaNoneTool(BaseTool):
    def __init__(self, persona_memory: "UserPersonaMemory") -> None:
        super().__init__(
            name="user_persona_none",
            description=(
                "用户画像写库：action=none。不修改画像文件；无额外参数。"
                "当本轮对话未带来任何可确认的画像变更时使用。"
            ),
            input_schema={},
        )
        self._pm = persona_memory

    def run(self, **_kwargs: Any) -> ToolResult:
        self._pm.apply_persona_memory_update({"action": "none"})
        return ToolResult(
            success=True,
            output="user_persona_none_ok",
            metadata={"tool": self.name},
        )


class UserPersonaMergeTool(BaseTool):
    def __init__(self, persona_memory: "UserPersonaMemory") -> None:
        super().__init__(
            name="user_persona_merge",
            description=(
                "用户画像写库：action=merge（追加式）。"
                "delta：列表字段去重追加；字符串字段仅当新值非空时覆盖；extra 为键合并。"
                "delta 还可含任意顶层扩展键（不在内置 schema 内）：新键整段写入；若该键已存在且新旧值均为对象，则对象顶层键浅合并（便于在扩展结构里继续加 key）。"
                "remove（可选）：从列表字段删除条目，键为 research_areas/preferences，"
                "值为字符串数组，删除时与画像项去空白后完全一致才生效。"
            ),
            input_schema={
                "delta": "必填，对象；无增量可传 {}。",
                "remove": "可选，对象；从 preferences / research_areas 等列表字段按精确项删除。",
            },
        )
        self._pm = persona_memory

    def run(self, delta: Optional[Dict[str, Any]] = None, remove: Optional[Dict[str, Any]] = None, **_kwargs: Any) -> ToolResult:
        upd: Dict[str, Any] = {"action": "merge", "delta": delta if isinstance(delta, dict) else {}}
        if isinstance(remove, dict) and remove:
            upd["remove"] = remove
        self._pm.apply_persona_memory_update(upd)
        return ToolResult(
            success=True,
            output="user_persona_merge_ok",
            metadata={"tool": self.name},
        )


class UserPersonaSetTool(BaseTool):
    def __init__(self, persona_memory: "UserPersonaMemory") -> None:
        super().__init__(
            name="user_persona_set",
            description=(
                "用户画像写库：action=set（整字段覆盖）。"
                "必须提供 fields：字符串类字段可用空串清空；列表类整表替换（可 []）；"
                "extra 传入对象则整体替换，传 JSON null 则 extra 变为 {}。"
                "fields 中亦可含任意顶层扩展键：整值写入（与内置字段一样按 key 覆盖）。"
            ),
            input_schema={
                "fields": "必填，对象；顶层键须为画像合法字段的子集。",
            },
        )
        self._pm = persona_memory

    def run(self, fields: Optional[Dict[str, Any]] = None, **_kwargs: Any) -> ToolResult:
        if not isinstance(fields, dict):
            return ToolResult(
                success=False,
                output="",
                error="user_persona_set 需要 fields 对象",
                metadata={"tool": self.name},
            )
        self._pm.apply_persona_memory_update({"action": "set", "fields": fields})
        return ToolResult(
            success=True,
            output="user_persona_set_ok",
            metadata={"tool": self.name},
        )


class UserPersonaClearTool(BaseTool):
    def __init__(self, persona_memory: "UserPersonaMemory") -> None:
        super().__init__(
            name="user_persona_clear",
            description=(
                "用户画像写库：action=clear。"
                "clear_keys：字符串数组；内置字段恢复为系统默认空值，扩展顶层键则从 JSON 中删除该键。"
            ),
            input_schema={
                "clear_keys": "必填，字符串数组，如 [\"writing_preferences\", \"preferences\"]",
            },
        )
        self._pm = persona_memory

    def run(self, clear_keys: Optional[List[Any]] = None, **_kwargs: Any) -> ToolResult:
        if not isinstance(clear_keys, list):
            return ToolResult(
                success=False,
                output="",
                error="user_persona_clear 需要 clear_keys 数组",
                metadata={"tool": self.name},
            )
        self._pm.apply_persona_memory_update({"action": "clear", "clear_keys": clear_keys})
        return ToolResult(
            success=True,
            output="user_persona_clear_ok",
            metadata={"tool": self.name},
        )


def build_user_persona_tools(persona_memory: "UserPersonaMemory") -> List[BaseTool]:
    """供 tool_list 注册；顺序不影响功能。"""
    return [
        UserPersonaGetTool(persona_memory),
        UserPersonaNoneTool(persona_memory),
        UserPersonaMergeTool(persona_memory),
        UserPersonaSetTool(persona_memory),
        UserPersonaClearTool(persona_memory),
    ]
