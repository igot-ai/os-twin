import os
import sys
import asyncio
import time
import json
import uvicorn
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# ── Load ~/.ostwin/.env early ──
# This makes the dashboard self-contained: it works whether started via
# `ostwin dashboard` (which already sources .env) or directly via `python api.py`.
# NOTE: This is a one-time bootstrap load.  For live hot-reload when the
# .env file is edited at runtime, see dashboard/env_watcher.py which is
# started as an async task in startup_all().
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
    WARROOMS_DIR,
    USE_FE,
    FE_OUT_DIR,
)
from dashboard.frontend_fallback import resolve_frontend_file
from dashboard.tasks import startup_all
# --- Route Imports ---
# Heavy libraries (torch, langchain) are now lazy-loaded inside these routes
# so direct imports here translate to < 2s total dashboard boot time.
from dashboard.routes import (
    auth, system, mcp, threads, plans, rooms, skills, 
    roles, memory, amem, channels, command, tunnel, 
    files, settings, engagement
)

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

# Attach handlers directly — basicConfig is a no-op if any import already
# triggered default logging configuration before this line.
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
if _file_handler not in _root.handlers:
    _root.addHandler(_file_handler)
if _console_handler not in _root.handlers:
    _root.addHandler(_console_handler)

logger = logging.getLogger(__name__)
logger.info("Dashboard log file: %s", _log_file)

# --- App + lifespan ----------------------------------------------------
# We need to drive the FastMCP streamable-HTTP app's lifespan from the
# parent FastAPI app, otherwise the FastMCP session manager's task group
# never starts and the first POST to /mcp/* dies with
# ``RuntimeError: Task group is not initialized. Make sure to use run().``
#
# FastAPI/Starlette do NOT propagate lifespans to mounted sub-apps, so we
# wire it in explicitly here. The MCP app reference is filled in further
# down (after we mount it) via ``_register_mcp_lifespan()``.
_mcp_lifespan_app: "object | None" = None


def _register_mcp_lifespan(mcp_app) -> None:
    """Called from the MCP mount block to hand the app to the lifespan ctx."""
    global _mcp_lifespan_app
    _mcp_lifespan_app = mcp_app


@asynccontextmanager
async def app_lifespan(_app):
    # --- Startup ---
    # Migrated from the legacy @app.on_event("startup") handler. Using
    # create_task so the lifecycle doesn't block the server from accepting
    # connections.
    asyncio.create_task(startup_all())

    # Drive the FastMCP app's own lifespan inside ours so its
    # ``session_manager.run()`` initialises the task group. Without this,
    # the first POST to /mcp/* dies with "Task group is not initialized".
    #
    # IMPORTANT: ``StreamableHTTPSessionManager`` is single-use — it
    # raises ``RuntimeError`` on a second ``run()`` call. In production
    # the lifespan runs exactly once per process and the singleton is
    # fine. In tests, multiple ``TestClient(app)`` contexts re-enter our
    # lifespan and would crash on the second entry. We handle both:
    #
    #   1. Reset the spent session manager (no-op if not yet created).
    #   2. Re-resolve the FastMCP ASGI app so the next mount uses a fresh
    #      session manager bound to the new task group.
    #   3. Re-mount the fresh inner app onto the parent so dispatch keeps
    #      working through the rest of this lifespan window.
    if _mcp_lifespan_app is not None:
        try:
            from dashboard.knowledge.mcp_server import (  # noqa: WPS433
                get_mcp_app,
                reset_mcp_session_manager,
            )

            reset_mcp_session_manager()
            fresh_mcp_app = get_mcp_app()
            _replace_mounted_mcp_app(_app, fresh_mcp_app)
        except Exception as _exc:  # noqa: BLE001
            logger.warning("MCP lifespan refresh failed: %s", _exc)
            fresh_mcp_app = _mcp_lifespan_app

        async with fresh_mcp_app.router.lifespan_context(fresh_mcp_app):
            try:
                yield
            finally:
                await _shutdown_app()
    else:
        # MCP mount failed (logged at mount time); still drive shutdown.
        try:
            yield
        finally:
            await _shutdown_app()


def _replace_mounted_mcp_app(parent_app, fresh_mcp_app) -> None:
    """Swap the inner FastMCP ASGI app on the existing /mcp mount.

    The parent FastAPI app's mount routes hold a reference to whatever was
    passed to ``app.mount(...)`` at startup. When we recreate the FastMCP
    app for a new lifespan, we need the existing mount to point at the new
    instance so request dispatch keeps working.

    The wrapped (auth) variant uses a Starlette wrapper containing
    ``Mount("/", app=_mcp_app)`` — so we walk into the wrapper to swap
    its inner mount as well.
    """
    from starlette.routing import Mount

    for route in parent_app.router.routes:
        if isinstance(route, Mount) and route.path == "/mcp":
            existing = route.app
            # Direct mount (dev mode, no auth) — replace and we're done.
            if hasattr(existing, "router") and any(
                isinstance(r, Mount)
                for r in getattr(existing.router, "routes", [])
            ):
                # Wrapped variant: existing is a Starlette() with a
                # Mount("/", app=_mcp_app) inside.
                for inner in existing.router.routes:
                    if isinstance(inner, Mount) and inner.path == "":
                        inner.app = fresh_mcp_app
                        return
            # Plain direct mount.
            route.app = fresh_mcp_app
            return


