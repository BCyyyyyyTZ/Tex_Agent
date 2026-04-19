"""
PersonaMemoryTool：用户画像更新/读取工具。

用于将用户画像维护逻辑下沉到 tools 层，避免 workflow 节点直接操作
UserPersonaMemory 的内部更新方法。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from core.message import ToolResult
from tools.base_tool import BaseTool
from utils.logger import get_logger

if False:  # pragma: no cover
    from memory.persona_memory import UserPersonaMemory

logger = get_logger(__name__)


class PersonaMemoryTool(BaseTool):
    """
    用户画像工具：
    - action=apply_update：应用入口节点产出的 persona_memory_update
    - action=get_profile：读取当前画像（JSON 字符串）
    """

    def __init__(self, persona_memory: Optional["UserPersonaMemory"] = None) -> None:
        super().__init__(
            name="persona_memory",
            description="维护长期用户画像（更新与读取）",
            input_schema={
                "action": "必填，支持 apply_update/get_profile",
                "update": "可选，action=apply_update 时传入 persona_memory_update 对象",
                "source_node": "可选，调用来源节点标识",
                "allow_non_entry": "可选，是否允许非入口节点更新画像，默认 false",
            },
        )
        self._persona_memory = persona_memory

    def run(
        self,
        action: str,
        update: Any = None,
        source_node: str = "",
        allow_non_entry: bool = False,
    ) -> ToolResult:
        if self._persona_memory is None:
            return ToolResult(
                success=False,
                output="",
                error="persona_memory 未配置，无法执行画像工具",
                metadata={"action": action},
            )

        action_norm = str(action or "").strip().lower()
        if action_norm == "get_profile":
            profile = self._persona_memory.get_profile()
            return ToolResult(
                success=True,
                output=json.dumps(profile, ensure_ascii=False, indent=2),
                metadata={"action": "get_profile"},
            )

        if action_norm != "apply_update":
            return ToolResult(
                success=False,
                output="",
                error=f"不支持的 action: {action!r}",
                metadata={"action": action},
            )

        if not allow_non_entry and source_node and source_node != "__entry__":
            logger.debug(f"[PersonaMemoryTool] 忽略非入口节点画像更新: node={source_node}")
            return ToolResult(
                success=True,
                output="ignored_non_entry_update",
                metadata={"action": "apply_update", "ignored": True, "source_node": source_node},
            )

        try:
            self._persona_memory.apply_persona_memory_update(update)
            return ToolResult(
                success=True,
                output="persona_memory_updated",
                metadata={"action": "apply_update", "source_node": source_node or "__entry__"},
            )
        except Exception as e:
            logger.warning(f"[PersonaMemoryTool] 更新失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                metadata={"action": "apply_update", "source_node": source_node},
            )
