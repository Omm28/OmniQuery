from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt import decode_access_token
from app.database import get_user_by_id

_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/auth/callback", auto_error=False)
_AUTH_COOKIE = "oq_token"

async def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(_bearer_scheme),
) -> dict:
    token = request.cookies.get(_AUTH_COOKIE) or bearer_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub' claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_optional_user(
    request: Request,
    bearer_token: str | None = Depends(_bearer_scheme),
) -> dict | None:
    try:
        return await get_current_user(request, bearer_token)
    except HTTPException:
        return None
