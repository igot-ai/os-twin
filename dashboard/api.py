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
from dashboard.tasks import startup_all
from dashboard.routes import auth, engagement, plans, rooms, system, mcp, skills, roles, memory
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
                    await websocket.send_json({"type": "pong"})
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
app.include_router(plans.router)
app.include_router(rooms.router)
app.include_router(system.router)
app.include_router(mcp.router)
app.include_router(skills.router)
app.include_router(roles.router)
app.include_router(memory.router)

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
        # 1. Exact file (e.g. favicon.ico, robots.txt)
        exact = FE_OUT_DIR / path
        if exact.is_file():
            return FileResponse(str(exact))
        # 2. {path}.html (e.g. /roles → roles.html)
        html_file = FE_OUT_DIR / f"{path}.html"
        if html_file.is_file():
            return FileResponse(str(html_file))
        # 3. {path}/index.html (e.g. /plans/plan-001 → plans/plan-001/index.html)
        index_file = FE_OUT_DIR / path / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))

        # 4. Dynamic route fallback — serve a pre-rendered template page.
        #    The Next.js JS bundle reads the real ID from window.location.
        import re
        parts = path.strip("/").split("/")

        # /plans/{id}/epics/{ref} → serve any pre-rendered epic page
        # Next.js static export generates flat HTML: plans/plan-001/epics/EPIC-001.html
        if len(parts) == 4 and parts[0] == "plans" and parts[2] == "epics":
            epics_dir = FE_OUT_DIR / "plans"
            if epics_dir.is_dir():
                for plan_dir in epics_dir.iterdir():
                    if not plan_dir.is_dir():
                        continue
                    epic_dir = plan_dir / "epics"
                    if epic_dir.is_dir():
                        # Check flat .html files first (e.g. EPIC-001.html)
                        for html_file in epic_dir.glob("*.html"):
                            return FileResponse(str(html_file))
                        # Then check nested index.html (e.g. EPIC-001/index.html)
                        for epic_sub in epic_dir.iterdir():
                            tpl = epic_sub / "index.html"
                            if tpl.is_file():
                                return FileResponse(str(tpl))

        # /plans/{id} → serve any pre-rendered plan page
        # Next.js static export generates flat HTML: plans/plan-001.html
        if len(parts) == 2 and parts[0] == "plans":
            plans_dir = FE_OUT_DIR / "plans"
            if plans_dir.is_dir():
                # Check flat .html files first (e.g. plan-001.html)
                for html_file in plans_dir.glob("*.html"):
                    return FileResponse(str(html_file))
                # Fallback: check nested index.html (e.g. plan-001/index.html)
                for sub in plans_dir.iterdir():
                    tpl = sub / "index.html"
                    if tpl.is_file():
                        return FileResponse(str(tpl))

        # 5. Final fallback
        return FileResponse(str(FE_OUT_DIR / "index.html"))


# --- Lifecycle ---
@app.on_event("startup")
async def on_startup():
    await startup_all()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ostwin Dashboard")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--project-dir", default=None, help="Project directory to monitor"
    )
    args = parser.parse_args()

    if args.project_dir:
        os.environ["OSTWIN_PROJECT_DIR"] = os.path.abspath(args.project_dir)
        # We need to manually update these for the print statements since they were imported early
        PROJECT_ROOT = Path(args.project_dir)
        WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"

    print("⬡ OS Twin Command Center (Modular)")
    print(f"  Project:   {args.project_dir or PROJECT_ROOT}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  URL:       http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
