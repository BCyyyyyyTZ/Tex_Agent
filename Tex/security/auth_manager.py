# ============================================================
# security/auth_manager.py — 认证管理器
# ============================================================
# 管理用户认证与会话令牌，支持 API Key 和 JWT 两种认证方式。
#
# 核心内容:
# - AuthMethod: 枚举（API_KEY / JWT / ANONYMOUS）
# - UserCredentials: 用户凭证（user_id/api_key/roles/created_at/is_active）
# - AuthToken: 访问令牌（token/user_id/expires_at/scopes）
# - AuthManager:
#   - authenticate(credentials) -> AuthToken: 验证凭证，签发令牌
#   - verify_token(token) -> Optional[AuthToken]: 验证令牌有效性
#   - revoke_token(token) -> None: 吊销令牌
#   - create_api_key(user_id) -> str: 为用户创建 API Key
#   - rotate_api_key(old_key) -> str: 轮换 API Key
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class AuthMethod(str, Enum):
    API_KEY = "api_key"
    JWT = "jwt"
    ANONYMOUS = "anonymous"


@dataclass
class AuthToken:
    token: str = ""
    user_id: str = ""
    expires_at: datetime = field(default_factory=datetime.now)
    scopes: List[str] = field(default_factory=list)
    auth_method: AuthMethod = AuthMethod.API_KEY


class AuthManager:
    """
    用户认证与令牌管理器。
    【需要实现 authenticate / verify_token / revoke_token / create_api_key】
    使用 python-jose 处理 JWT，bcrypt 哈希 API Key。
    """

    def authenticate(self, api_key: str) -> Optional[AuthToken]:
        """验证 API Key，签发令牌，【需要实现】"""
        pass

    def verify_token(self, token: str) -> Optional[AuthToken]:
        """验证令牌有效性，【需要实现】"""
        pass

    def revoke_token(self, token: str) -> None:
        """吊销令牌，【需要实现】"""
        pass

    def create_api_key(self, user_id: str) -> str:
        """为用户创建 API Key，【需要实现】"""
        pass
