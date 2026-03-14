from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class Room(BaseModel):
    room_id: str
    task_ref: str
    status: str
    retries: int
    message_count: int
    last_activity: Optional[str] = None
    task_description: Optional[str] = None
    goal_total: int = 0
    goal_done: int = 0

class Message(BaseModel):
    id: str
    ts: str
    from_: str
    to: str
    type: str
    ref: str
    body: str

class RunRequest(BaseModel):
    plan: str
    plan_id: Optional[str] = None

class ReactionRequest(BaseModel):
    entity_id: str
    user_id: str
    reaction_type: str

class CommentRequest(BaseModel):
    entity_id: str
    user_id: str
    body: str
    parent_id: Optional[str] = None

class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str

class CreatePlanRequest(BaseModel):
    path: str
    title: str = "Untitled"
    content: Optional[str] = None
    working_dir: Optional[str] = None

class SavePlanRequest(BaseModel):
    content: str

class RefineRequest(BaseModel):
    message: str
    plan_content: str = ""
    plan_id: str = ""
    model: str = ""
    chat_history: list = Field(default_factory=list)

class UpdatePlanRoleConfigRequest(BaseModel):
    default_model: str | None = None
    timeout_seconds: int | None = None
    cli: str | None = None
