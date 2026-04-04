import json
import asyncio
from typing import List
from dashboard.ws_router import manager

class Broadcaster:
    def __init__(self):
        self.sse_clients: List[asyncio.Queue] = []

    async def subscribe_sse(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.sse_clients.append(queue)
        return queue

    def unsubscribe_sse(self, queue: asyncio.Queue):
        if queue in self.sse_clients:
            self.sse_clients.remove(queue)

    async def broadcast(self, event_type: str, data: dict):
        event_dict = {"event": event_type, **data}
        json_event = json.dumps(event_dict)
        
        # SSE format
        sse_event = f"data: {json_event}\n\n"
        for queue in list(self.sse_clients):
            await queue.put(sse_event)
            
        # WebSocket format
        await manager.broadcast(event_dict)

broadcaster = Broadcaster()

# These will be initialized by api.py on startup
store = None
tunnel_url: str | None = None
