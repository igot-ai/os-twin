import os
import sys
import json
import uvicorn
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ── Load ~/.ostwin/.env early (before any module reads env at import time) ──
# This makes the dashboard self-contained: it works whether started via
# `ostwin dashboard` (which already sources .env) or directly via `python api.py`.
_env_file = Path.home() / ".ostwin" / ".env"
if _env_file.is_file():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=False)
    except ImportError:
        # Manual fallback — only set vars not already in the environment
        with _env_file.open() as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#"):
                    continue
                if "=" in _line:
                    _k, _, _v = _line.partition("=")
                    _k = _k.strip()
                    _v = _v.strip().strip("\"'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v

# Add the project root and dashboard dir to sys.path
_dashboard_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dashboard_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

from dashboard.api_utils import (
    PROJECT_ROOT,
    AGENTS_DIR,
    WARROOMS_DIR,
    DEMO_DIR,
    USE_FE,
    FE_OUT_DIR,
)
from dashboard.frontend_fallback import resolve_frontend_file
from dashboard.tasks import startup_all
from dashboard.routes import auth, engagement, plans, rooms, system, mcp, skills, roles, memory, channels, command, threads, tunnel
from dashboard.global_state import broadcaster

# Configure logging — file + console
# All dashboard logs are written to ~/.ostwin/dashboard/debug.log (DEBUG level)
# Console output stays at INFO to keep the terminal clean.
_log_dir = Path.home() / ".ostwin" / "dashboard"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "debug.log"

from logging.handlers import RotatingFileHandler

_file_handler = RotatingFileHandler(
    str(_log_file), maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(
    logging.Formatter("%(levelname)-8s  %(name)s  %(message)s")
)

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
logger = logging.getLogger(__name__)
logger.info("Dashboard log file: %s", _log_file)

app = FastAPI(title="OS Twin Command Center", version="0.1.0")

# --- WebSocket ---
from fastapi import WebSocket, WebSocketDisconnect
from dashboard.ws_router import manager

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "event": "connected",
            "timestamp": "now"
        })
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    import time
                    await websocket.send_json({"type": "pong", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            except: pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
# (removed importlib logic for ws_router)
app.include_router(auth.router)
app.include_router(engagement.router)
app.include_router(threads.router)
app.include_router(plans.router)
app.include_router(rooms.router)
app.include_router(system.router)
app.include_router(mcp.router)
app.include_router(skills.router)
app.include_router(roles.router)
app.include_router(memory.router)
app.include_router(channels.router)
app.include_router(command.router)
app.include_router(tunnel.router)

# --- Static Frontend Serving ---
# Hybrid approach:
#   1. StaticFiles for /_next (JS/CSS/media assets — fast, cacheable)
#   2. Catch-all route for HTML pages with SPA fallback
#      (handles unknown plan IDs not pre-rendered at build time)
from fastapi.responses import FileResponse

if USE_FE:
    if (FE_OUT_DIR / "_next").exists():
        app.mount(
            "/_next",
            StaticFiles(directory=str(FE_OUT_DIR / "_next")),
            name="fe_next_static",
        )

    @app.api_route("/", methods=["GET", "HEAD"])
    async def fe_index():
        return FileResponse(str(FE_OUT_DIR / "index.html"))

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def fe_catch_all(path: str):
        return FileResponse(str(resolve_frontend_file(FE_OUT_DIR, path)))


# --- Lifecycle ---
@app.on_event("startup")
async def on_startup():
    await startup_all()


@app.on_event("shutdown")
async def on_shutdown():
    from dashboard.tunnel import stop_tunnel
    stop_tunnel()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ostwin Dashboard")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--project-dir", default=None, help="Project directory to monitor"
    )
    parser.add_argument("--reindex", action="store_true", help="Force full re-index of vector store")
    args = parser.parse_args()

    if args.project_dir:
        os.environ["OSTWIN_PROJECT_DIR"] = os.path.abspath(args.project_dir)
        # We need to manually update these for the print statements since they were imported early
        PROJECT_ROOT = Path(args.project_dir)
        WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"
    
    if args.reindex:
        os.environ["OSTWIN_REINDEX"] = "true"

    os.environ.setdefault("DASHBOARD_PORT", str(args.port))

    print("⬡ OS Twin Command Center (Modular)")
    print(f"  Project:   {args.project_dir or PROJECT_ROOT}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  URL:       http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
