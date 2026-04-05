"""Command & conversation endpoints for the Home tab chat interface."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["command"])

# ── In-memory conversation store ──
_conversations: Dict[str, dict] = {}


class CommandRequest(BaseModel):
    message: str
    mode: str = "auto"
    conversation_id: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    role: str  # 'user' | 'assistant'
    content: str
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    last_activity_at: str
    messages: List[MessageOut]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_reply(msg: str) -> str:
    """Simple intent-based stub response."""
    lower = msg.lower().strip()

    if any(kw in lower for kw in ["status", "what's running", "active"]):
        return ("Here's the current status:\n\n"
                "- **War rooms**: Check the Plans tab for active rooms\n"
                "- **Agents**: All agents are idle\n\n"
                "Use the Plans tab to create and manage plans.")
    elif any(kw in lower for kw in ["create plan", "build", "deploy", "make"]):
        return (f"I'd love to help you with that! Here's what I suggest:\n\n"
                f"1. Go to **Plans → New Plan** to create a structured plan\n"
                f"2. Describe your project and I'll help break it into EPICs\n"
                f"3. Then run it with `ostwin run`\n\n"
                f"Your request: *\"{msg}\"*")
    else:
        return (f"Hey there! 👋 The full conversational AI backend is coming soon.\n\n"
                f"In the meantime, you can:\n"
                f"- Use **Plans** to create and run agentic plans\n"
                f"- Use **MCP** to manage tool servers\n"
                f"- Use **Channels** to connect Telegram/Discord\n\n"
                f"Your message: *\"{msg}\"*")


@router.post("/command")
async def handle_command(req: CommandRequest):
    """Process a user command from the Home prompt."""
    conv_id = req.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    # Create conversation if new
    if conv_id not in _conversations:
        _conversations[conv_id] = {
            "id": conv_id,
            "title": req.message[:60],
            "created_at": now,
            "last_activity_at": now,
            "messages": [],
        }

    conv = _conversations[conv_id]

    # Add user message
    user_msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "content": req.message,
        "created_at": now,
    }
    conv["messages"].append(user_msg)

    # Generate and add assistant reply
    reply_content = _generate_reply(req.message)
    assistant_msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "content": reply_content,
        "created_at": now,
    }
    conv["messages"].append(assistant_msg)
    conv["last_activity_at"] = now

    return {
        "type": "command_response",
        "content": reply_content,
        "conversation_id": conv_id,
    }


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Return a conversation with all its messages."""
    conv = _conversations.get(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv
