"""
[扩展] LaTeXParserTool 接口定义。
预留 LaTeX 源文件语法检查、AST 解析与文档结构提取的工具接口。

TODO: 开发者 C 负责实现此类（第二阶段任务）
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any

from tools.base_tool import BaseTool
from core.message import ToolResult


@dataclass
class LaTeXSyntaxIssue:
    """
    LaTeX 语法问题描述。

    Attributes:
        line: 问题所在行号（从 1 开始）。
        column: 问题所在列号（从 1 开始，-1 表示未知）。
        message: 问题描述文本。
        severity: 严重程度，"error"（错误）/ "warning"（警告）/ "info"（提示）。
    """

    line: int
    column: int
    message: str
    severity: str = "error"  # "error" | "warning" | "info"


class LaTeXParserTool(BaseTool):
    """
    [扩展] LaTeX 文档解析工具抽象基类。

    功能规划：
        1. 语法检查：识别常见 LaTeX 语法错误
           （未闭合环境、命令拼写错误、引用缺失等）
        2. AST 解析：将 LaTeX 源码解析为结构化抽象语法树
           （建议接入 pylatexenc 或 plasTeX 等库）
        3. 结构分析：提取章节、公式、图表、参考文献等结构元素

    TODO: 开发者 C 实现建议：
          - 语法检查可先用正则匹配常见错误模式
          - AST 解析推荐使用 pylatexenc 库（pip install pylatexenc）
          - 结构提取可基于 AST 结果进一步处理
    """

    @property
    def name(self) -> str:
        """返回工具唯一标识符（用于路由与注册）。"""
        return "latex_parser"

    @property
    def description(self) -> str:
        """返回工具用途说明（用于向模型/用户展示能力与输入输出）。"""
        return (
            "解析 LaTeX 源文件，进行语法检查和文档结构分析。"
            "可识别语法错误（未闭合环境等）、提取章节层次、分析公式和图表。"
            "输入 LaTeX 源码字符串，返回结构化的解析结果。"
        )

    @abstractmethod
    def check_syntax(self, latex_source: str) -> List[LaTeXSyntaxIssue]:
        """
        检查 LaTeX 源码中的语法问题。

        Args:
            latex_source: 完整的 LaTeX 源码字符串。

        Returns:
            LaTeXSyntaxIssue 列表（为空列表则表示无问题）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def parse_to_ast(self, latex_source: str) -> Dict[str, Any]:
        """
        将 LaTeX 源码解析为抽象语法树（AST）。

        Args:
            latex_source: LaTeX 源码字符串。

        Returns:
            AST 字典表示，结构由具体实现定义。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def extract_structure(self, latex_source: str) -> Dict[str, Any]:
        """
        提取 LaTeX 文档的逻辑结构。

        Args:
            latex_source: LaTeX 源码字符串。

        Returns:
            结构化信息字典，建议包含：
            {
                "sections": [{"title": str, "level": int, "content": str}],
                "equations": [{"label": str, "content": str}],
                "figures": [{"label": str, "caption": str}],
                "citations": [str],  # 引用 key 列表
            }

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def run(self, input: str) -> ToolResult:
        """
        执行 LaTeX 解析（占位实现）。

        TODO: 开发者 C 在此实现完整逻辑，整合 check_syntax / extract_structure，
              返回包含语法问题和文档结构的 ToolResult。
        """
        raise NotImplementedError(
            "LaTeXParserTool.run() 尚未实现。"
            "请参考 check_syntax()/parse_to_ast()/extract_structure() 接口文档进行实现。"
        )
