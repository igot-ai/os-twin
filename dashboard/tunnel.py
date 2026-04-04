"""
tunnel.py — ngrok tunnel manager for Ostwin Dashboard.

Auto-starts an ngrok tunnel when NGROK_AUTHTOKEN is set,
exposing the dashboard on a public URL for remote monitoring.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Module-level state
_tunnel = None
_tunnel_url: str | None = None
_started_at: str | None = None
_error: str | None = None


async def start_tunnel(port: int, auth_token: str, domain: str | None = None) -> str:
    """Start an ngrok tunnel to the given port. Returns the public URL."""
    global _tunnel, _tunnel_url, _started_at, _error

    try:
        from pyngrok import ngrok, conf

        # Configure auth token
        conf.get_default().auth_token = auth_token

        # Build connect kwargs
        kwargs = {"addr": port, "bind_tls": True}
        if domain:
            kwargs["hostname"] = domain

        # Disconnect any existing tunnel first
        if _tunnel:
            try:
                ngrok.disconnect(_tunnel.public_url)
            except Exception:
                pass

        _tunnel = ngrok.connect(**kwargs)
        _tunnel_url = _tunnel.public_url
        _started_at = datetime.now(timezone.utc).isoformat()
        _error = None

        logger.info("ngrok tunnel active: %s -> localhost:%d", _tunnel_url, port)
        return _tunnel_url

    except Exception as e:
        _error = str(e)
        _tunnel = None
        _tunnel_url = None
        _started_at = None
        logger.error("Failed to start ngrok tunnel: %s", e)
        raise


def stop_tunnel():
    """Disconnect the active ngrok tunnel."""
    global _tunnel, _tunnel_url, _started_at, _error

    if _tunnel:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(_tunnel.public_url)
            ngrok.kill()
            logger.info("ngrok tunnel stopped")
        except Exception as e:
            logger.warning("Error stopping ngrok tunnel: %s", e)
    _tunnel = None
    _tunnel_url = None
    _started_at = None
    _error = None


def get_tunnel_url() -> str | None:
    """Return the current public tunnel URL, or None if not active."""
    return _tunnel_url


def get_tunnel_status() -> dict:
    """Return tunnel status dict."""
    return {
        "active": _tunnel_url is not None,
        "url": _tunnel_url,
        "started_at": _started_at,
        "error": _error,
    }
