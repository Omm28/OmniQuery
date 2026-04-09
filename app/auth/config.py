from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"[auth] Required environment variable '{name}' is not set. "
            f"Add it to your .env file."
        )
    return value

GITHUB_CLIENT_ID: str     = _require("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET: str = _require("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI: str  = os.getenv(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/callback"
)

GITHUB_AUTHORIZE_URL   = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL       = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL    = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"

JWT_SECRET_KEY:     str = _require("JWT_SECRET_KEY")
JWT_ALGORITHM:      str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", JWT_SECRET_KEY)
