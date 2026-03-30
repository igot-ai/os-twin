import json
import asyncio
from typing import List
from dashboard.ws_router import manager
from dashboard.notification_dispatcher import notification_dispatcher

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

        # Notify external platforms (async, non-blocking for this method's completion)
        asyncio.create_task(notification_dispatcher.dispatch(event_type, data))

broadcaster = Broadcaster()

# These will be initialized by api.py on startup
store = None
