import os
import sys
import httpx
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse

from dashboard.auth import get_current_user
from dashboard.api_utils import AGENTS_DIR

# Add MCP module path for vault
MCP_MODULE_PATH = str(AGENTS_DIR / "mcp")
if MCP_MODULE_PATH not in sys.path:
    sys.path.append(MCP_MODULE_PATH)

try:
    from vault import get_vault
except ImportError:
    get_vault = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Provider configuration mapping
PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "default_scopes": [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ],
    },
    "microsoft": {
        "auth_url": (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        ),
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "default_scopes": [
            "openid", "profile", "email", "offline_access",
            "User.Read", "Mail.Read", "Files.Read.All"
        ],
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
    },
    "asana": {
        "auth_url": "https://app.asana.com/-/oauth_authorize",
        "token_url": "https://app.asana.com/-/oauth_token",
    },
    "hubspot": {
        "auth_url": "https://app.hubspot.com/oauth/authorize",
        "token_url": "https://api.hubapi.com/oauth/v1/token",
    }
}


def get_redirect_uri(request: Request, provider: str) -> str:
    """Determine the callback URI. Prefer tunnel URL if active."""
    # Try to import tunnel locally to avoid circular dependency
    from dashboard import tunnel as tunnel_mod
    base_url = tunnel_mod.get_tunnel_url()
    if not base_url:
        # Fallback to the request's base URL
        base_url = str(request.base_url).rstrip("/")

    return f"{base_url}/api/oauth/callback/{provider}"


@router.get("/authorize/{provider}")
async def authorize(
    provider: str,
    request: Request,
    scopes: Optional[str] = None,
    client_name: Optional[str] = None,  # For grouped providers
    user: dict = Depends(get_current_user)
):
    """Start the OAuth flow by redirecting to the provider's auth URL."""
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider} not supported"
        )

    config = PROVIDERS[provider]

    # Construct env var names for client_id and client_secret
    # Supports provider-grouped clients: GOOGLE_MAIN_CLIENT_ID or
    # GOOGLE_CLIENT_ID
    prefix = provider.upper()
    if client_name:
        prefix = f"{prefix}_{client_name.upper()}"

    client_id = os.environ.get(f"{prefix}_CLIENT_ID") or \
        os.environ.get(f"{provider.upper()}_CLIENT_ID")

    if not client_id:
        raise HTTPException(
            status_code=400,
            detail=f"{prefix}_CLIENT_ID not configured"
        )

    redirect_uri = get_redirect_uri(request, provider)

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": f"{client_name or 'default'}",  # Pass back client_name
    }

    # Provider-specific parameters
    if provider == "google":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    if scopes:
        params["scope"] = scopes
    elif "default_scopes" in config:
        params["scope"] = " ".join(config["default_scopes"])

    auth_url = config["auth_url"]
    from urllib.parse import urlencode
    query_string = urlencode(params)
    return RedirectResponse(url=f"{auth_url}?{query_string}")


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    request: Request,
    code: str,
    state: Optional[str] = None,
):
    """Callback from provider, exchanges code for token and stores in vault."""
    if provider not in PROVIDERS:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider} not supported"
        )

    config = PROVIDERS[provider]
    client_name = state if state != "default" else None

    prefix = provider.upper()
    if client_name:
        prefix = f"{prefix}_{client_name.upper()}"

    client_id = os.environ.get(f"{prefix}_CLIENT_ID") or \
        os.environ.get(f"{provider.upper()}_CLIENT_ID")
    client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET") or \
        os.environ.get(f"{provider.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Client credentials not configured"
        )

    redirect_uri = get_redirect_uri(request, provider)

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        # Notion and some others might need special headers or data format
        headers = {"Accept": "application/json"}
        response = await client.post(
            config["token_url"],
            data=token_data,
            headers=headers
        )
        if response.status_code != 200:
            logger.error(f"Failed to exchange code for token: {response.text}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Failed to exchange code",
                    "details": response.json()
                }
            )

        tokens = response.json()

    # Store tokens in vault
    vault = get_vault()
    if vault:
        # Define vault keys. Convention: oauth/{provider}/{client_name}/key
        vault_server = f"oauth/{provider}"
        vault_prefix = f"{client_name or 'default'}"

        vault.set(
            vault_server,
            f"{vault_prefix}/access_token",
            tokens.get("access_token")
        )
        if "refresh_token" in tokens:
            vault.set(
                vault_server,
                f"{vault_prefix}/refresh_token",
                tokens.get("refresh_token")
            )

        # Store metadata
        if "expires_in" in tokens:
            vault.set(
                vault_server,
                f"{vault_prefix}/expires_in",
                str(tokens.get("expires_in"))
            )
            vault.set(
                vault_server,
                f"{vault_prefix}/received_at",
                str(int(datetime.now().timestamp()))
            )

    return {
        "status": "success",
        "message": f"Successfully authenticated with {provider}",
        "vault_server": f"oauth/{provider}",
        "vault_prefix": f"{client_name or 'default'}"
    }


