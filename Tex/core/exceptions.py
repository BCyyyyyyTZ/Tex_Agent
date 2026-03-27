# ============================================================
# core/exceptions.py
# NeuroTeX 统一异常体系
# ============================================================
# 本文件定义整个 NeuroTeX 系统的异常层级，确保错误可被
# 精准捕获和处理，提供清晰的错误信息和调试上下文。
#
# 【异常设计原则】
# 1. 所有自定义异常继承自 NeuroTeXError
# 2. 每个异常携带结构化信息（错误码、上下文、建议）
# 3. 区分用户错误（可恢复）和系统错误（不可恢复）
# 4. 支持异常链（cause），保留原始错误信息
#
# 【需要实现的内容】
#
# 1. ErrorCode — 枚举，系统错误码
#    格式: NT_{模块}_{编号}
#    - NT_SYS_001: 系统初始化失败
#    - NT_SYS_002: 配置加载失败
#    - NT_AGT_001: Agent 执行失败
#    - NT_AGT_002: Agent 超时
#    - NT_AGT_003: Agent 未找到
#    - NT_AGT_004: Agent 工具调用失败
#    - NT_MEM_001: 记忆存储失败
#    - NT_MEM_002: 记忆检索失败
#    - NT_MEM_003: 分支操作失败
#    - NT_RAG_001: 文档索引失败
#    - NT_RAG_002: 检索失败
#    - NT_RAG_003: 知识库不存在
#    - NT_ROU_001: 路由决策失败
#    - NT_ROU_002: 无可用 Agent
#    - NT_TOL_001: 工具执行错误
#    - NT_TOL_002: 工具超时
#    - NT_TOL_003: LaTeX 解析错误
#    - NT_TOL_004: 文献检索失败
#    - NT_SEC_001: 认证失败
#    - NT_SEC_002: 权限不足
#    - NT_USR_001: 无效输入
#    - NT_USR_002: 资源超出限制
#
# 2. NeuroTeXError — 基础异常类
#    属性:
#    - error_code: ErrorCode
#    - message: str
#    - context: dict             # 错误发生时的上下文信息
#    - suggestion: str           # 给用户的修复建议
#    - is_recoverable: bool      # 是否可恢复
#    方法:
#    - to_dict(): 序列化为字典（用于 API 错误响应）
#    - __str__(): 格式化错误信息
#
# 3. 各模块专用异常类（继承 NeuroTeXError）
#
#    AgentError(NeuroTeXError)   — Agent 执行相关错误
#    AgentNotFoundError(AgentError)
#    AgentTimeoutError(AgentError)
#    AgentToolCallError(AgentError)
#    MaxIterationsExceededError(AgentError)
#
#    MemoryError(NeuroTeXError)  — 记忆系统错误
#    MemoryStorageError(MemoryError)
#    BranchNotFoundError(MemoryError)
#    BranchMergeConflictError(MemoryError)
#
#    RAGError(NeuroTeXError)     — RAG 检索错误
#    KnowledgeBaseNotFoundError(RAGError)
#    IndexingError(RAGError)
#    RetrievalError(RAGError)
#
#    RouterError(NeuroTeXError)  — 路由错误
#    NoAvailableAgentError(RouterError)
#    RoutingDecisionError(RouterError)
#
#    ToolError(NeuroTeXError)    — 工具执行错误
#    LaTeXParsingError(ToolError)
#    LiteratureSearchError(ToolError)
#    VisualizationError(ToolError)
#    ImageGenerationError(ToolError)
#
#    SecurityError(NeuroTeXError) — 安全错误
#    AuthenticationError(SecurityError)
#    PermissionDeniedError(SecurityError)
#
#    ConfigError(NeuroTeXError)  — 配置错误
#    MissingAPIKeyError(ConfigError)
#    InvalidConfigError(ConfigError)
#
#    UserInputError(NeuroTeXError) — 用户输入错误（可恢复）
#    InvalidInputError(UserInputError)
#    ResourceLimitExceededError(UserInputError)
#
# 4. 异常处理辅助函数
#    handle_exception(exc) -> dict:
#    - 将任意异常转换为统一的错误字典格式
#    - 对已知异常直接调用 to_dict()
#    - 对未知异常封装为 NeuroTeXError 后转换
#
#    is_recoverable(exc) -> bool:
#    - 判断异常是否可恢复（用于决定是否重试）
# ============================================================

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """系统错误码枚举，【实现见上方注释】"""
    NT_SYS_001 = "NT_SYS_001"
    NT_SYS_002 = "NT_SYS_002"
    NT_AGT_001 = "NT_AGT_001"
    NT_AGT_002 = "NT_AGT_002"
    NT_AGT_003 = "NT_AGT_003"
    NT_AGT_004 = "NT_AGT_004"
    NT_MEM_001 = "NT_MEM_001"
    NT_MEM_002 = "NT_MEM_002"
    NT_MEM_003 = "NT_MEM_003"
    NT_RAG_001 = "NT_RAG_001"
    NT_RAG_002 = "NT_RAG_002"
    NT_RAG_003 = "NT_RAG_003"
    NT_ROU_001 = "NT_ROU_001"
    NT_ROU_002 = "NT_ROU_002"
    NT_TOL_001 = "NT_TOL_001"
    NT_TOL_002 = "NT_TOL_002"
    NT_TOL_003 = "NT_TOL_003"
    NT_TOL_004 = "NT_TOL_004"
    NT_SEC_001 = "NT_SEC_001"
    NT_SEC_002 = "NT_SEC_002"
    NT_USR_001 = "NT_USR_001"
    NT_USR_002 = "NT_USR_002"


