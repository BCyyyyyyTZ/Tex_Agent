# ============================================================
# skills/skill_registry.py — 技能注册表
# ============================================================
# 管理系统中所有可复用技能的注册、查找与版本控制。
# 技能(Skill)是比 Tool 更高层的可复用任务单元，
# 封装了"完成某类子任务"所需的提示词模板 + 工具组合 + 后处理逻辑。
#
# 核心概念:
# - SkillMeta: 技能元数据（名称/描述/版本/所需工具/适用 Agent 类型）
# - SkillRegistry: 全局技能注册表，支持按名称/标签/类别检索
# - @register_skill 装饰器: 自动注册技能类到全局注册表
# - get_skill(name, version): 获取指定版本的技能实例
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


@dataclass
class SkillMeta:
    """技能元数据"""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = "general"         # academic / technical / analytical / general
    required_tools: List[str] = field(default_factory=list)
    compatible_agents: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    author: str = "NeuroTeX"


class SkillRegistry:
    """
    全局技能注册表。
    支持注册、版本管理和多维度检索。
    【需要实现】
    - register(skill_class, meta): 注册技能
    - get(name, version=None): 获取技能
    - list_by_category(category): 按类别列出
    - find(tags=[], agent_type=""): 多条件搜索
    """
    _instance: Optional["SkillRegistry"] = None

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills: Dict[str, Dict[str, Any]] = {}
        return cls._instance

    def register(self, skill_class: Type, meta: SkillMeta) -> None:
        """注册技能，【需要实现】"""
        pass

    def get(self, name: str, version: Optional[str] = None) -> Any:
        """获取技能实例，【需要实现】"""
        pass

    def list_by_category(self, category: str) -> List[SkillMeta]:
        """按类别列出技能，【需要实现】"""
        pass

    def find(
        self, tags: List[str] = [], agent_type: str = ""
    ) -> List[SkillMeta]:
        """多条件检索技能，【需要实现】"""
        pass


def register_skill(meta: SkillMeta):
    """技能注册装饰器，【需要实现】"""
    def decorator(cls):
        return cls
    return decorator


def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
