import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

AUTH_COOKIE_NAME = "ostwin_auth_key"


def _get_expected_key() -> str:
    """Get API key from environment at runtime (not cached)."""
    return os.environ.get("OSTWIN_API_KEY", "")


@router.post("/token")
async def login_for_access_token(request: Request):
    """Authenticate with API key and set cookie.

    Accepts JSON body: {"key": "ostwin_..."} or form data.
    Sets the auth cookie on success.
    """
    # Try JSON body
    key = None
    try:
        body = await request.json()
        key = body.get("key", "")
    except Exception:
        # Try form data
        form = await request.form()
        key = form.get("key", "") or form.get("password", "")

    expected_key = _get_expected_key()
    if not key or not expected_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"},
        )

    import secrets

    if not secrets.compare_digest(str(key), expected_key):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"},
        )

    # Set cookie and return token
    response = JSONResponse(
        content={
            "access_token": expected_key,
            "token_type": "bearer",
            "username": "api-key-user",
        }
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=expected_key,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/",
    )
    return response


@router.get("/me")
async def read_users_me(request: Request):
    """Return current user info — validates the API key from header or cookie."""
    from dashboard.auth import get_current_user as _get_user

    user = await _get_user(request)
    return user


@router.post("/logout")
async def logout():
    """Clear the auth cookie."""
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return response
