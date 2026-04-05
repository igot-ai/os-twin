import asyncio
import json
import time
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._last_states: dict[str, Any] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    async def broadcast_epic_progress(self, plan_id: str, epic_ref: str, status: str, progress: int):
        await self.broadcast({
            "type": "epic_progress",
            "plan_id": plan_id,
            "epic_ref": epic_ref,
            "status": status,
            "progress": progress
        })

    async def broadcast_connection_health(self, service: str, status: str, latency: float = 0.0):
        await self.broadcast({
            "type": "connection_health",
            "service": service,
            "status": status,
            "latency": latency
        })

    @property
    def client_count(self):
        return len(self.active_connections)

manager = ConnectionManager()

async def handle_client_message(websocket: WebSocket, msg: dict):
    msg_type = msg.get("type")
    
    if msg_type == "ping":
        await websocket.send_json({"type": "pong", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

def create_ws_router() -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            await websocket.send_json({
                "event": "connected",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })

            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    await handle_client_message(websocket, msg)
                except json.JSONDecodeError:
                    pass

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            manager.disconnect(websocket)

    return router
