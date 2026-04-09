from __future__ import annotations

import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.config import (
    GITHUB_AUTHORIZE_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_REDIRECT_URI,
    GITHUB_TOKEN_URL,
    GITHUB_USER_EMAILS_URL,
    GITHUB_USERINFO_URL,
    JWT_EXPIRE_MINUTES,
)
from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.database import upsert_user
from app.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])

AUTH_COOKIE = "oq_token"

@router.get("/login", summary="Redirect to GitHub OAuth login")
async def login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    authorization_url = f"{GITHUB_AUTHORIZE_URL}?{query_string}"

    logger.info("auth/login | redirecting to GitHub OAuth")
    return RedirectResponse(url=authorization_url)

@router.get("/callback", summary="GitHub OAuth callback")
async def callback(request: Request, code: str, state: str) -> RedirectResponse:
    stored_state = request.session.pop("oauth_state", None)
    if not stored_state or stored_state != state:
        logger.warning("auth/callback | CSRF state mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state. Possible CSRF attack.",
        )

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            logger.error("auth/callback | token exchange failed: %s", token_response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to exchange authorization code with GitHub.",
            )

        token_data = token_response.json()
        github_access_token: str | None = token_data.get("access_token")

        if not github_access_token:
            logger.error("auth/callback | no access_token in response: %s", token_data)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub did not return an access token.",
            )

        auth_headers = {
            "Authorization": f"Bearer {github_access_token}",
            "Accept": "application/vnd.github+json",
        }

        profile_response = await client.get(GITHUB_USERINFO_URL, headers=auth_headers)
        if profile_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch GitHub user profile.",
            )
        profile = profile_response.json()

        email: str | None = profile.get("email")
        if not email:
            emails_response = await client.get(
                GITHUB_USER_EMAILS_URL, headers=auth_headers
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None,
                )
                email = primary["email"] if primary else None

    user = upsert_user(
        github_id=profile["id"],
        login=profile.get("login", ""),
        email=email,
        name=profile.get("name") or profile.get("login", ""),
        avatar_url=profile.get("avatar_url", ""),
    )
    logger.info(
        "auth/callback | user upserted | github_id=%s login=%s",
        profile["id"],
        profile.get("login"),
    )

    access_token = create_access_token(data={"sub": str(user["id"])})

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=AUTH_COOKIE,
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        secure=False,
    )

    logger.info("auth/callback | JWT cookie set, redirecting to /")
    return response

@router.get("/logout", summary="Clear JWT cookie and redirect")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key=AUTH_COOKIE, httponly=True, samesite="lax")
    logger.info("auth/logout | cookie cleared")
    return response

@router.get("/me", summary="Return the currently authenticated user's profile")
async def me(current_user: dict = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(content={
        "id":         current_user["id"],
        "login":      current_user["login"],
        "name":       current_user["name"],
        "email":      current_user["email"],
        "avatar_url": current_user["avatar_url"],
    })
