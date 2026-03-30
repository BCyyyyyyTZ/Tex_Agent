# plugins/__init__.py — 插件系统入口
from plugins.plugin_base import BasePlugin, PluginManager, PluginManifest, PluginType
from plugins.latex_plugin.plugin_core import LaTeXPluginCore

__all__ = ["BasePlugin", "PluginManager", "PluginManifest", "PluginType", "LaTeXPluginCore"]
