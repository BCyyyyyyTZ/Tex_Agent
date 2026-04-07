"""
[扩展] 安全与权限控制中间件接口定义。
预留权限验证、数据脱敏、访问日志和速率限制的拦截器接口。

TODO: 开发者 D 负责实现此类（第四阶段任务）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional


class Permission(Enum):
    """权限级别枚举，支持细粒度权限控制。"""

    READ = "read"       # 只读权限（查看历史、检索文献）
    WRITE = "write"     # 写入权限（修改文档、保存记忆）
    EXECUTE = "execute" # 执行权限（调用工具、触发 LLM）
    ADMIN = "admin"     # 管理员权限（配置修改、数据清空）


@dataclass
class SecurityContext:
    """
    请求安全上下文，携带当前用户的身份与权限信息。

    Attributes:
        user_id: 用户唯一标识符。
        permissions: 用户拥有的权限集合（Permission 枚举列表）。
        session_id: 当前会话唯一 ID。
        metadata: 扩展元数据（IP 地址、设备类型、请求来源等）。
    """

    user_id: str
    permissions: List[Permission]
    session_id: str
    metadata: dict = field(default_factory=dict)


class SecurityMiddleware(ABC):
    """
    [扩展] 安全控制中间件抽象基类。

    功能规划：
        1. 身份认证（Authentication）：
           验证用户令牌（JWT / API Key），返回安全上下文
        2. 权限授权（Authorization）：
           检查用户是否有权限执行特定操作
        3. 数据脱敏（Data Sanitization）：
           对输出中的敏感信息（API Key、邮箱、手机号等）进行遮蔽
        4. 速率限制（Rate Limiting）：
           防止 API 滥用，限制单位时间内的请求数量
        5. 审计日志（Audit Logging）：
           记录所有敏感操作的操作日志，支持安全审计

    TODO: 开发者 D 实现建议：
          - 认证可先用简单的 API Key 校验，后续升级为 JWT
          - 数据脱敏可使用正则匹配常见敏感信息模式
          - 速率限制可使用 Python 的令牌桶或 Redis 实现
    """

    @abstractmethod
    def authenticate(self, token: str) -> Optional[SecurityContext]:
        """
        验证用户身份令牌，返回安全上下文。

        Args:
            token: 用户身份令牌（JWT Token 或 API Key）。

        Returns:
            SecurityContext（认证成功）或 None（认证失败/令牌无效）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def authorize(self, context: SecurityContext, permission: Permission) -> bool:
        """
        检查用户安全上下文是否包含指定权限。

        Args:
            context: 用户安全上下文（由 authenticate() 返回）。
            permission: 需要检查的权限枚举值。

        Returns:
            True 表示有权限，False 表示无权限。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    @abstractmethod
    def sanitize(self, data: Any) -> Any:
        """
        对数据进行脱敏处理，移除或遮蔽敏感信息。

        Args:
            data: 原始数据（字符串、字典、列表等任意类型）。

        Returns:
            脱敏后的数据（保持原始类型）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError

    def intercept(self, func: Callable) -> Callable:
        """
        拦截器装饰器，在函数执行前后注入安全检查逻辑。

        使用方式：
            @security_middleware.intercept
            def sensitive_operation(user_token: str, ...):
                ...

        TODO: 开发者 D 在此实现：
              前置：authenticate(token) → authorize(ctx, permission)
              后置：sanitize(result) → audit_log(ctx, operation, result)

        Args:
            func: 需要被安全拦截保护的函数。

        Returns:
            包装后的函数（含安全检查逻辑）。

        Raises:
            NotImplementedError: 子类必须实现。
        """
        raise NotImplementedError(
            "SecurityMiddleware.intercept() 尚未实现。"
            "请实现前置认证授权 + 后置数据脱敏与审计日志逻辑。"
        )

    # TODO: 未来增加 rate_limit(user_id, max_requests_per_minute) 接口
    # TODO: 未来增加 audit_log(context, operation, result) 接口
