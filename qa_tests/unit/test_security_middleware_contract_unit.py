from __future__ import annotations

import pytest

from security.middleware import Permission, SecurityContext, SecurityMiddleware


def test_permission_enum_values__stable() -> None:
    assert Permission.READ.value == "read"
    assert Permission.WRITE.value == "write"
    assert Permission.EXECUTE.value == "execute"
    assert Permission.ADMIN.value == "admin"


def test_security_context_dataclass__stores_fields() -> None:
    ctx = SecurityContext(
        user_id="u1",
        permissions=[Permission.READ, Permission.WRITE],
        session_id="s1",
        metadata={"ip": "127.0.0.1"},
    )
    assert ctx.user_id == "u1"
    assert Permission.READ in ctx.permissions
    assert ctx.metadata["ip"] == "127.0.0.1"


def test_security_middleware_intercept__not_implemented() -> None:
    class _M(SecurityMiddleware):
        def authenticate(self, token: str):
            raise NotImplementedError

        def authorize(self, context: SecurityContext, permission: Permission) -> bool:
            raise NotImplementedError

        def sanitize(self, data):
            raise NotImplementedError

    with pytest.raises(NotImplementedError) as e:
        _M().intercept(lambda: None)
    assert "尚未实现" in str(e.value)

