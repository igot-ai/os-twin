from typing import Optional, List, Dict, Any
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
    # "manual_save", "ai_refine", "expansion"
    change_source: str = "manual_save"


class RefineRequest(BaseModel):
    message: str
    plan_content: str = ""
    plan_id: str = ""
    model: str = ""
    chat_history: list = Field(default_factory=list)


class UpdatePlanRoleConfigRequest(BaseModel):
    default_model: str | None = None
    temperature: float | None = None
    timeout_seconds: int | None = None
    cli: str | None = None
    skill_refs: List[str] | None = None


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
    version: str = "0.1.0"
    category: Optional[str] = None
    score: Optional[float] = None
    applicable_roles: List[str] = Field(default_factory=list)
    content: str = ""
    path: Optional[str] = None
    relative_path: Optional[str] = None
    params: List[Dict[str, Any]] = Field(default_factory=list)
    changelog: List[Dict[str, Any]] = Field(default_factory=list)
    author: Optional[str] = None
    updated_at: Optional[str] = None
    forked_from: Optional[str] = None
    is_draft: bool = False
    active_epics_count: int = 0


class Role(BaseModel):
    id: str
    name: str
    provider: str  # 'Claude', 'GPT', 'Gemini', 'Custom'
    version: str
    temperature: float = 0.7
    budget_tokens_max: int = 500000
    max_retries: int = 3
    timeout_seconds: int = 300
    skill_refs: List[str] = Field(default_factory=list)
    system_prompt_override: Optional[str] = None
    created_at: str
    updated_at: str


class CreateRoleRequest(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9 \-_]+$"
    )
    provider: str
    version: str
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    budget_tokens_max: int = Field(500000, ge=1000, le=10000000)
    max_retries: int = Field(3, ge=1, le=10)
    timeout_seconds: int = Field(300, ge=60, le=3600)
    skill_refs: List[str] = Field(default_factory=list)
    system_prompt_override: Optional[str] = Field(None, max_length=2000)


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


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)
    description: str = Field(..., min_length=10, max_length=500)
    category: str
    applicable_roles: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    content: str = Field(..., min_length=50)
    is_draft: bool = False


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    category: Optional[str] = None
    applicable_roles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    is_draft: Optional[bool] = None
    major_bump: bool = False
    change_description: Optional[str] = None


class SkillForkRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)


class SkillValidateRequest(BaseModel):
    content: str


class SkillValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    markers: List[Dict[str, Any]] = Field(default_factory=list)


class SkillDuplicateCheckRequest(BaseModel):
    name: str


class SkillDuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    similar_skills: List[str] = Field(default_factory=list)
