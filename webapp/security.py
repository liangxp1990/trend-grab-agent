"""认证与授权：密码哈希（PBKDF2）+ JWT 签发校验。

不引入额外依赖：hashlib.pbkdf2_hmac 与 pyjwt 已满足单管理员场景。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SETTINGS

_PBKDF2_ITERATIONS = 120_000
_SALT_BYTES = 16
_ALGORITHM = "HS256"
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """生成 PBKDF2 密码哈希（盐内嵌，格式 pbkdf2$iter$salt_hex$hash_hex）。

    Args:
        password: 明文密码。

    Returns:
        可直接存储的哈希字符串。
    """
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码与存储哈希是否匹配（恒定时间比较）。

    Args:
        password: 用户输入的明文。
        stored: 数据库中的哈希串。

    Returns:
        匹配返回 True；格式非法返回 False。
    """
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class TokenClaims:
    """JWT 载荷核心字段。"""

    sub: str
    role: str
    exp: float


def create_access_token(username: str, role: str) -> str:
    """签发访问令牌。

    Args:
        username: 用户名（sub 声明）。
        role: 角色声明，为 RBAC 预留。

    Returns:
        编码后的 JWT 字符串。
    """
    claims = {
        "sub": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + SETTINGS.token_expire_hours * 3600,
    }
    return jwt.encode(claims, SETTINGS.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    """解码并校验访问令牌。

    Args:
        token: JWT 字符串。

    Returns:
        令牌声明。

    Raises:
        ValueError: 令牌无效或已过期。
    """
    payload = jwt.decode(token, SETTINGS.secret_key, algorithms=[_ALGORITHM])
    return TokenClaims(sub=payload["sub"], role=payload.get("role", "admin"), exp=payload["exp"])


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> TokenClaims:
    """FastAPI 依赖：从 Authorization 头解析当前用户，失败返回 401。

    Args:
        credentials: Bearer 凭据。

    Returns:
        令牌声明。

    Raises:
        HTTPException: 缺失或非法令牌。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少访问令牌"
        )
    try:
        return decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"令牌无效: {exc}"
        ) from exc


CurrentUser = Annotated[TokenClaims, Depends(get_current_user)]


def client_ip(request: Request) -> str:
    """提取客户端 IP（兼容反代 X-Forwarded-For）。

    Args:
        request: FastAPI 请求对象。

    Returns:
        IP 字符串。
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
