import os
import sys
import uvicorn
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

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
    USE_NEXTJS,
    NEXTJS_OUT_DIR,
)
from dashboard.tasks import startup_all
from dashboard.routes import auth, engagement, plans, rooms, system, mcp, skills
from dashboard.global_state import broadcaster

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# --- Static Frontend Serving ---
if USE_NEXTJS:
    if (NEXTJS_OUT_DIR / "_next").exists():
        app.mount(
            "/_next",
            StaticFiles(directory=str(NEXTJS_OUT_DIR / "_next")),
            name="nextjs_static",
        )
    if (DEMO_DIR / "assets").exists():
        app.mount(
            "/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets"
        )
else:
    if (DEMO_DIR / "assets").exists():
        app.mount(
            "/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets"
        )


# --- Root Redirect/Index ---
@app.get("/")
async def index():
    if USE_NEXTJS:
        return FileResponse(str(NEXTJS_OUT_DIR / "index.html"))
    index_file = DEMO_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>OS Twin Command Center</h1><p>index.html not found.</p>")


# --- SPA Catch-all ---
@app.get("/{path:path}")
async def catch_all(path: str):
    if USE_NEXTJS:
        return FileResponse(str(NEXTJS_OUT_DIR / "index.html"))
    return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)


# --- Lifecycle ---
@app.on_event("startup")
async def on_startup():
    await startup_all()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ostwin Dashboard")
    parser.add_argument("--port", type=int, default=int(os.environ.get("OSTWIN_DASHBOARD_PORT", 9000)), help="Port to listen on")
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
