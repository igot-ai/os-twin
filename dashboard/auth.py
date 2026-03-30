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

from fastapi import Request, HTTPException, WebSocket

# Kept for API compatibility with existing imports
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Read API key from environment (set during install.sh)
_API_KEY = os.environ.get("OSTWIN_API_KEY", "")

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


def _extract_api_key_from_request(request: Request) -> Optional[str]:
    """Extract API key from request headers or cookies.

    Checks (in order):
      1. X-API-Key header
      2. Authorization: Bearer <key>
      3. Cookie: ostwin_auth_key
    """
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


def _extract_api_key_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Extract API key from websocket headers, cookies, or query params."""
    api_key = websocket.headers.get("x-api-key")
    if api_key:
        return api_key

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    cookie_key = websocket.cookies.get(AUTH_COOKIE_NAME)
    if cookie_key:
        return cookie_key

    q_key = websocket.query_params.get("key")
    if q_key:
        return q_key

    return None


def _validate_api_key(provided_key: Optional[str]) -> dict:
    """Validate a provided API key and return the authenticated user."""
    if not provided_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via X-API-Key header, Authorization: Bearer <key>, or cookie.",
        )

    if not _API_KEY or not secrets.compare_digest(provided_key, _API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return {"username": "api-key-user"}


async def get_current_user(request: Request) -> dict:
    """Validate API key for HTTP requests.

    The key can be provided via header or cookie.
    Returns 401 if missing or invalid.
    """
    return _validate_api_key(_extract_api_key_from_request(request))


async def get_current_user_ws(websocket: WebSocket) -> dict:
    """Validate API key for websocket connections."""
    return _validate_api_key(_extract_api_key_from_websocket(websocket))