async def _shutdown_app() -> None:
    """Shutdown logic — migrated from the legacy on_event("shutdown") handler."""
    from dashboard.tunnel import stop_tunnel

    stop_tunnel()

    # Stop the bot process if it was started.
    import dashboard.global_state as gs

    if gs.bot_manager and gs.bot_manager.is_running:
        await gs.bot_manager.stop()


app = FastAPI(title="OS Twin Command Center", version="0.1.0", lifespan=app_lifespan)

# --- WebSocket ---
from fastapi import WebSocket, WebSocketDisconnect
from dashboard.ws_router import manager


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"event": "connected", "timestamp": "now"})
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    import time

                    await websocket.send_json(
                        {
                            "type": "pong",
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }
                    )
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


# --- Middleware ---
is_dev = (
    os.environ.get("NODE_ENV") == "development"
    or os.environ.get("OSTWIN_DEV_MODE") == "1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if is_dev else ["*"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$" if is_dev else None,
    allow_credentials=is_dev,
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
app.include_router(amem.router)
app.include_router(channels.router)
app.include_router(command.router)
app.include_router(tunnel.router)
app.include_router(files.router)
app.include_router(settings.router)

# --- MCP endpoint (knowledge) -------------------------------------------
# Mounted as a sub-app at /mcp via FastMCP's streamable-HTTP transport.
# Lazy: importing dashboard.knowledge.mcp_server does NOT pull kuzu / zvec /
# sentence_transformers / anthropic — those load on the first tool call.
# Auth: when OSTWIN_API_KEY is set AND OSTWIN_DEV_MODE != "1", a Starlette
# middleware enforces ``Authorization: Bearer <key>``. Otherwise (dev mode,
# or no key configured) anonymous access is allowed — the MCP transport's
# own JSON-RPC handshake still validates message structure.
try:
    from dashboard.knowledge.mcp_server import get_mcp_app

    _mcp_app = get_mcp_app()

    # Register the inner FastMCP app so app_lifespan() can drive its
    # ``session_manager.run()`` lifecycle. This is the fix for the
    # "Task group is not initialized" RuntimeError. The auth wrapper below
    # is transparent to the lifespan — only the inner app has the
    # FastMCP-specific lifespan_context.
    _register_mcp_lifespan(_mcp_app)

    if (
        os.environ.get("OSTWIN_DEV_MODE") != "1"
        and os.environ.get("OSTWIN_API_KEY")
    ):
        from starlette.applications import Starlette
        from starlette.middleware import Middleware
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
        from starlette.routing import Mount

        _expected_token = f"Bearer {os.environ.get('OSTWIN_API_KEY')}"

        class _MCPBearerAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):  # type: ignore[override]
                if request.headers.get("authorization") != _expected_token:
                    return JSONResponse(
                        {"error": "unauthorized", "code": "UNAUTHORIZED"},
                        status_code=401,
                    )
                return await call_next(request)

        wrapped_mcp = Starlette(
            routes=[Mount("/", app=_mcp_app)],
            middleware=[Middleware(_MCPBearerAuth)],
        )
        app.mount("/mcp", wrapped_mcp)
        logger.info("Knowledge MCP server mounted at /mcp (auth required)")
    else:
        app.mount("/mcp", _mcp_app)
        if os.environ.get("OSTWIN_DEV_MODE") == "1":
            _port = os.environ.get("DASHBOARD_PORT", "3366")
            logger.info(
                "Knowledge MCP server live at http://localhost:%s/mcp (dev mode, no auth)",
                _port,
            )
        else:
            logger.info("Knowledge MCP server mounted at /mcp (no auth — OSTWIN_API_KEY unset)")
except Exception as _mcp_exc:
    logger.warning("Failed to mount knowledge MCP server: %s", _mcp_exc)

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
        # Never serve SPA HTML for /api/* or /mcp/* paths — let those mounts
        # handle them. The /mcp exception is required because Starlette's
        # mount dispatch otherwise loses to this catch-all for the bare
        # ``/mcp`` path (no trailing slash).
        if path.startswith("api/") or path == "mcp" or path.startswith("mcp/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Route not found: /{path}")
        return FileResponse(str(resolve_frontend_file(FE_OUT_DIR, path)))


# --- Lifecycle ---
# NOTE: The legacy @app.on_event("startup") and @app.on_event("shutdown")
# handlers were migrated into ``app_lifespan`` (above) when we switched to
# the lifespan= constructor arg. FastAPI ignores on_event handlers when a
# lifespan context manager is passed to the FastAPI() constructor.


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ostwin Dashboard")
    parser.add_argument("--port", type=int, default=3366, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--project-dir", default=None, help="Project directory to monitor"
    )
    parser.add_argument(
        "--reindex", action="store_true", help="Force full re-index of vector store"
    )
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
    uvicorn.run(app, host=args.host, port=args.port)
