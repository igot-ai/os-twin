"""
Auth module — DISABLED (all endpoints are open).

To re-enable, restore the original auth.py with JWT + bcrypt logic.
"""

from typing import Optional
from datetime import timedelta

# Kept for API compatibility with api.py imports
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True


def get_password_hash(password: str) -> str:
    return "disabled"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return "disabled"


async def get_current_user() -> dict:
    """No-op auth — always returns admin user."""
    return {"username": "admin"}
