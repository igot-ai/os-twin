"""
Auth module — ENV-based API-key authentication.

OSTWIN_API_KEY must be set. All API requests must include the key via:
  - Header: X-API-Key: <key>
  - Header: Authorization: Bearer <key>
  - Cookie: ostwin_auth_key=<key>

Unauthenticated requests receive 401.
"""

import os
import secrets
from typing import Optional
from datetime import timedelta

from fastapi import Request, HTTPException

# Kept for API compatibility with existing imports
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Cookie name used by the frontend
AUTH_COOKIE_NAME = "ostwin_auth_key"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True


def get_password_hash(password: str) -> str:
    return "disabled"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return "disabled"


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"ostwin_{secrets.token_urlsafe(32)}"


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from request headers or cookies.

    Checks (in order):
      1. X-API-Key header
      2. Authorization: Bearer <key>
      3. Cookie: ostwin_auth_key
    """
    # Check X-API-Key header
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key

    # Check Authorization: Bearer <key>
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # Check cookie
    cookie_key = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_key:
        return cookie_key

    return None


async def get_current_user(request: Request) -> dict:
    """Validate API key — always required.

    The key can be provided via header or cookie.
    Returns 401 if missing or invalid.
    """
    provided_key = _extract_api_key(request)
    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via X-API-Key header, Authorization: Bearer <key>, or cookie.",
        )

    # Read API key from environment at runtime (not cached at module load)
    # This ensures the key is available even if .env was loaded after module import
    expected_key = os.environ.get("OSTWIN_API_KEY", "")
    if not expected_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    # Allow X-User header for identity if API key is valid (for testing/dev)
    username = request.headers.get("x-user", "api-key-user")
    return {"username": username}