@router.get("/status/{provider}")
async def status(
    provider: str,
    client_name: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Check if we have valid tokens for the provider in the vault."""
    vault = get_vault()
    if not vault:
        return {"authenticated": False, "reason": "Vault not available"}

    vault_server = f"oauth/{provider}"
    vault_prefix = f"{client_name or 'default'}"

    access_token = vault.get(vault_server, f"{vault_prefix}/access_token")
    refresh_token = vault.get(vault_server, f"{vault_prefix}/refresh_token")

    if not access_token:
        return {"authenticated": False}

    # Check expiry if available
    received_at = vault.get(vault_server, f"{vault_prefix}/received_at")
    expires_in = vault.get(vault_server, f"{vault_prefix}/expires_in")

    is_expired = False
    if received_at and expires_in:
        now = int(datetime.now().timestamp())
        if now > int(received_at) + int(expires_in) - 60:  # 1 min buffer
            is_expired = True

    return {
        "authenticated": True,
        "is_expired": is_expired,
        "has_refresh_token": bool(refresh_token)
    }


async def refresh_provider_token(
    provider: str,
    client_name: Optional[str] = None
) -> Optional[str]:
    """Uses a stored refresh token to get a new access token."""
    vault = get_vault()
    if not vault:
        return None

    vault_server = f"oauth/{provider}"
    vault_prefix = f"{client_name or 'default'}"

    refresh_token = vault.get(vault_server, f"{vault_prefix}/refresh_token")
    if not refresh_token:
        return None

    config = PROVIDERS.get(provider)
    if not config:
        return None

    prefix = provider.upper()
    if client_name:
        prefix = f"{prefix}_{client_name.upper()}"

    client_id = os.environ.get(f"{prefix}_CLIENT_ID") or \
        os.environ.get(f"{provider.upper()}_CLIENT_ID")
    client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET") or \
        os.environ.get(f"{provider.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        return None

    refresh_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(config["token_url"], data=refresh_data)
        if response.status_code != 200:
            logger.error(f"Failed to refresh token: {response.text}")
            return None

        new_tokens = response.json()

    # Store new tokens
    vault.set(
        vault_server,
        f"{vault_prefix}/access_token",
        new_tokens.get("access_token")
    )
    if "refresh_token" in new_tokens:
        vault.set(
            vault_server,
            f"{vault_prefix}/refresh_token",
            new_tokens.get("refresh_token")
        )

    if "expires_in" in new_tokens:
        vault.set(
            vault_server,
            f"{vault_prefix}/expires_in",
            str(new_tokens.get("expires_in"))
        )
        vault.set(
            vault_server,
            f"{vault_prefix}/received_at",
            str(int(datetime.now().timestamp()))
        )

    return new_tokens.get("access_token")


@router.post("/refresh/{provider}")
async def refresh_endpoint(
    provider: str,
    client_name: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Force a token refresh."""
    new_token = await refresh_provider_token(provider, client_name)
    if not new_token:
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    return {"status": "success", "message": "Token refreshed"}
