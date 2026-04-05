import os
import logging
from fastapi import APIRouter, HTTPException, Depends

from dashboard.auth import get_current_user
from dashboard import tunnel as tunnel_mod
import dashboard.global_state as global_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])


@router.get("/status")
async def tunnel_status(_user=Depends(get_current_user)):
    return tunnel_mod.get_tunnel_status()


@router.post("/restart")
async def tunnel_restart(_user=Depends(get_current_user)):
    """Restart the tunnel (disconnect + reconnect) to get a new URL."""
    auth_token = os.environ.get("NGROK_AUTHTOKEN")
    if not auth_token:
        raise HTTPException(status_code=400, detail="NGROK_AUTHTOKEN not configured")

    tunnel_mod.stop_tunnel()

    port = int(os.environ.get("DASHBOARD_PORT", "9000"))
    domain = os.environ.get("NGROK_DOMAIN")
    try:
        url = await tunnel_mod.start_tunnel(port, auth_token, domain)
        global_state.tunnel_url = url
        return {"url": url, "message": "Tunnel restarted"}
    except Exception as e:
        global_state.tunnel_url = None
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share")
async def tunnel_share(_user=Depends(get_current_user)):
    """Send the tunnel URL to connected Telegram chats."""
    url = tunnel_mod.get_tunnel_url()
    if not url:
        raise HTTPException(status_code=400, detail="No active tunnel")

    try:
        from dashboard.notify import send_message
        sent = await send_message(f"📡 Dashboard is live at: {url}")
        return {"sent": sent, "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
