# ============================================================
# plugins/plugin_base.py — 插件抽象基类与生命周期管理
# ============================================================
# 定义 NeuroTeX 插件系统的基础架构，允许第三方扩展系统功能。
# 插件可以为编辑器（LaTeX/VSCode）、文档格式、新 Agent 类型等
# 提供标准化的扩展接口。
#
# 核心内容:
# - PluginType: 枚举（EDITOR/AGENT/TOOL/KNOWLEDGE_SOURCE/EXPORTER）
# - PluginManifest: 插件元数据（name/version/type/description/entry_point/
#   dependencies/compatible_neurotex_version）
# - BasePlugin（ABC）: 插件抽象基类
#   - on_load(): 插件加载时回调（初始化资源）
#   - on_unload(): 插件卸载时回调（释放资源）
#   - on_event(event): 系统事件处理（可选覆写）
#   - get_manifest() -> PluginManifest: 返回插件元数据
# - PluginManager: 插件管理器
#   - discover(plugin_dir): 扫描并注册本地插件
#   - load(plugin_name): 动态加载插件
#   - unload(plugin_name): 卸载插件
#   - list_loaded(): 返回已加载的插件列表
# ============================================================

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PluginType(str, Enum):
    EDITOR = "editor"
    AGENT = "agent"
    TOOL = "tool"
    KNOWLEDGE_SOURCE = "knowledge_source"
    EXPORTER = "exporter"


@dataclass
class PluginManifest:
    name: str = ""
    version: str = "1.0.0"
    plugin_type: PluginType = PluginType.TOOL
    description: str = ""
    author: str = ""
    entry_point: str = ""                           # 插件主类路径
    dependencies: List[str] = field(default_factory=list)
    compatible_neurotex_version: str = ">=1.0.0"


class BasePlugin(ABC):
    """
    插件抽象基类。
    所有 NeuroTeX 插件必须继承此类并实现 get_manifest()。
    """

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """返回插件元数据，【子类必须实现】"""
        pass

    async def on_load(self) -> None:
        """插件加载回调，【子类按需覆写】"""
        pass

    async def on_unload(self) -> None:
        """插件卸载回调，【子类按需覆写】"""
        pass

    async def on_event(self, event: Any) -> None:
        """系统事件处理，【子类按需覆写】"""
        pass


class PluginManager:
    """
    插件管理器。
    【需要实现】
    - discover(plugin_dir): 扫描目录，找到所有合法插件
    - load(name): importlib 动态导入，调用 on_load()
    - unload(name): 调用 on_unload()，从注册表移除
    - list_loaded(): 返回当前已加载的插件信息
    """

    def __init__(self) -> None:
        self._loaded: Dict[str, BasePlugin] = {}

    def discover(self, plugin_dir: str) -> List[PluginManifest]:
        """扫描插件目录，【需要实现】"""
        pass

    async def load(self, plugin_name: str) -> None:
        """动态加载插件，【需要实现】"""
        pass

    async def unload(self, plugin_name: str) -> None:
        """卸载插件，【需要实现】"""
        pass

    def list_loaded(self) -> List[PluginManifest]:
        """返回已加载插件列表，【需要实现】"""
        return [p.get_manifest() for p in self._loaded.values()]
