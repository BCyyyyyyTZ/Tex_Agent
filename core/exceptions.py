"""
TeX_Agent 自定义异常体系。
所有模块异常均继承自 TexAgentError，便于统一捕获与处理。
"""
from typing import Optional


class TexAgentError(Exception):
    """TeX_Agent 系统基础异常，所有自定义异常的根类。"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}


class AgentError(TexAgentError):
    """Agent 推理或执行过程中的异常。"""


class ToolError(TexAgentError):
    """工具调用或执行过程中的异常。"""


class WorkflowError(TexAgentError):
    """工作流编排、构建或执行异常。"""


class MemoryError(TexAgentError):
    """记忆/上下文模块异常。"""


class RouterError(TexAgentError):
    """路由模块异常（无合适 Agent 或路由策略失败）。"""


class SecurityError(TexAgentError):
    """安全权限模块异常（认证失败、权限不足等）。"""


class ConfigError(TexAgentError):
    """配置错误（必填字段缺失、格式非法等）。"""
