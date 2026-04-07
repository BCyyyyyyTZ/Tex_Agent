# ============================================================
# ui/cli/output_formatter.py — CLI 输出格式化器
# ============================================================
# 使用 Rich 库将 Agent 响应、表格数据等以美观方式渲染到终端。
#
# 核心内容:
# - CliFormatter（使用 Rich Console）:
#   - print_agent_response(role, content): 渲染 Agent 消息（带颜色标识）
#   - print_markdown(text): 渲染 Markdown 格式内容
#   - print_paper_table(papers): 以表格形式展示论文搜索结果
#   - print_progress(task, current, total): 进度条渲染
#   - print_branch_tree(tree_data): 渲染分支树形结构
#   - print_error(error_msg): 红色错误提示
#   - print_success(msg): 绿色成功提示
#   - spinner(text): 上下文管理器，展示加载动画
# ============================================================

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Dict, Generator, List


class CliFormatter:
    """
    CLI 输出格式化器（基于 Rich）。
    【需要实现所有方法】使用 rich.console.Console 渲染内容。
    """

    def __init__(self) -> None:
        # 【需要实现】from rich.console import Console; self.console = Console()
        pass

    def print_agent_response(self, role: str, content: str) -> None:
        """渲染 Agent 消息，【需要实现】"""
        pass

    def print_markdown(self, text: str) -> None:
        """渲染 Markdown，【需要实现】"""
        pass

    def print_paper_table(self, papers: List[Dict[str, Any]]) -> None:
        """以表格展示论文，【需要实现】"""
        pass

    def print_branch_tree(self, tree_data: Dict[str, Any]) -> None:
        """渲染分支树，【需要实现】"""
        pass

    @contextmanager
    def spinner(self, text: str) -> Generator:
        """加载动画上下文管理器，【需要实现】"""
        yield
