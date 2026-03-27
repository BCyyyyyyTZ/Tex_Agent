# ============================================================
# plugins/latex_plugin/plugin_core.py — LaTeX 编辑器插件核心
# ============================================================
# 将 NeuroTeX 的 AI 能力集成到 LaTeX 编辑器中（如 VSCode/Overleaf）。
# 遵循 LSP（Language Server Protocol）扩展协议，以标准方式
# 提供代码补全、错误诊断、快速修复、悬停提示等功能。
#
# 核心功能:
# - 实时错误检测：监听文档变更，调用 LaTeXValidator 实时诊断
# - AI 补全：在光标位置触发 AI 续写建议（调用 WritingAgent）
# - 快速修复：错误定位后提供一键 AI 修复操作（LaTeXAgent）
# - 悬停提示：对 \cite{} \ref{} 等命令悬停时显示内容预览
# - 文献插入：输入关键词后 AI 搜索并插入 BibTeX
# - 侧边栏：显示当前文档结构树、分支列表、Agent 建议面板
#
# 通信方式:
# - 编辑器插件（JS/TS）通过 WebSocket 连接 NeuroTeX API Server
# - 本文件实现服务端的 WebSocket 处理逻辑
#
# 核心类 LaTeXPluginCore:
# - handle_document_change(uri, content, version): 处理文档变更
# - get_completions(uri, position, context) -> list: 获取补全建议
# - get_diagnostics(uri, content) -> list: 获取诊断信息（LSP格式）
# - get_code_actions(uri, range, diagnostics) -> list: 获取快速修复
# - get_hover(uri, position) -> dict: 获取悬停信息
# - handle_command(command, args) -> Any: 处理编辑器自定义命令
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from plugins.plugin_base import BasePlugin, PluginManifest, PluginType


@dataclass
class LSPPosition:
    """LSP 协议位置表示"""
    line: int = 0
    character: int = 0


@dataclass
class LSPDiagnostic:
    """LSP 协议诊断信息"""
    range_start: LSPPosition = field(default_factory=LSPPosition)
    range_end: LSPPosition = field(default_factory=LSPPosition)
    severity: int = 1            # 1=Error, 2=Warning, 3=Info, 4=Hint
    message: str = ""
    code: str = ""
    source: str = "NeuroTeX"
    data: Dict[str, Any] = field(default_factory=dict)


class LaTeXPluginCore(BasePlugin):
    """
    LaTeX 编辑器插件服务端核心。
    通过 WebSocket 与编辑器插件（JS端）通信，提供 AI 增强能力。
    【需要实现所有方法】
    """

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="neurotex-latex-plugin",
            version="1.0.0",
            plugin_type=PluginType.EDITOR,
            description="将 NeuroTeX AI 能力集成到 LaTeX 编辑器",
            author="NeuroTeX Team",
        )

    async def handle_document_change(
        self, uri: str, content: str, version: int
    ) -> None:
        """处理文档变更事件（防抖后触发诊断），【需要实现】"""
        pass

    async def get_completions(
        self, uri: str, position: LSPPosition, context: Dict[str, Any] = {}
    ) -> List[Dict[str, Any]]:
        """
        获取 AI 补全建议。
        【需要实现】
        - 分析光标前的内容判断补全类型
        - \cite{ → 文献补全（调用 PaperKnowledgeBase）
        - \ref{ → 标签补全（解析当前文档 \label）
        - 段落末尾 → AI 续写建议（调用 WritingAgent）
        """
        pass

    async def get_diagnostics(
        self, uri: str, content: str
    ) -> List[LSPDiagnostic]:
        """
        获取诊断信息（LSP 格式）。
        【需要实现】调用 LaTeXValidator，转换为 LSP Diagnostic 格式。
        """
        pass

    async def get_code_actions(
        self,
        uri: str,
        diagnostics: List[LSPDiagnostic],
    ) -> List[Dict[str, Any]]:
        """获取快速修复动作，【需要实现】"""
        pass

    async def get_hover(
        self, uri: str, position: LSPPosition
    ) -> Optional[Dict[str, Any]]:
        """获取悬停信息，【需要实现】"""
        pass

    async def handle_command(
        self, command: str, args: List[Any]
    ) -> Any:
        """
        处理编辑器自定义命令。
        【需要实现】支持的命令：
        - neurotex.fixAll: 修复全部错误
        - neurotex.searchPaper: 搜索并插入文献
        - neurotex.writeSection: AI 撰写选中章节
        - neurotex.createBranch: 创建对话分支
        """
        pass
