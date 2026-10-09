"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..audit import record_audit
from ..database import get_session
from ..models import User
from ..schemas import LoginRequest, TokenResponse
from ..security import CurrentUser, create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_LOGIN_RATE_WINDOW_SECONDS = 60
_MAX_LOGIN_FAILURES = 10
_login_failures: dict[str, list[float]] = {}


def _rate_limited(ip: str) -> bool:
    """简单登录限速：同 IP 60 秒内失败超过阈值则拒绝。"""
    import time

    now = time.time()
    failures = [ts for ts in _login_failures.get(ip, []) if now - ts < _LOGIN_RATE_WINDOW_SECONDS]
    _login_failures[ip] = failures
    return len(failures) >= _MAX_LOGIN_FAILURES


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """用户名密码登录，签发访问令牌。

    Args:
        payload: 登录凭据。
        request: 请求对象（用于限速与审计）。

    Returns:
        JWT 令牌与用户信息。

    Raises:
        HTTPException: 限速触发 429；凭据错误 401。
    """
    from ..security import client_ip

    ip = client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")

    with get_session() as session:
        user = session.query(User).filter_by(username=payload.username, is_active=True).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        import time

        _login_failures.setdefault(ip, []).append(time.time())
        record_audit(request, payload.username, "auth.login_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    record_audit(request, user.username, "auth.login")
    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        username=user.username,
        role=user.role,
    )


@router.get("/me")
def me(current: CurrentUser) -> dict[str, str]:
    """返回当前令牌身份。"""
    return {"username": current.sub, "role": current.role}


class PasswordChange(BaseModel):
    """修改密码请求。"""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.put("/password")
def change_password(payload: PasswordChange, request: Request, current: CurrentUser) -> dict:
    """修改当前用户密码（校验旧密码，写入审计）。

    Raises:
        HTTPException: 旧密码错误 401 / 用户不存在 404。
    """
    with get_session() as session:
        user = session.query(User).filter_by(username=current.sub, is_active=True).first()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not verify_password(payload.old_password, user.password_hash):
            record_audit(request, current.sub, "auth.password_change_failed")
            raise HTTPException(status_code=401, detail="旧密码不正确")
        user.password_hash = hash_password(payload.new_password)
    record_audit(request, current.sub, "auth.password_change", "密码已修改")
    return {"ok": True, "message": "密码已修改，下次登录生效"}
