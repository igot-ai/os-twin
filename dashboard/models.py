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
    plan_id: str


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
    change_source: str = "manual_save"  # "manual_save", "ai_refine", "expansion"


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


class StrategyParameter(BaseModel):
    name: str
    label: str
    value: float | int | str | bool
    type: str  # "int", "float", "bool", "string"


class Strategy(BaseModel):
    id: str
    name: str
    description: str
    status: str  # "active", "inactive"
    parameters: List[StrategyParameter]
    last_run: Optional[str] = None


class Skill(BaseModel):
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    trust_level: str = "experimental"
    source: str = "project"
    path: Optional[str] = None
    content: Optional[str] = None


class SkillSearchResponse(BaseModel):
    skills: List[Skill]
    total: int


class SkillInstallRequest(BaseModel):
    path: str


class SkillSearchRequest(BaseModel):
    query: str
    role: Optional[str] = None
    tags: List[str] = []


class SkillSyncResponse(BaseModel):
    synced_count: int
    added: List[str]
    updated: List[str]
    removed: List[str]
