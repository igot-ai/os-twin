import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Read API key at module load (same as dashboard.auth)
_API_KEY = os.environ.get("OSTWIN_API_KEY", "")
AUTH_COOKIE_NAME = "ostwin_auth_key"


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

    if not key or not _API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"},
        )

    import secrets
    if not secrets.compare_digest(str(key), _API_KEY):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"},
        )

    # Set cookie and return token
    response = JSONResponse(content={
        "access_token": _API_KEY,
        "token_type": "bearer",
        "username": "api-key-user",
    })
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=_API_KEY,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/",
    )
    return response


@router.get("/me")
async def read_users_me(user: dict = Depends(get_current_user)):
    """Return current user info — validates the API key from header or cookie."""
    return user


@router.get("/local-key")
async def get_local_key(request: Request):
    """Serve the API key to local frontend clients.

    This endpoint is intentionally unauthenticated so the frontend
    can bootstrap itself. In a cloud deployment, this endpoint should
    be disabled or restricted to localhost only.
    """
    if not _API_KEY:
        return {"key": None, "auth_enabled": True}

    return {"key": _API_KEY, "auth_enabled": True}


@router.post("/logout")
async def logout():
    """Clear the auth cookie."""
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return response
