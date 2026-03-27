# ============================================================
# security/permission_controller.py — 权限控制器
# ============================================================
# 基于角色的访问控制（RBAC），管理用户对系统功能的访问权限。
#
# 核心内容:
# - Permission: 枚举（READ/WRITE/DELETE/EXECUTE/ADMIN）
# - Role: 枚举（guest/user/premium/admin）
# - ROLE_PERMISSIONS: 角色 -> 权限映射表
# - PermissionController:
#   - check(user_id, action, resource) -> bool: 权限检查
#   - grant_role(user_id, role): 授予角色
#   - revoke_role(user_id, role): 撤销角色
#   - get_user_permissions(user_id) -> list: 获取用户所有权限
#   - require_permission(permission): 权限验证装饰器（用于 FastAPI 路由）
# ============================================================

from __future__ import annotations
from enum import Enum
from typing import Callable, List, Set


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class Role(str, Enum):
    GUEST = "guest"
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


ROLE_PERMISSIONS: dict = {
    Role.GUEST: {Permission.READ},
    Role.USER: {Permission.READ, Permission.WRITE, Permission.EXECUTE},
    Role.PREMIUM: {Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.DELETE},
    Role.ADMIN: set(Permission),
}


class PermissionController:
    """
    基于角色的权限控制器（RBAC）。
    【需要实现 check / grant_role / revoke_role / require_permission】
    """

    def check(
        self, user_id: str, permission: Permission, resource: str = ""
    ) -> bool:
        """检查用户权限，【需要实现】"""
        pass

    def grant_role(self, user_id: str, role: Role) -> None:
        """授予角色，【需要实现】"""
        pass

    def revoke_role(self, user_id: str, role: Role) -> None:
        """撤销角色，【需要实现】"""
        pass

    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """获取用户所有权限，【需要实现】"""
        pass

    def require_permission(self, permission: Permission) -> Callable:
        """FastAPI 权限验证依赖，【需要实现】"""
        pass