class NeuroTeXError(Exception):
    """NeuroTeX 基础异常类，【实现字段和方法见上方注释】"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.NT_SYS_001,
        context: Optional[Dict[str, Any]] = None,
        suggestion: str = "",
        is_recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = context or {}
        self.suggestion = suggestion
        self.is_recoverable = is_recoverable

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，【需要实现】"""
        pass

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


# ---- Agent 相关异常 ----

class AgentError(NeuroTeXError):
    """Agent 执行错误基类"""
    pass

class AgentNotFoundError(AgentError):
    """指定 Agent 不存在"""
    pass

class AgentTimeoutError(AgentError):
    """Agent 任务执行超时"""
    pass

class AgentToolCallError(AgentError):
    """Agent 调用工具时出错"""
    pass

class MaxIterationsExceededError(AgentError):
    """超过最大推理迭代次数"""
    pass


# ---- 记忆系统异常 ----

class MemoryError(NeuroTeXError):  # type: ignore[no-redef]
    """记忆系统错误基类"""
    pass

class MemoryStorageError(MemoryError):
    """记忆存储失败"""
    pass

class BranchNotFoundError(MemoryError):
    """上下文分支不存在"""
    pass

class BranchMergeConflictError(MemoryError):
    """分支合并冲突"""
    pass


# ---- RAG 检索异常 ----

class RAGError(NeuroTeXError):  # type: ignore[no-redef]
    """RAG 系统错误基类"""
    pass

class KnowledgeBaseNotFoundError(RAGError):
    """知识库不存在"""
    pass

class IndexingError(RAGError):
    """文档索引失败"""
    pass

class RetrievalError(RAGError):
    """检索失败"""
    pass


# ---- 路由异常 ----

class RouterError(NeuroTeXError):  # type: ignore[no-redef]
    """路由错误基类"""
    pass

class NoAvailableAgentError(RouterError):
    """没有可用的 Agent"""
    pass

class RoutingDecisionError(RouterError):
    """路由决策失败"""
    pass


# ---- 工具异常 ----

class ToolError(NeuroTeXError):  # type: ignore[no-redef]
    """工具执行错误基类"""
    pass

class LaTeXParsingError(ToolError):
    """LaTeX 解析错误"""
    pass

class LiteratureSearchError(ToolError):
    """文献检索失败"""
    pass

class VisualizationError(ToolError):
    """可视化生成失败"""
    pass

class ImageGenerationError(ToolError):
    """图像生成失败"""
    pass


# ---- 安全异常 ----

class SecurityError(NeuroTeXError):  # type: ignore[no-redef]
    """安全错误基类"""
    pass

class AuthenticationError(SecurityError):
    """认证失败"""
    pass

class PermissionDeniedError(SecurityError):
    """权限不足"""
    pass


# ---- 配置异常 ----

class ConfigError(NeuroTeXError):  # type: ignore[no-redef]
    """配置错误基类"""
    pass

class MissingAPIKeyError(ConfigError):
    """API Key 未配置"""
    pass

class InvalidConfigError(ConfigError):
    """配置值无效"""
    pass


# ---- 用户输入异常 ----

class UserInputError(NeuroTeXError):
    """用户输入错误（可恢复）"""
    pass

class InvalidInputError(UserInputError):
    """输入格式或内容无效"""
    pass

class ResourceLimitExceededError(UserInputError):
    """资源超出限制（文件过大、Token 超限等）"""
    pass


# ---- 辅助函数 ----

def handle_exception(exc: Exception) -> Dict[str, Any]:
    """
    将任意异常转换为统一错误字典。
    【需要实现】
    - NeuroTeXError 子类直接调用 to_dict()
    - 其他异常封装为 NeuroTeXError 并转换
    """
    pass


def is_recoverable(exc: Exception) -> bool:
    """
    判断异常是否可恢复（是否值得重试）。
    【需要实现】
    - NeuroTeXError: 读取 is_recoverable 属性
    - ConnectionError、TimeoutError: True
    - 其他: False
    """
    pass
