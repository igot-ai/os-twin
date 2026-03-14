import os
import sys
import uvicorn
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

# Add the project root to sys.path to allow running this script directly
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dashboard.api_utils import PROJECT_ROOT, AGENTS_DIR, WARROOMS_DIR, DEMO_DIR, USE_NEXTJS, NEXTJS_OUT_DIR
from dashboard.tasks import startup_all
from dashboard.routes import auth, engagement, plans, rooms, system
from dashboard.global_state import broadcaster

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OS Twin Command Center", version="0.1.0")

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
# Note: we need to import create_ws_router from the ws module in the parent directory
try:
    from ws import create_ws_router
    app.include_router(create_ws_router(), prefix="/api")
except ImportError:
    logger.warning("Could not import create_ws_router from ws.py")

app.include_router(auth.router)
app.include_router(engagement.router)
app.include_router(plans.router)
app.include_router(rooms.router)
app.include_router(system.router)

# --- Static Frontend Serving ---
if USE_NEXTJS:
    if (NEXTJS_OUT_DIR / "_next").exists():
        app.mount("/_next", StaticFiles(directory=str(NEXTJS_OUT_DIR / "_next")), name="nextjs_static")
    if (DEMO_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets")
else:
    if (DEMO_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets")

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
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--project-dir", default=None, help="Project directory to monitor")
    args = parser.parse_args()

    print("⬡ OS Twin Command Center (Modular)")
    print(f"  Project:   {args.project_dir or PROJECT_ROOT}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  URL:       http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
